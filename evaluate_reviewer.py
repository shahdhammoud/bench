import json
import os
import re
from collections import defaultdict
from openai import OpenAI

PROBLEM_TYPES = {
    2: "Architecture/model reuse: a class is copied inline instead of imported from shared module",
    3: "Interface/signature mismatch: return type annotation changed to wrong type",
    4: "Data model implementation: Pydantic model replaced with plain dict or wrong schema",
    5: "Field mapping/conversion mistake: dictionary key access uses wrong key name",
    6: "Wrong field access: attribute access uses wrong field name",
    7: "Broad exception handling: specific except clause replaced with except Exception",
    8: "Fake data in implementation: real logic replaced with hardcoded fake return values",
    9: "Test duplication: test functions duplicated into a separate file",
    10: "Forbidden mocking in tests: real business logic component mocked with unittest.mock.patch",
    11: "Missing real functionality tests: actual call to function under test removed",
    12: "Missing scenario/preconditions: required precondition setup removed from test",
    13: "Wrong test expectations: assertion expected values changed to wrong ones",
}

PROMPT = """You are a code reviewer. Compare the GOLD CODE (correct) with the BUGGY CODE (has one deliberate bug injected).

Identify which single problem type from the list below best describes the bug:

{type_list}

GOLD CODE:
{gold}

BUGGY CODE:
{buggy}

Respond with ONLY a JSON object like:
{{"problem_type": <number>, "explanation": "<one sentence>"}}"""

def get_problem_type(entry):
    ir = entry.get("injection_record", {})
    if "problem_type" in ir:
        return ir["problem_type"]
    injections = ir.get("injections", [])
    if injections:
        return injections[0].get("problem_type")
    return None

def evaluate(benchmark_path, output_path):
    client = OpenAI(
        base_url="http://10.32.2.11:54000/v1",
        api_key="sk-litellm-token-hyper"
    )
    model = "qwen2.5-72b"

    with open(benchmark_path) as f:
        data = json.load(f)

    type_list = "\n".join(f"  {k}: {v}" for k, v in PROBLEM_TYPES.items())

    results = []
    correct = 0
    total = 0
    per_type = defaultdict(lambda: {"correct": 0, "total": 0})

    for i, entry in enumerate(data):
        gold = entry.get("gold_code", "")[:3000]
        buggy = entry.get("buggy_code", "")[:3000]
        true_type = get_problem_type(entry)

        if true_type is None:
            print(f"Entry {i}: no problem type found, skipping")
            continue

        prompt = PROMPT.format(
            type_list=type_list,
            gold=gold,
            buggy=buggy
        )

        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )
            raw = resp.choices[0].message.content.strip()
            # Extract JSON
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                predicted = int(parsed.get("problem_type", -1))
                explanation = parsed.get("explanation", "")
            else:
                predicted = -1
                explanation = raw

        except Exception as e:
            print(f"Entry {i}: LLM error — {e}")
            predicted = -1
            explanation = str(e)

        is_correct = predicted == true_type
        if is_correct:
            correct += 1
        total += 1
        per_type[true_type]["total"] += 1
        if is_correct:
            per_type[true_type]["correct"] += 1

        status = "✓" if is_correct else "✗"
        print(f"[{i+1:3}/{len(data)}] {status} true={true_type} pred={predicted} | {explanation[:80]}")

        results.append({
            "entry_index": i,
            "true_type": true_type,
            "predicted_type": predicted,
            "correct": is_correct,
            "explanation": explanation,
        })

    # Summary
    print(f"\n{'='*50}")
    print(f"OVERALL: {correct}/{total} = {correct/total*100:.1f}%")
    print(f"\nPer problem type:")
    for pt in sorted(per_type):
        d = per_type[pt]
        pct = d['correct']/d['total']*100 if d['total'] else 0
        print(f"  Type {pt:2}: {d['correct']}/{d['total']} = {pct:.0f}%  — {PROBLEM_TYPES.get(pt,'?')[:50]}")

    # Save results
    output = {
        "overall_accuracy": correct / total if total else 0,
        "correct": correct,
        "total": total,
        "per_type": {str(k): v for k, v in per_type.items()},
        "entries": results,
    }
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {output_path}")

if __name__ == "__main__":
    evaluate("data/benchmark.json", "data/evaluation_results.json")
