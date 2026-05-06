import json
import shutil
from pathlib import Path


def inject_project_structure(repo_path, source_file_relative):
    """
    Moves a Python file to the wrong location (project root) and
    updates its import in other files to reflect the wrong path.
    """
    repo = Path(repo_path)
    source_file = repo / source_file_relative
    records = []

    if not source_file.exists():
        return {"injected": False, "reason": "Source file not found"}

    filename = source_file.name
    wrong_location = repo / filename

    if wrong_location.exists():
        return {"injected": False, "reason": "File already exists at root level"}

    shutil.move(str(source_file), str(wrong_location))

    original_import = source_file_relative.replace("/", ".").replace(".py", "")
    wrong_import = filename.replace(".py", "")

    files_updated = []
    for py_file in repo.rglob("*.py"):
        if py_file == wrong_location:
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            if original_import in text:
                new_text = text.replace(original_import, wrong_import)
                py_file.write_text(new_text, encoding="utf-8")
                files_updated.append(str(py_file.relative_to(repo)))
        except Exception:
            continue

    records.append({
        "original_location": source_file_relative,
        "wrong_location": filename,
        "files_with_updated_imports": files_updated,
        "problem_type": 1,
        "problem_name": "project_structure_problem",
        "description": "Moved {} from {} to project root (wrong location)".format(
            filename, source_file_relative
        )
    })

    return {
        "injected": True,
        "repo_path": repo_path,
        "injections": records,
        "problem_type": 1,
        "problem_name": "project_structure_problem",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python injector_project_structure.py <repo_path> <file_relative_path>")
        print("Example: python injector_project_structure.py ./myrepo src/utils/helpers.py")
        sys.exit(1)
    result = inject_project_structure(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2))
