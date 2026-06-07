import json
import pathlib
import subprocess
import importlib.util
from pathlib import Path
from collections import Counter

BENCH_DIR = Path("/home/shahd-hl/bench")
TASKS_DIR = BENCH_DIR / "data" / "swe_tasks"
REPO_DIR = BENCH_DIR / "data" / "repos" / "astropy"
INJECTORS_DIR = BENCH_DIR / "injectors"
OUTPUT_FILE = BENCH_DIR / "data" / "benchmark.json"

LLM_INJECTORS = [
    "injector_fake_data.py",
    "injector_wrong_test_expectations.py",
    "injector_missing_functionality_tests.py",
    "injector_missing_scenario.py",
    "injector_architecture_reuse.py",
    "injector_data_model.py",
]

TEST_ONLY_INJECTORS = {
    'injector_wrong_test_expectations.py',
    'injector_missing_functionality_tests.py',
    'injector_missing_scenario.py',
}


def find_test_file(target_rel, repo_dir):
    basename = pathlib.Path(target_rel).stem
    matches = list(repo_dir.rglob(f'test_{basename}.py'))
    if matches:
        return matches[0]
    return None


def call_injector(injector_file, target_abs, target_rel):
    mod = load_injector(injector_file)
    if hasattr(mod, 'inject'):
        return mod.inject(target_abs)
    raise ValueError(f"No known inject function in {injector_file}")


def load_injector(injector_file):
    path = INJECTORS_DIR / injector_file
    module_name = injector_file.replace(".py", "")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_patched_files(patch_text):
    files = []
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            f = line[6:].strip()
            if f.endswith(".py"):
                files.append(f)
    return files


def apply_patch(patch_text, repo_dir):
    patch_file = repo_dir / "_temp_patch.diff"
    patch_file.write_text(patch_text)
    code, out, err = run_command(f"git apply {patch_file}", cwd=repo_dir)
    if code != 0:
        code, out, err = run_command(f"git apply --3way {patch_file}", cwd=repo_dir)
    if code != 0:
        rcode, rout, rerr = run_command(f"git apply --reverse --check {patch_file}", cwd=repo_dir)
        if rcode == 0:
            print("    Patch already applied, using file as-is (gold code)")
            code = 0
    patch_file.unlink(missing_ok=True)
    return code, out, err


def restore_file(file_rel, repo_dir):
    run_command(f"git checkout HEAD -- {file_rel}", cwd=repo_dir)


def checkout_commit(commit, repo_dir):
    code, out, err = run_command(f"git checkout {commit}", cwd=repo_dir)
    return code


def main():
    # Load existing entries
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            benchmark = json.load(f)
        print(f"Loaded {len(benchmark)} existing entries")
    else:
        benchmark = []
        print("No existing benchmark file, starting fresh")

    tasks = sorted(TASKS_DIR.glob("*.json"))
    print(f"Found {len(tasks)} tasks")

    for task_idx, task_file in enumerate(tasks):
        with open(task_file) as f:
            task = json.load(f)

        instance_id = task["instance_id"]
        base_commit = task["base_commit"]
        patch_text = task["patch"]

        print(f"\n=== Task {task_idx}: {instance_id} ===")

        run_command("git checkout -- .", cwd=REPO_DIR)
        run_command("git clean -fd", cwd=REPO_DIR)
        code = checkout_commit(base_commit, REPO_DIR)
        if code != 0:
            print(f"  ERROR: git checkout failed, skipping task")
            continue

        code, out, err = apply_patch(patch_text, REPO_DIR)
        if code != 0:
            print(f"  ERROR: patch failed: {err}, skipping task")
            continue

        patched_files = get_patched_files(patch_text)
        if not patched_files:
            print(f"  ERROR: no Python files in patch, skipping task")
            continue
        print(f"  Patched files: {patched_files}")

        for injector_file in LLM_INJECTORS:

            if injector_file in TEST_ONLY_INJECTORS:
                target_rel = None
                for pf in patched_files:
                    if '/test' in pf or pf.startswith('test_'):
                        target_rel = pf
                        break
                if target_rel is None:
                    test_file = find_test_file(patched_files[0], REPO_DIR)
                    if test_file is not None:
                        target_rel = str(test_file.relative_to(REPO_DIR))
                if target_rel is None:
                    print(f"  {injector_file} -- no test file found, skipping")
                    continue
            else:
                target_rel = patched_files[0]

            target_abs = str(REPO_DIR / target_rel)

            # Skip large files for architecture_reuse (causes LLM timeout)
            if injector_file == 'injector_architecture_reuse.py':
                file_size = pathlib.Path(target_abs).stat().st_size
                if file_size > 50000:
                    print(f"  {injector_file} -- file too large ({file_size} bytes), skipping")
                    continue

            print(f"  {injector_file} on {target_rel}")

            try:
                gold_code = Path(target_abs).read_text()
            except Exception as e:
                print(f"    ERROR reading file: {e}, skipping")
                continue

            try:
                record = call_injector(injector_file, target_abs, target_rel)
            except Exception as e:
                print(f"    ERROR running injector: {e}, skipping")
                restore_file(target_rel, REPO_DIR)
                continue

            try:
                buggy_code = Path(target_abs).read_text()
            except Exception as e:
                print(f"    ERROR reading injected file: {e}, skipping")
                restore_file(target_rel, REPO_DIR)
                continue

            if record.get("injected") == False:
                print(f"    SKIPPED: nothing to inject ({record.get('reason', '')})")
                restore_file(target_rel, REPO_DIR)
                continue

            entry = {
                "instance_id": instance_id,
                "base_commit": base_commit,
                "target_file": target_rel,
                "gold_code": gold_code,
                "buggy_code": buggy_code,
                "injection_record": record,
            }
            benchmark.append(entry)
            print(f"    Saved entry #{len(benchmark)}")
            restore_file(target_rel, REPO_DIR)

        # Save after every task so progress is not lost if interrupted
        with open(OUTPUT_FILE, "w") as f:
            json.dump(benchmark, f, indent=2)
        print(f"  Progress saved ({len(benchmark)} total entries so far)")

        run_command("git checkout HEAD -- .", cwd=REPO_DIR)

    print(f"\n=== DONE ===")
    print(f"Total entries: {len(benchmark)}")
    types = Counter(e['injection_record'].get('problem_type') for e in benchmark)
    for t, c in sorted(types.items()):
        print(f"  Type {t}: {c} entries")


if __name__ == "__main__":
    main()
