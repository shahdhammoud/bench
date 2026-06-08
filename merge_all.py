import json
import pathlib
import subprocess
import importlib.util
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path('/home/shahd-hl/bench')
TASKS_DIR = BENCH_DIR / 'data' / 'swe_tasks'
INJECTORS_DIR = BENCH_DIR / 'injectors'
OUTPUT_FILE = BENCH_DIR / 'data' / 'benchmark_final.json'

REPO_MAP = {
    'astropy/astropy':   BENCH_DIR / 'data' / 'repos' / 'astropy',
    'sympy/sympy':       BENCH_DIR / 'data' / 'repos' / 'sympy',
    'pytest-dev/pytest': BENCH_DIR / 'data' / 'repos' / 'pytest',
}

TYPE_TO_INJECTOR = {
    2:  'injector_architecture_reuse',
    3:  'injector_interface_mismatch',
    4:  'injector_data_model',
    5:  'injector_field_mapping',
    6:  'injector_wrong_field_access',
    7:  'injector_broad_exception',
    8:  'injector_fake_data',
    9:  'injector_test_duplication',
    10: 'injector_forbidden_mocking',
    11: 'injector_missing_functionality_tests',
    12: 'injector_missing_scenario',
    13: 'injector_wrong_test_expectations',
}

MAX_FILE_SIZE = 50000


