import json
import pathlib
import subprocess
import importlib.util
from pathlib import Path

BENCH_DIR = Path("/home/shahd-hl/bench")
TASKS_DIR = BENCH_DIR / "data" / "swe_tasks"
REPO_DIR = BENCH_DIR / "data" / "repos" / "astropy"
INJECTORS_DIR = BENCH_DIR / "injectors"
OUTPUT_FILE = BENCH_DIR / "data" / "benchmark.json"

INJECTOR_FILES = [
    "injector_broad_exception.py",
    "injector_wrong_field_access.py",
    "injector_interface_mismatch.py",
    "injector_test_duplication.py",
    "injector_forbidden_mocking.py",
    "injector_field_mapping.py",
    "injector_project_structure.py",
    "injector_fake_data.py",
    "injector_wrong_test_expectations.py",
    "injector_missing_functionality_tests.py",
    "injector_missing_scenario.py",
    "injector_architecture_reuse.py",
    "injector_data_model.py",
]

INJECTIONS_PER_TASK = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]

# These injectors only work on test files
TEST_ONLY_INJECTORS = {
    'injector_wrong_test_expectations.py',
    'injector_missing_functionality_tests.py',
    'injector_missing_scenario.py',
}

# This injector moves the file so needs special handling
DESTRUCTIVE_INJECTORS = {
    'injector_project_structure.py',
}


def find_test_file(target_rel, repo_dir):
    """Find the test file corresponding to a source file."""
    basename = pathlib.Path(target_rel).stem
    matches = list(repo_dir.rglob(f'test_{basename}.py'))
    if matches:
        return matches[0]
    return None


def call_injector(injector_file, target_abs, target_rel):
    mod = load_injector(injector_file)
    # LLM-based injectors: inject(file_path)
    if hasattr(mod, 'inject'):
        return mod.inject(target_abs)
    # Rule-based: inject_into_file(filepath)
    if hasattr(mod, 'inject_into_file'):
        return mod.inject_into_file(target_abs)
    # String-based injectors: read, inject, write back
    source = pathlib.Path(target_abs).read_text()
    if hasattr(mod, 'inject_broad_exception'):
        new_source, records = mod.inject_broad_exception(source)
        if not records:
            raise ValueError("No broad exceptions found")
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_wrong_field_access'):
        new_source, records = mod.inject_wrong_field_access(source)
        if not records:
            raise ValueError("No field access found")
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_interface_mismatch'):
        new_source, records = mod.inject_interface_mismatch(source)
        if not records:
            raise ValueError("No interface mismatch found")
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_field_mapping'):
        new_source, records = mod.inject_field_mapping(source)
        if not records:
            raise ValueError("No field mapping found")
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_forbidden_mocking'):
        new_source, records = mod.inject_forbidden_mocking(source)
        if not records:
            raise ValueError("No injectable functions found")
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_test_duplication'):
        repo_path = str(REPO_DIR)
        return mod.inject_test_duplication(repo_path, target_rel)
    if hasattr(mod, 'inject_project_structure'):
        repo_path = str(REPO_DIR)
        return mod.inject_project_structure(repo_path, target_rel)
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
    # First check if patch applies cleanly
    code, out, err = run_command(f"git apply {patch_file}", cwd=repo_dir)
    if code != 0:
        # Try with --3way fallback
        code, out, err = run_command(f"git apply --3way {patch_file}", cwd=repo_dir)
    if code != 0:
        # Check if patch is already applied (reverse check)
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
    tasks = sorted(TASKS_DIR.glob("*.json"))
    print(f"Found {len(tasks)} tasks")

    benchmark = []
    injector_index = 0

    for task_idx, task_file in enumerate(tasks):
        with open(task_file) as f:
            task = json.load(f)

        instance_id = task["instance_id"]
        base_commit = task["base_commit"]
        patch_text = task["patch"]
        n_injections = INJECTIONS_PER_TASK[task_idx]

        print(f"\n=== Task {task_idx}: {instance_id} ({n_injections} injections) ===")

        print(f"  Checking out {base_commit[:10]}...")
        run_command("git checkout -- .", cwd=REPO_DIR)
        run_command("git clean -fd", cwd=REPO_DIR)
        code = checkout_commit(base_commit, REPO_DIR)
        if code != 0:
            print(f"  ERROR: git checkout failed, skipping task")
            continue

        print(f"  Applying gold patch...")
        code, out, err = apply_patch(patch_text, REPO_DIR)
        if code != 0:
            print(f"  ERROR: patch failed: {err}, skipping task")
            continue

        patched_files = get_patched_files(patch_text)
        if not patched_files:
            print(f"  ERROR: no Python files in patch, skipping task")
            continue
        print(f"  Patched files: {patched_files}")

        for inj_i in range(n_injections):
            injector_file = INJECTOR_FILES[injector_index % len(INJECTOR_FILES)]
            injector_index += 1

            target_rel = patched_files[inj_i % len(patched_files)]
            target_abs = str(REPO_DIR / target_rel)

            # Test-only injectors: find the test file instead
            actual_rel = target_rel
            actual_abs = target_abs
            if injector_file in TEST_ONLY_INJECTORS:
                test_file = find_test_file(target_rel, REPO_DIR)
                if test_file is None:
                    print(f"  Injection {inj_i+1}/{n_injections}: {injector_file} -- no test file found, skipping")
                    continue
                actual_abs = str(test_file)
                actual_rel = str(test_file.relative_to(REPO_DIR))

            # Skip destructive injectors in assembly
            if injector_file in DESTRUCTIVE_INJECTORS:
                print(f"  Injection {inj_i+1}/{n_injections}: {injector_file} -- skipped (destructive)")
                continue

            print(f"  Injection {inj_i+1}/{n_injections}: {injector_file} on {actual_rel}")

            try:
                gold_code = Path(actual_abs).read_text()
            except Exception as e:
                print(f"    ERROR reading file: {e}, skipping")
                continue

            try:
                record = call_injector(injector_file, actual_abs, actual_rel)
            except Exception as e:
                print(f"    ERROR running injector: {e}, skipping")
                restore_file(actual_rel, REPO_DIR)
                continue

            try:
                buggy_code = Path(actual_abs).read_text()
            except Exception as e:
                print(f"    ERROR reading injected file: {e}, skipping")
                restore_file(actual_rel, REPO_DIR)
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

            restore_file(actual_rel, REPO_DIR)

        run_command("git checkout HEAD -- .", cwd=REPO_DIR)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(benchmark, f, indent=2)

    print(f"\n=== DONE ===")
    print(f"Total entries: {len(benchmark)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
