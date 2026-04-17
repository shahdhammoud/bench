import json
import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def parse_specs(specs_path: str) -> dict:
    """Parse specs.md into project name, goal, and requirements."""
    result = {
        "project_name": "",
        "project_goal": "",
        "functional_requirements": [],
        "non_functional_requirements": [],
    }
    if not os.path.exists(specs_path):
        return result

    text = Path(specs_path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    current_section = None
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("# "):
            result["project_name"] = stripped[2:].strip()
        elif "goal" in lower and lower.startswith("#"):
            current_section = "goal"
        elif "functional requirement" in lower and "non" not in lower:
            current_section = "functional"
        elif "non-functional" in lower or "nonfunctional" in lower:
            current_section = "non_functional"
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:].strip()
            if current_section == "functional":
                result["functional_requirements"].append(item)
            elif current_section == "non_functional":
                result["non_functional_requirements"].append(item)
        elif current_section == "goal" and stripped and not stripped.startswith("#"):
            if not result["project_goal"]:
                result["project_goal"] = stripped

    return result


def parse_modules_description(modules_desc_path: str) -> list:
    """Parse modules_description.md into a list of module summaries."""
    modules = []
    if not os.path.exists(modules_desc_path):
        return modules

    text = Path(modules_desc_path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    current_module = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_module:
                modules.append(current_module)
            current_module = {"name": stripped[3:].strip(), "description": ""}
        elif current_module and stripped and not stripped.startswith("#"):
            if not current_module["description"]:
                current_module["description"] = stripped

    if current_module:
        modules.append(current_module)

    return modules


def parse_module_file(module_path: str) -> dict:
    """Parse a single module .md file into structured data."""
    result = {
        "name": "",
        "purpose": "",
        "interfaces": [],
        "dependencies": [],
        "tech_stack": [],
        "key_classes": [],
        "key_functions": [],
        "notes": "",
    }
    if not os.path.exists(module_path):
        return result

    text = Path(module_path).read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    result["name"] = Path(module_path).stem
    current_section = None

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if lower.startswith("# "):
            result["name"] = stripped[2:].strip()
        elif "purpose" in lower and stripped.startswith("#"):
            current_section = "purpose"
        elif "interface" in lower and stripped.startswith("#"):
            current_section = "interfaces"
        elif "dependenc" in lower and stripped.startswith("#"):
            current_section = "dependencies"
        elif "tech" in lower and stripped.startswith("#"):
            current_section = "tech_stack"
        elif "class" in lower and stripped.startswith("#"):
            current_section = "key_classes"
        elif "function" in lower and stripped.startswith("#"):
            current_section = "key_functions"
        elif "note" in lower and stripped.startswith("#"):
            current_section = "notes"
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:].strip()
            if current_section == "interfaces":
                result["interfaces"].append(item)
            elif current_section == "dependencies":
                result["dependencies"].append(item)
            elif current_section == "tech_stack":
                result["tech_stack"].append(item)
            elif current_section == "key_classes":
                result["key_classes"].append(item)
            elif current_section == "key_functions":
                result["key_functions"].append(item)
        elif current_section == "purpose" and stripped and not stripped.startswith("#"):
            if not result["purpose"]:
                result["purpose"] = stripped
        elif current_section == "notes" and stripped and not stripped.startswith("#"):
            result["notes"] += stripped + " "

    result["notes"] = result["notes"].strip()
    return result


def parse_openapi(openapi_path: str) -> list:
    """Parse openapi_spec.yaml into a list of endpoints."""
    endpoints = []
    if not os.path.exists(openapi_path) or yaml is None:
        return endpoints

    try:
        with open(openapi_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except Exception:
        return endpoints

    paths = spec.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ("get", "post", "put", "delete", "patch"):
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "description": details.get("summary", details.get("description", "")),
                    "auth_required": "security" in details,
                })

    return endpoints


def parse_asyncapi(asyncapi_path: str) -> list:
    """Parse asyncapi_spec.yaml into a list of async events."""
    events = []
    if not os.path.exists(asyncapi_path) or yaml is None:
        return events

    try:
        with open(asyncapi_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except Exception:
        return events

    channels = spec.get("channels", {})
    for channel, details in channels.items():
        desc = ""
        if isinstance(details, dict):
            desc = details.get("description", "")
        events.append(f"{channel}: {desc}".strip(": "))

    return events


def parse_socketio_docs(socketio_path: str) -> list:
    """Parse socketio_protocol_docs.md into a list of events."""
    events = []
    if not os.path.exists(socketio_path):
        return events

    text = Path(socketio_path).read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            events.append(stripped[2:].strip())
        elif stripped.startswith("`") and "`" in stripped[1:]:
            event = stripped.strip("`").split("`")[0]
            if event:
                events.append(event)

    return events


def parse_guidelines(guidelines_path: str) -> list:
    """Parse agentic_coding_best_practices.md into a list of guidelines."""
    guidelines = []
    if not os.path.exists(guidelines_path):
        return guidelines

    text = Path(guidelines_path).read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            guidelines.append(stripped[2:].strip())

    return guidelines


def parse_docs(docs_dir: str) -> dict:
    """Main function: parse all documentation files from a directory into structured JSON."""
    base = Path(docs_dir)

    specs = parse_specs(str(base / "specs.md"))
    modules_overview = parse_modules_description(str(base / "modules_description.md"))

    modules_dir = base / "modules"
    module_details = []
    if modules_dir.exists():
        for md_file in sorted(modules_dir.glob("*.md")):
            module_details.append(parse_module_file(str(md_file)))

    endpoints = parse_openapi(str(base / "openapi_spec.yaml"))
    async_events = parse_asyncapi(str(base / "asyncapi_spec.yaml"))
    socketio_events = parse_socketio_docs(str(base / "socketio_protocol_docs.md"))
    guidelines = parse_guidelines(str(base / "agentic_coding_best_practices.md"))

    all_async_events = async_events + socketio_events

    return {
        "project_name": specs["project_name"],
        "project_goal": specs["project_goal"],
        "functional_requirements": specs["functional_requirements"],
        "non_functional_requirements": specs["non_functional_requirements"],
        "modules_overview": modules_overview,
        "modules": module_details,
        "api_endpoints": endpoints,
        "async_events": all_async_events,
        "guidelines": guidelines,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python parser.py <docs_directory>")
        sys.exit(1)
    result = parse_docs(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
