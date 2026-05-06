import re
import json
from pathlib import Path


def inject_forbidden_mocking(source_code, module_to_mock=None):
    lines = source_code.splitlines()
    records = []
    modified_lines = lines.copy()

    import_pattern = re.compile(r"^from\s+([\w.]+)\s+import\s+([\w,\s]+)")
    imported_targets = []
    for line in lines:
        match = import_pattern.match(line)
        if match:
            module = match.group(1)
            names = [n.strip() for n in match.group(2).split(",")]
            for name in names:
                if name and not name.startswith("_"):
                    imported_targets.append("{}.{}".format(module, name))

    if not imported_targets and not module_to_mock:
        target = "builtins.open"
    else:
        target = module_to_mock or imported_targets[0]

    test_pattern = re.compile(r"^(\s*)(def\s+test_[a-zA-Z0-9_]+\s*\()([^)]*)\)\s*:")
    for i, line in enumerate(lines):
        match = test_pattern.match(line)
        if match:
            indent = match.group(1)
            params = match.group(3).strip()

            mock_decorator = "{}@unittest.mock.patch(\'{}\')".format(indent, target)

            if "import unittest" not in source_code:
                modified_lines.insert(0, "import unittest.mock")
                i += 1

            modified_lines.insert(i, mock_decorator)

            if params:
                new_params = params + ", mock_target"
            else:
                new_params = "mock_target"

            modified_lines[i + 1] = re.sub(
                r"def\s+(test_[a-zA-Z0-9_]+)\s*\([^)]*\)",
                lambda m: "def {}({})".format(m.group(1), new_params),
                modified_lines[i + 1]
            )

            records.append({
                "line": i + 1,
                "mocked_target": target,
                "original": line.strip(),
                "injected": mock_decorator.strip(),
                "problem_type": 10,
                "problem_name": "forbidden_mocking",
                "description": "Added forbidden mock of {} in test on line {}".format(
                    target, i + 1
                )
            })
            break

    return "\n".join(modified_lines), records


def inject_into_file(filepath):
    source = Path(filepath).read_text(encoding="utf-8", errors="ignore")
    modified, records = inject_forbidden_mocking(source)

    if not records:
        return {"injected": False, "reason": "No test functions found"}

    return {
        "injected": True,
        "original_file": filepath,
        "modified_code": modified,
        "injections": records,
        "problem_type": 10,
        "problem_name": "forbidden_mocking",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python injector_forbidden_mocking.py <python_file>")
        sys.exit(1)
    result = inject_into_file(sys.argv[1])
    print(json.dumps(result, indent=2))
