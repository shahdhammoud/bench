import ast
import json
import sys
import re
from openai import OpenAI
from collections import Counter

# ── LLM client ────────────────────────────────────────────────────────────────
client = OpenAI(
    base_url="http://d.dgx:54000/v1",
    api_key="sk-litellm-token-hyper",
)
MODEL = "gpt-oss-120b"

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_functions(source: str):
    """Return a list of (name, lineno_start, lineno_end) for every function
    that has at least one return statement returning a non-None value."""
    tree = ast.parse(source)
    lines = source.splitlines()
    candidates = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # check it has a real return
        has_return = any(
            isinstance(n, ast.Return) and n.value is not None
            for n in ast.walk(node)
        )
        if not has_return:
            continue
        # get end line
        end = node.end_lineno if hasattr(node, "end_lineno") else node.lineno
        candidates.append((node.name, node.lineno, end))

    return candidates


def get_function_source(source: str, lineno_start: int, lineno_end: int) -> str:
    lines = source.splitlines()
    return "\n".join(lines[lineno_start - 1 : lineno_end])


def ask_llm(function_source: str) -> str:
    """Ask the LLM to replace the real return logic with a hardcoded fake value.
    Returns the modified function source as a string."""
    prompt = f"""You are a code mutation tool. Your job is to inject a subtle bug.

Given the following Python function, replace the real return logic with a hardcoded fake value.
Rules:
- Keep the function signature (name, parameters, decorators) exactly the same.
- Replace the body with minimal code that returns a hardcoded fake value of the correct type.
- The fake value should look plausible but be wrong (e.g. a fake email, a hardcoded 0, an empty list, a made-up string).
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
    """Strip markdown code fences if the LLM added them."""
    raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    return raw.strip()


def self_consistency(function_source: str, n: int = 3) -> str:
    """Call LLM n times and return the most common result."""
    responses = []
    for i in range(n):
        print(f"  LLM call {i+1}/{n}...")
        raw = ask_llm(function_source)
        cleaned = clean_code(raw)
        responses.append(cleaned)

    # most common response wins
    counter = Counter(responses)
    best = counter.most_common(1)[0][0]
    return best


def replace_function_in_source(source: str, lineno_start: int, lineno_end: int, new_func: str) -> str:
    """Replace lines lineno_start..lineno_end (1-indexed) with new_func."""
    lines = source.splitlines()
    before = lines[:lineno_start - 1]
    after = lines[lineno_end:]
    return "\n".join(before + new_func.splitlines() + after)


# ── Main ──────────────────────────────────────────────────────────────────────

def inject(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    candidates = extract_functions(source)
    if not candidates:
        raise ValueError(f"No injectable functions found in {file_path}")

    # pick the first candidate (can be randomized later)
    name, start, end = candidates[0]
    print(f"Injecting into function '{name}' (lines {start}-{end})")

    original_func = get_function_source(source, start, end)
    print("Running self-consistency (3 LLM calls)...")
    new_func = self_consistency(original_func, n=3)

    new_source = replace_function_in_source(source, start, end, new_func)

    # write modified file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_source)

    record = {
        "injector": "injector_fake_data",
        "problem_type": 8,
        "problem_type_name": "Fake data in implementation",
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
        print("Usage: python injector_fake_data.py <path_to_python_file>")
        sys.exit(1)

    target = sys.argv[1]
    result = inject(target)

    print("\n── Injection Record ──")
    print(json.dumps(result, indent=2))
