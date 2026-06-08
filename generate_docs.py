import json
import sys
import os
from pathlib import Path

sys.path.insert(0, '/home/shahd-hl/bench')
os.environ['GPT_OSS_HOST'] = 'http://10.32.2.11:54000/v1'
os.environ['GPT_OSS_KEY'] = 'sk-litellm-token-hyper'
os.environ['GPT_OSS_MODEL_NAME'] = 'gpt-oss-120b'

from openai import OpenAI
from doc_generator.workflow import run_workflow

BENCHMARK_FILE = Path('/home/shahd-hl/bench/data/benchmark.json')
client = OpenAI(base_url='http://10.32.2.11:54000/v1', api_key='sk-litellm-token-hyper')
MODEL = 'gpt-oss-120b'


def extract_doc(result):
    return {
        'project_name': result.get('project_name'),
        'project_goal': result.get('project_goal'),
        'functional_requirements': result.get('functional_requirements'),
        'non_functional_requirements': result.get('non_functional_requirements'),
        'module_docs': result.get('module_docs'),
        'critic_score': result.get('critic_score'),
        'critic_problems': result.get('critic_problems'),
    }


def main():
    entries = json.load(open(BENCHMARK_FILE))
    print(f'Total entries: {len(entries)}')

    already_done = sum(1 for e in entries if e.get('documentation'))
    print(f'Already have docs: {already_done}')

    for i, e in enumerate(entries):
        if e.get('documentation'):
            print(f'Entry {i+1}/{len(entries)} — already has docs, skipping')
            continue

        print(f'\nEntry {i+1}/{len(entries)} — {e["instance_id"]} — {e["target_file"]}')

        files = {e['target_file']: e['gold_code']}

        try:
            result = run_workflow(files, client, MODEL)
            e['documentation'] = extract_doc(result)
            print(f'  OK — critic score: {result.get("critic_score", "N/A")}')
        except Exception as ex:
            print(f'  ERROR: {ex}')
            e['documentation'] = None

        # Save after every entry
        with open(BENCHMARK_FILE, 'w') as f:
            json.dump(entries, f, indent=2)

    done = sum(1 for e in entries if e.get('documentation'))
    print(f'\nDone. {done}/{len(entries)} entries have documentation.')


if __name__ == '__main__':
    main()
