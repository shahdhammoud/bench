import re
import json
from pathlib import Path


def inject_test_duplication(repo_path, test_file_relative):
    repo = Path(repo_path)
    test_file = repo / test_file_relative
    records = []

    if not test_file.exists():
        return {"injected": False, "reason": "Test file not found"}

    source = test_file.read_text(encoding="utf-8", errors="ignore")
    lines = source.splitlines()

    pattern = re.compile(r"^def\s+(test_[a-zA-Z0-9_]+)\s*\(")
    test_functions = []
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            test_functions.append((i, match.group(1)))

    if not test_functions:
        return {"injected": False, "reason": "No test functions found in file"}

    duplicate_filename = test_file.stem + "_duplicate" + test_file.suffix
    duplicate_path = test_file.parent / duplicate_filename

    imports = "\n".join(
        line for line in lines
        if line.startswith("import ") or line.startswith("from ")
    )

    func_blocks = []
    for idx, (start, func_name) in enumerate(test_functions[:3]):
        end = start + 1
        base_indent = 0
        while end < len(lines):
            l = lines[end]
            if l.strip() == "":
                end += 1
                continue
            current_indent = len(l) - len(l.lstrip())
            if current_indent <= base_indent and end > start + 1:
                break
            end += 1
        func_blocks.append("\n".join(lines[start:end]))

    header = "# Duplicate test file - same tests copied from {}\n\n".format(test_file.name)
    duplicate_content = header + imports + "\n\n\n" + "\n\n\n".join(func_blocks)
    duplicate_path.write_text(duplicate_content, encoding="utf-8")

    records.append({
        "original_file": test_file_relative,
        "duplicate_file": str(duplicate_path.relative_to(repo)),
        "duplicated_functions": [f for _, f in test_functions[:3]],
        "problem_type": 9,
        "problem_name": "test_duplication",
        "description": "Copied {} test functions from {} into new file {}".format(
            len(test_functions[:3]), test_file.name, duplicate_filename
        )
    })

    return {
        "injected": True,
        "repo_path": repo_path,
        "injections": records,
        "problem_type": 9,
        "problem_name": "test_duplication",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python injector_test_duplication.py <repo_path> <test_file_relative>")
        sys.exit(1)
    result = inject_test_duplication(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
