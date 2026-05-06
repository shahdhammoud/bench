import re
import json
from pathlib import Path


def inject_interface_mismatch(source_code):
    lines = source_code.splitlines()
    records = []
    modified_lines = lines.copy()

    pattern = re.compile(r"^(\s*def\s+)([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)\s*->\s*([^\s:][^:]*?)\s*:")

    TYPE_SUBSTITUTIONS = {
        "str": "int",
        "int": "str",
        "bool": "str",
        "float": "int",
        "list": "dict",
        "dict": "list",
        "None": "str",
        "bytes": "str",
        "Optional[str]": "Optional[int]",
        "Optional[int]": "Optional[str]",
        "List[str]": "List[int]",
        "List[int]": "List[str]",
    }

    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            func_name = match.group(2)
            if func_name.startswith("__"):
                continue
            return_type = match.group(4).strip()
            if return_type in TYPE_SUBSTITUTIONS:
                wrong_type = TYPE_SUBSTITUTIONS[return_type]
                original = line
                modified_lines[i] = line.replace(
                    "-> " + return_type + ":",
                    "-> " + wrong_type + ":"
                )
                records.append({
                    "line": i + 1,
                    "original": original.strip(),
                    "injected": modified_lines[i].strip(),
                    "problem_type": 3,
                    "problem_name": "interface_signature_mismatch",
                    "description": "Changed return type of {} from {} to {} on line {}".format(
                        func_name, return_type, wrong_type, i + 1
                    )
                })
                break

    return "\n".join(modified_lines), records


def inject_into_file(filepath):
    source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    modified, records = inject_interface_mismatch(source)

    if not records:
        return {"injected": False, "reason": "No suitable return type annotation found"}

    return {
        "injected": True,
        "original_file": filepath,
        "modified_code": modified,
        "injections": records,
        "problem_type": 3,
        "problem_name": "interface_signature_mismatch",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python injector_interface_mismatch.py <python_file>")
        sys.exit(1)
    result = inject_into_file(sys.argv[1])
    print(json.dumps(result, indent=2))
