import re
import json
from pathlib import Path


def inject_broad_exception(source_code: str) -> tuple[str, list[dict]]:
    lines = source_code.splitlines()
    records = []
    modified_lines = lines.copy()

    pattern = re.compile(r"^(\s*)except\s+([A-Z][a-zA-Z0-9_]+(\s*,\s*[A-Z][a-zA-Z0-9_]+)*)\s*:")

    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            indent = match.group(1)
            modified_lines[i] = f"{indent}except Exception:"
            records.append({
                "line": i + 1,
                "original": line.strip(),
                "injected": f"{indent}except Exception:".strip(),
                "problem_type": 7,
                "problem_name": "broad_exception_handling",
                "description": f"Replaced specific exception handler with broad Exception on line {i + 1}"
            })

    return "\n".join(modified_lines), records


def inject_into_file(filepath: str) -> dict:
    source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    modified, records = inject_broad_exception(source)

    if not records:
        return {"injected": False, "reason": "No specific exception handlers found"}

    return {
        "injected": True,
        "original_file": filepath,
        "modified_code": modified,
        "injections": records,
        "problem_type": 7,
        "problem_name": "broad_exception_handling",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python injector_broad_exception.py <python_file>")
        sys.exit(1)
    result = inject_into_file(sys.argv[1])
    print(json.dumps(result, indent=2))
