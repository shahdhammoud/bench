import ast
import json
import sys
import re
from openai import OpenAI
from collections import Counter

client = OpenAI(
    base_url="http://10.32.2.11:54000/v1",
    api_key="sk-litellm-token-hyper",
)
MODEL = "gpt-oss-120b"


def find_pydantic_usage(source: str):
    """Find lines where a class that looks like a Pydantic model is instantiated."""
    tree = ast.parse(source)
    usages = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        # Look for calls like MyModel(...) where name starts with uppercase
        if isinstance(func, ast.Name) and func.id[0].isupper():
            usages.append((func.id, node.lineno))
        elif isinstance(func, ast.Attribute) and func.attr[0].isupper():
            usages.append((func.attr, node.lineno))
    return usages


def ask_llm(source: str, model_name: str, lineno: int) -> str:
    prompt = f"""You are a code mutation tool. Your job is to inject a subtle data model bug.

Given the following Python file, find the instantiation of {model_name} near line {lineno}.
Replace that instantiation with a plain Python dictionary that:
1. Uses wrong or missing field names (e.g. rename a field, drop a required field, or add a wrong one)
2. Uses wrong values for at least one field (e.g. wrong type, None instead of a real value)
3. Removes the Pydantic model entirely — no import, no class, just a plain dict

Rules:
- Keep everything else in the file exactly the same.
- The change should look like a plausible mistake a developer might make.
- Do NOT add any explanation or comments.
- Return ONLY the complete modified file content, nothing else.

File:
{source}
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


def self_consistency(source: str, model_name: str, lineno: int, n: int = 3) -> str:
    responses = []
    for i in range(n):
        print(f"  LLM call {i+1}/{n}...")
        raw = ask_llm(source, model_name, lineno)
        cleaned = clean_code(raw)
        responses.append(cleaned)
    counter = Counter(responses)
    return counter.most_common(1)[0][0]


def inject(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    usages = find_pydantic_usage(source)
    if not usages:
        raise ValueError(f"No Pydantic-style model instantiation found in {file_path}")

    model_name, lineno = usages[0]
    print(f"Injecting: replacing {model_name}(...) on line {lineno} with plain dict")
    print("Running self-consistency (3 LLM calls)...")

    new_source = self_consistency(source, model_name, lineno, n=3)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_source)

    record = {
        "injector": "injector_data_model",
        "problem_type": 4,
        "problem_type_name": "Data model implementation",
        "file": file_path,
        "model_name": model_name,
        "lineno": lineno,
        "original_first_100_chars": source[:100],
        "injected_first_100_chars": new_source[:100],
    }
    return record


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python injector_data_model.py <path_to_python_file>")
        sys.exit(1)
    result = inject(sys.argv[1])
    print("\n── Injection Record ──")
    print(json.dumps(result, indent=2))
