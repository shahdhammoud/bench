import re
import json
from pathlib import Path

FIELD_SUBSTITUTIONS = {
    "name": "title",
    "title": "name",
    "id": "uid",
    "uid": "id",
    "value": "data",
    "data": "value",
    "status": "state",
    "state": "status",
    "type": "kind",
    "kind": "type",
    "email": "username",
    "username": "email",
    "path": "url",
    "url": "path",
    "message": "text",
    "text": "message",
    "result": "output",
    "output": "result",
}


def inject_wrong_field_access(source_code: str) -> tuple[str, list[dict]]:
    lines = source_code.splitlines()
    records = []
    modified_lines = lines.copy()

    pattern = re.compile(r"(\bself\.|\b[a-z_][a-z0-9_]*\.)([a-z_][a-z0-9_]*)\b")

    for i, line in enumerate(lines):
        if line.strip().startswith("#") or line.strip().startswith('"""') or line.strip().startswith("'''"):
            continue
        match = pattern.search(line)
        if match:
            field = match.group(2)
            if field in FIELD_SUBSTITUTIONS:
                wrong_field = FIELD_SUBSTITUTIONS[field]
                original = line
                modified_lines[i] = line[:match.start(2)] + wrong_field + line[match.end(2):]
                records.append({
                    "line": i + 1,
                    "original": original.strip(),
                    "injected": modified_lines[i].strip(),
                    "problem_type": 6,
                    "problem_name": "wrong_field_access",
                    "description": f"Replaced field .{field} with .{wrong_field} on line {i + 1}"
                })
                break

    return "\n".join(modified_lines), records


def inject_into_file(filepath: str) -> dict:
    source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    modified, records = inject_wrong_field_access(source)

    if not records:
        return {"injected": False, "reason": "No matching field access found"}

    return {
        "injected": True,
        "original_file": filepath,
        "modified_code": modified,
        "injections": records,
        "problem_type": 6,
        "problem_name": "wrong_field_access",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python injector_wrong_field_access.py <python_file>")
        sys.exit(1)
    result = inject_into_file(sys.argv[1])
    print(json.dumps(result, indent=2))