def run_command(cmd, cwd=None):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def load_injector(injector_name):
    path = INJECTORS_DIR / f'{injector_name}.py'
    spec = importlib.util.spec_from_file_location(injector_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def call_injector_on_file(injector_name, target_abs, target_rel, repo_dir):
    mod = load_injector(injector_name)
    if hasattr(mod, 'inject'):
        return mod.inject(target_abs)
    source = pathlib.Path(target_abs).read_text()
    if hasattr(mod, 'inject_broad_exception'):
        new_source, records = mod.inject_broad_exception(source)
        if not records: return {'injected': False}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_wrong_field_access'):
        new_source, records = mod.inject_wrong_field_access(source)
        if not records: return {'injected': False}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_interface_mismatch'):
        new_source, records = mod.inject_interface_mismatch(source)
        if not records: return {'injected': False}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_field_mapping'):
        new_source, records = mod.inject_field_mapping(source)
        if not records: return {'injected': False}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_forbidden_mocking'):
        new_source, records = mod.inject_forbidden_mocking(source)
        if not records: return {'injected': False}
        pathlib.Path(target_abs).write_text(new_source)
        return records[0]
    if hasattr(mod, 'inject_test_duplication'):
        return mod.inject_test_duplication(str(repo_dir), target_rel)
    raise ValueError(f'No inject function in {injector_name}')


def apply_patch(patch_text, repo_dir):
    patch_file = repo_dir / '_temp_patch.diff'
    patch_file.write_text(patch_text)
    code, _, _ = run_command(f'git apply {patch_file}', cwd=repo_dir)
    if code != 0:
        code, _, _ = run_command(f'git apply --3way {patch_file}', cwd=repo_dir)
    if code != 0:
        rcode, _, _ = run_command(f'git apply --reverse --check {patch_file}', cwd=repo_dir)
        if rcode == 0: code = 0
    patch_file.unlink(missing_ok=True)
    return code


def get_repo_for_entry(e):
    repo_name = e.get('repo', 'astropy/astropy')
    return repo_name, REPO_MAP.get(repo_name)


def find_patch_for_task(instance_id):
    for tf in sorted(TASKS_DIR.glob('*.json')):
        task = json.load(open(tf))
        if task['instance_id'] == instance_id:
            return task.get('patch'), task.get('repo', 'astropy/astropy')
    return None, None


def main():
    # Load both sets
    astropy_entries = json.load(open(BENCH_DIR / 'data' / 'benchmark.json'))
    new_entries = json.load(open(BENCH_DIR / 'data' / 'benchmark_new.json'))

    # astropy entries are already merged — keep as-is
    # new entries need to be merged
    all_raw = new_entries
    print(f'Astropy merged entries: {len(astropy_entries)}')
    print(f'New raw entries to merge: {len(all_raw)}')

    # Group new entries by (instance_id, target_file)
    groups = defaultdict(list)
    for e in all_raw:
        key = (e['instance_id'], e['target_file'], e.get('repo', 'astropy/astropy'))
        groups[key].append(e)

    print(f'Groups to merge: {len(groups)}')
    merged_new = []

    for (instance_id, target_file, repo_name), group in sorted(groups.items()):
        repo_dir = REPO_MAP.get(repo_name)
        base_commit = group[0]['base_commit']

        print(f'\n--- {instance_id} — {target_file} ({len(group)} injections) ---')

        if len(group) == 1:
            merged_new.append(group[0])
            print(f'  Kept as single entry')
            continue

        # Get patch
        patch_text, _ = find_patch_for_task(instance_id)
        if patch_text is None:
            print(f'  ERROR: patch not found, keeping separate')
            merged_new.extend(group)
            continue

        # Checkout and patch
        run_command('git checkout -- .', cwd=repo_dir)
        run_command('git clean -fd', cwd=repo_dir)
        code, _, _ = run_command(f'git checkout {base_commit}', cwd=repo_dir)
        if code != 0:
            print(f'  ERROR: checkout failed')
            merged_new.extend(group)
            continue

        code = apply_patch(patch_text, repo_dir)
        if code != 0:
            print(f'  ERROR: patch failed')
            merged_new.extend(group)
            run_command('git checkout -- .', cwd=repo_dir)
            continue

        target_abs = str(repo_dir / target_file)
        gold_code = Path(target_abs).read_text()

        successful_records = []
        types_applied = []

        for e in group:
            ptype = e['injection_record'].get('problem_type')
            injector_name = TYPE_TO_INJECTOR.get(ptype)
            if injector_name is None:
                continue

            # Skip large files for architecture_reuse
            if injector_name == 'injector_architecture_reuse':
                if Path(target_abs).stat().st_size > MAX_FILE_SIZE:
                    print(f'  SKIP Type {ptype}: file too large')
                    continue

            print(f'  Applying Type {ptype}...')
            try:
                record = call_injector_on_file(injector_name, target_abs, target_file, repo_dir)
                if record.get('injected') == False:
                    print(f'    SKIPPED')
                    continue
                successful_records.append(record)
                types_applied.append(ptype)
                print(f'    OK')
            except Exception as ex:
                print(f'    ERROR: {ex}')
                continue

        if not successful_records:
            print(f'  No successful injections, keeping separate')
            merged_new.extend(group)
            run_command('git checkout -- .', cwd=repo_dir)
            continue

        buggy_code = Path(target_abs).read_text()

        # Clean up duplicate files from test_duplication
        for record in successful_records:
            for inj in record.get('injections', []):
                dup = inj.get('duplicate_file')
                if dup:
                    dup_path = repo_dir / dup
                    if dup_path.exists():
                        dup_path.unlink()

        run_command(f'git checkout HEAD -- {target_file}', cwd=repo_dir)

        merged_entry = {
            'instance_id': instance_id,
            'base_commit': base_commit,
            'repo': repo_name,
            'target_file': target_file,
            'gold_code': gold_code,
            'buggy_code': buggy_code,
            'injection_record': {
                'injected': True,
                'problem_types': types_applied,
                'injections': successful_records,
            }
        }
        merged_new.append(merged_entry)
        print(f'  Merged: types {types_applied}')

        run_command('git checkout HEAD -- .', cwd=repo_dir)

    # Combine astropy + merged new
    final = astropy_entries + merged_new
    print(f'\n=== DONE ===')
    print(f'Astropy entries: {len(astropy_entries)}')
    print(f'Merged new entries: {len(merged_new)}')
    print(f'Total: {len(final)}')

    from collections import Counter
    inj_counts = Counter()
    for e in final:
        rec = e['injection_record']
        if 'problem_types' in rec:
            inj_counts[len(rec['problem_types'])] += 1
        else:
            inj_counts[1] += 1
    print('Entries by injection count:')
    for n, c in sorted(inj_counts.items()):
        print(f'  {n} injection(s): {c} entries')

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(final, f, indent=2)
    print(f'Saved to {OUTPUT_FILE}')


if __name__ == '__main__':
    main()
