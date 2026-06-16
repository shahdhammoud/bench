import json
import pathlib
import subprocess
import importlib.util
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCH_DIR / 'data' / 'repos' / 'astropy'
INJECTORS_DIR = BENCH_DIR / 'injectors'
INPUT_FILE = BENCH_DIR / 'data' / 'benchmark.json'
OUTPUT_FILE = BENCH_DIR / 'data' / 'benchmark.json'


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def load_injector(injector_name):
    # injector_name like 'injector_broad_exception'
    path = INJECTORS_DIR / f'{injector_name}.py'
    spec = importlib.util.spec_from_file_location(injector_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def apply_patch(patch_text, repo_dir):
    patch_file = repo_dir / '_temp_patch.diff'
    patch_file.write_text(patch_text)
    code, out, err = run_command(f'git apply {patch_file}', cwd=repo_dir)
    if code != 0:
        code, out, err = run_command(f'git apply --3way {patch_file}', cwd=repo_dir)
    if code != 0:
        rcode, _, _ = run_command(f'git apply --reverse --check {patch_file}', cwd=repo_dir)
        if rcode == 0:
            code = 0
    patch_file.unlink(missing_ok=True)
    return code


def call_injector_on_file(injector_name, target_abs, target_rel):
    mod = load_injector(injector_name)
    if hasattr(mod, 'inject'):
        return mod.inject(target_abs)
    source = pathlib.Path(target_abs).read_text()
    if hasattr(mod, 'inject_broad_exception'):
        new_source, records = mod.inject_broad_exception(source)
        if not records:
            return {'injected': False, 'reason': 'nothing found'}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_wrong_field_access'):
        new_source, records = mod.inject_wrong_field_access(source)
        if not records:
            return {'injected': False, 'reason': 'nothing found'}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_interface_mismatch'):
        new_source, records = mod.inject_interface_mismatch(source)
        if not records:
            return {'injected': False, 'reason': 'nothing found'}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_field_mapping'):
        new_source, records = mod.inject_field_mapping(source)
        if not records:
            return {'injected': False, 'reason': 'nothing found'}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_forbidden_mocking'):
        new_source, records = mod.inject_forbidden_mocking(source)
        if not records:
            return {'injected': False, 'reason': 'nothing found'}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_test_duplication'):
        return mod.inject_test_duplication(str(REPO_DIR), target_rel)
    raise ValueError(f'No known inject function in {injector_name}')


# Map problem_type to injector name
TYPE_TO_INJECTOR = {
    2: 'injector_architecture_reuse',
    3: 'injector_interface_mismatch',
    4: 'injector_data_model',
    5: 'injector_field_mapping',
    6: 'injector_wrong_field_access',
    7: 'injector_broad_exception',
    8: 'injector_fake_data',
    9: 'injector_test_duplication',
    10: 'injector_forbidden_mocking',
    11: 'injector_missing_functionality_tests',
    12: 'injector_missing_scenario',
    13: 'injector_wrong_test_expectations',
}


def main():
    entries = json.load(open(INPUT_FILE))
    print(f'Loaded {len(entries)} entries')

    # Group by (instance_id, target_file)
    groups = defaultdict(list)
    for e in entries:
        key = (e['instance_id'], e['target_file'], e['base_commit'])
        groups[key].append(e)

    print(f'Total groups: {len(groups)}')
    merged = []

    for (instance_id, target_file, base_commit), group in sorted(groups.items()):
        print(f'\n--- {instance_id} — {target_file} ({len(group)} injections) ---')

        if len(group) == 1:
            # Single injection — keep as-is
            merged.append(group[0])
            print(f'  Kept as single entry (Type {group[0]["injection_record"].get("problem_type")})')
            continue

        # Multiple injections — need to stack them on the live file
        # Step 1: checkout correct commit
        run_command('git checkout -- .', cwd=REPO_DIR)
        run_command('git clean -fd', cwd=REPO_DIR)
        code, _, _ = run_command(f'git checkout {base_commit}', cwd=REPO_DIR)
        if code != 0:
            print(f'  ERROR: git checkout failed, keeping entries separate')
            merged.extend(group)
            continue

        # Step 2: apply gold patch (get patch from task file)
        task_files = sorted((BENCH_DIR / 'data' / 'swe_tasks').glob('*.json'))
        patch_text = None
        for tf in task_files:
            task = json.load(open(tf))
            if task['instance_id'] == instance_id:
                patch_text = task['patch']
                break

        if patch_text is None:
            # manual entries (type 3 extras) — just use gold_code directly
            target_abs = str(REPO_DIR / target_file)
            Path(target_abs).write_text(group[0]['gold_code'])
        else:
            code = apply_patch(patch_text, REPO_DIR)
            if code != 0:
                print(f'  ERROR: patch failed, keeping entries separate')
                merged.extend(group)
                run_command('git checkout -- .', cwd=REPO_DIR)
                continue

        target_abs = str(REPO_DIR / target_file)
        gold_code = Path(target_abs).read_text()

        # Step 3: run injectors sequentially
        successful_records = []
        types_applied = []

        for e in group:
            ptype = e['injection_record'].get('problem_type')
            injector_name = TYPE_TO_INJECTOR.get(ptype)
            if injector_name is None:
                print(f'  SKIP Type {ptype}: no injector mapping')
                continue

            print(f'  Applying Type {ptype} ({injector_name})...')
            try:
                record = call_injector_on_file(injector_name, target_abs, target_file)
                if record.get('injected') == False:
                    print(f'    SKIPPED: {record.get("reason", "")}')
                    continue
                successful_records.append(record)
                types_applied.append(ptype)
                print(f'    OK')
            except Exception as ex:
                print(f'    ERROR: {ex}')
                continue

        if not successful_records:
            print(f'  No successful injections, keeping entries separate')
            merged.extend(group)
            run_command('git checkout -- .', cwd=REPO_DIR)
            continue

        # Read the final buggy code after all injections
        buggy_code = Path(target_abs).read_text()

        # Clean up any duplicate files created by test_duplication
        for record in successful_records:
            injs = record.get('injections', [])
            for inj in injs:
                dup = inj.get('duplicate_file')
                if dup:
                    dup_path = REPO_DIR / dup
                    if dup_path.exists():
                        dup_path.unlink()

        # Restore file
        run_command(f'git checkout HEAD -- {target_file}', cwd=REPO_DIR)

        # Build merged entry
        merged_entry = {
            'instance_id': instance_id,
            'base_commit': base_commit,
            'target_file': target_file,
            'gold_code': gold_code,
            'buggy_code': buggy_code,
            'injection_record': {
                'injected': True,
                'problem_types': types_applied,
                'injections': successful_records,
            }
        }
        merged.append(merged_entry)
        print(f'  Merged entry with {len(successful_records)} injections: types {types_applied}')

    run_command('git checkout -- .', cwd=REPO_DIR)

    print(f'\n=== DONE ===')
    print(f'Original entries: {len(entries)}')
    print(f'Merged entries: {len(merged)}')

    # Count by number of injections
    from collections import Counter
    inj_counts = Counter()
    for e in merged:
        rec = e['injection_record']
        if 'problem_types' in rec:
            inj_counts[len(rec['problem_types'])] += 1
        else:
            inj_counts[1] += 1
    print('Entries by injection count:')
    for n, c in sorted(inj_counts.items()):
        print(f'  {n} injection(s): {c} entries')

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(merged, f, indent=2)
    print(f'Saved to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
