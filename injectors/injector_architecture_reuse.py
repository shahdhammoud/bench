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


client = OpenAI(
    base_url=os.getenv('LLM_BASE_URL'),
    api_key=os.getenv('LLM_API_KEY'),
)
MODEL = "gpt-oss-120b"

def extract_imports(source: str):
    """Return list of (module, name, lineno) for all from-imports."""
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module is None:
            continue
        for alias in node.names:
            imports.append((node.module, alias.name, node.lineno))
    return imports

def get_function_source(source: str, lineno_start: int, lineno_end: int) -> str:
    lines = source.splitlines()
    return "\n".join(lines[lineno_start - 1 : lineno_end])

def ask_llm(source: str, module: str, name: str) -> str:
    prompt = f"""You are a code mutation tool. Your job is to inject a subtle architecture bug.

Given the following Python file, find the import of {name} from {module} and:
1. Remove that import line.
2. Add a copy of the {name} class or function definition directly into this file (before its first use), instead of importing it.
   - The copied definition should be a plausible but slightly simplified or subtly wrong version.
   - It should look like someone copy-pasted the class instead of importing it from the shared location.

Rules:
- Keep everything else exactly the same.
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

def self_consistency(source: str, module: str, name: str, n: int = 3) -> str:
    responses = []
    for i in range(n):
        print(f"  LLM call {i+1}/{n}...")
        raw = ask_llm(source, module, name)
        cleaned = clean_code(raw)
        responses.append(cleaned)
    counter = Counter(responses)
    return counter.most_common(1)[0][0]

def inject(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    imports = extract_imports(source)
    if not imports:
        raise ValueError(f"No from-imports found in {file_path}")

    module, name, lineno = imports[0]
    print(f"Injecting: replacing import of '{name}' from '{module}' with inline copy")

    print("Running self-consistency (3 LLM calls)...")
    new_source = self_consistency(source, module, name, n=3)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_source)

    record = {
        "injector": "injector_architecture_reuse",
        "problem_type": 2,
        "problem_type_name": "Architecture / model reuse",
        "file": file_path,
        "imported_name": name,
        "imported_from": module,
        "import_lineno": lineno,
        "original_first_100_chars": source[:100],
        "injected_first_100_chars": new_source[:100],
    }
    return record

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python injector_architecture_reuse.py <path_to_python_file>")
        sys.exit(1)
    result = inject(sys.argv[1])
    print("\n── Injection Record ──")
    print(json.dumps(result, indent=2))
