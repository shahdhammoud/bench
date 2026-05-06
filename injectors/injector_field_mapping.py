import re
import json
from pathlib import Path

KEY_SUBSTITUTIONS = {
    "name": "label", "label": "name",
    "id": "key", "key": "id",
    "value": "val", "val": "value",
    "type": "kind", "kind": "type",
    "status": "state", "state": "status",
    "data": "payload", "payload": "data",
    "result": "response", "response": "result",
    "error": "exception", "exception": "error",
    "message": "msg", "msg": "message",
    "path": "filepath", "filepath": "path",
    "cosmology": "model", "model": "cosmology",
    "format": "encoding", "encoding": "format",
    "version": "revision", "revision": "version",
    "config": "settings", "settings": "config",
    "output": "result", "input": "source",
    "source": "input", "target": "destination",
    "mode": "method", "size": "length",
    "count": "total", "total": "count",
    "index": "position", "position": "index",
}


def inject_field_mapping(source_code):
    lines = source_code.splitlines()
    records = []
    modified_lines = lines.copy()

    patterns = [
        re.compile(r'(\w+\.get\(["\'\'])([a-z_]+)(["\'\'])'),
        re.compile(r'(\w+\[["\'\'])([a-z_]+)(["\'\']\])'),
    ]

    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                key = match.group(2)
                if key in KEY_SUBSTITUTIONS:
                    wrong_key = KEY_SUBSTITUTIONS[key]
                    original = line
                    modified_lines[i] = (
                        line[:match.start(2)] + wrong_key + line[match.end(2):]
                    )
                    records.append({
                        "line": i + 1,
                        "original": original.strip(),
                        "injected": modified_lines[i].strip(),
                        "problem_type": 5,
                        "problem_name": "field_mapping_mistake",
                        "description": "Replaced key \"{}\" with \"{}\" on line {}".format(key, wrong_key, i + 1)
                    })
                    return "\n".join(modified_lines), records

    return "\n".join(lines), records


def inject_into_file(filepath):
    source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    modified, records = inject_field_mapping(source)

    if not records:
        return {"injected": False, "reason": "No matching dictionary key access found"}

    return {
        "injected": True,
        "original_file": filepath,
        "modified_code": modified,
        "injections": records,
        "problem_type": 5,
        "problem_name": "field_mapping_mistake",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python injector_field_mapping.py <python_file>")
        sys.exit(1)
    result = inject_into_file(sys.argv[1])
    print(json.dumps(result, indent=2))
