import argparse
import json
import os
import sys
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from doc_generator.workflow import run_workflow
from doc_generator.serializer import save_docs

load_dotenv()


def load_files_from_dir(repo_path: str) -> dict[str, str]:
    """Load all Python files from a directory."""
    files = {}
    repo = Path(repo_path)
    for py_file in repo.rglob("*.py"):
        try:
            relative = str(py_file.relative_to(repo))
            files[relative] = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"Warning: could not read {py_file}: {e}")
    return files


def load_files_from_patch(patch_file: str) -> dict[str, str]:
    """Load files listed in a patch/diff file."""
    files = {}
    current_file = None
    lines = []

    with open(patch_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("+++ b/"):
                if current_file and lines:
                    files[current_file] = "".join(lines)
                current_file = line[6:].strip()
                lines = []
            elif current_file and line.startswith("+") and not line.startswith("+++"):
                lines.append(line[1:])

    if current_file and lines:
        files[current_file] = "".join(lines)

    return files


def load_files_from_json(files_json: str) -> dict[str, str]:
    """Load files from a JSON file mapping filename -> content."""
    with open(files_json, "r", encoding="utf-8") as f:
        return json.load(f)


def build_llm() -> tuple:
    """Build OpenAI client from environment variables."""
    host = os.getenv("GPT_OSS_HOST")
    key = os.getenv("GPT_OSS_KEY", "token-abc123")
    model = os.getenv("GPT_OSS_MODEL_NAME")

    if not host or not model:
        print("Error: GPT_OSS_HOST and GPT_OSS_MODEL_NAME must be set in .env")
        sys.exit(1)

    client = OpenAI(base_url=host, api_key=key)
    return client, model


def main():
    parser = argparse.ArgumentParser(
        description="Generate documentation for a Python codebase."
    )
    parser.add_argument("--repo_path", type=str, help="Path to the Python repository")
    parser.add_argument("--patch_file", type=str, help="Path to a git patch/diff file")
    parser.add_argument("--files_json", type=str, help="Path to a JSON file mapping filename to content")
    parser.add_argument("--output", type=str, default="output/docs.json", help="Output path for generated docs JSON")

    args = parser.parse_args()

    if not any([args.repo_path, args.patch_file, args.files_json]):
        print("Error: provide one of --repo_path, --patch_file, or --files_json")
        sys.exit(1)

    if args.repo_path:
        print(f"Loading files from directory: {args.repo_path}")
        files = load_files_from_dir(args.repo_path)
    elif args.patch_file:
        print(f"Loading files from patch: {args.patch_file}")
        files = load_files_from_patch(args.patch_file)
    else:
        print(f"Loading files from JSON: {args.files_json}")
        files = load_files_from_json(args.files_json)

    if not files:
        print("Error: no Python files found.")
        sys.exit(1)

    print(f"Loaded {len(files)} files.")

    client, model = build_llm()
    print(f"Using model: {model}")

    print("Running documentation generation workflow...")
    result = run_workflow(files, client, model)

    score = result.get("critic_score", "N/A")
    print(f"Critic score: {score}")

    save_docs(result, args.output)
    print("Done!")


if __name__ == "__main__":
    main()
