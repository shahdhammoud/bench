import ast
import json
import sys
import re
from openai import OpenAI
from collections import Counter
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / '.env')


# ── LLM client ────────────────────────────────────────────────────────────────
client = OpenAI(
    base_url=os.getenv('LLM_BASE_URL'),
    api_key=os.getenv('LLM_API_KEY'),
)
MODEL = "gpt-oss-120b"

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_test_functions(source: str):
    """Return list of (name, lineno_start, lineno_end) for test functions
    that contain at least one function call and at least one assert."""
    tree = ast.parse(source)
    candidates = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(node))
        has_call = any(isinstance(n, ast.Call) for n in ast.walk(node))
        if not has_assert or not has_call:
            continue
        end = node.end_lineno if hasattr(node, "end_lineno") else node.lineno
        candidates.append((node.name, node.lineno, end))

    return candidates


def get_function_source(source: str, lineno_start: int, lineno_end: int) -> str:
    lines = source.splitlines()
    return "\n".join(lines[lineno_start - 1 : lineno_end])


def ask_llm(function_source: str) -> str:
    prompt = f"""You are a code mutation tool. Your job is to inject a subtle bug into a test function.

Given the following Python test function, remove or comment out the actual call to the real function being tested.
Rules:
- Keep the function signature (name, parameters, decorators) exactly the same.
- Keep all setup code (variable definitions, imports, data preparation).
- Remove or comment out the line that actually calls the function under test.
- Keep the assert statements but they should now assert against the setup variables only (not the result of the real call).
- The result is a test that runs without errors but never actually tests the real function.
- Do NOT add any explanation or comments.
- Return ONLY the modified function code, nothing else.

Function:
{function_source}
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def clean_code(raw: str) -> str:
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    return raw.strip()


def self_consistency(function_source: str, n: int = 3) -> str:
    responses = []
    for i in range(n):
        print(f"  LLM call {i+1}/{n}...")
        raw = ask_llm(function_source)
        cleaned = clean_code(raw)
        responses.append(cleaned)

    counter = Counter(responses)
    best = counter.most_common(1)[0][0]
    return best


def replace_function_in_source(source: str, lineno_start: int, lineno_end: int, new_func: str) -> str:
    lines = source.splitlines()
    before = lines[:lineno_start - 1]
    after = lines[lineno_end:]
    return "\n".join(before + new_func.splitlines() + after)


# ── Main ──────────────────────────────────────────────────────────────────────

def inject(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    candidates = extract_test_functions(source)
    if not candidates:
        raise ValueError(f"No injectable test functions found in {file_path}")

    name, start, end = candidates[0]
    print(f"Injecting into test function '{name}' (lines {start}-{end})")

    original_func = get_function_source(source, start, end)
    print("Running self-consistency (3 LLM calls)...")
    new_func = self_consistency(original_func, n=3)

    new_source = replace_function_in_source(source, start, end, new_func)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_source)

    record = {
        "injector": "injector_missing_functionality_tests",
        "problem_type": 11,
        "problem_type_name": "Missing real functionality tests",
        "file": file_path,
        "function_name": name,
        "line_start": start,
        "line_end": end,
        "original": original_func,
        "injected": new_func,
    }

    return record


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python injector_missing_functionality_tests.py <path_to_test_file>")
        sys.exit(1)

    target = sys.argv[1]
    result = inject(target)

    print("\n── Injection Record ──")
    print(json.dumps(result, indent=2))
