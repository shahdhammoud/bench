import json
from pathlib import Path


def state_to_docs_json(state: dict) -> dict:
    """Convert LangGraph final state to parser-compatible JSON format."""
    modules = []
    for m in state.get("module_docs", []):
        modules.append({
            "name": m.get("name", ""),
            "purpose": m.get("purpose", ""),
            "interfaces": m.get("interfaces", []),
            "dependencies": m.get("dependencies", []),
            "tech_stack": m.get("tech_stack", []),
            "key_classes": m.get("key_classes", []),
            "key_functions": m.get("key_functions", []),
            "notes": m.get("notes", ""),
        })

    endpoints = []
    for e in state.get("endpoints", []):
        endpoints.append({
            "path": e.get("path", ""),
            "method": e.get("method", ""),
            "description": e.get("description", ""),
            "request_body": e.get("request_body", ""),
            "response": e.get("response", ""),
            "auth_required": e.get("auth_required", False),
        })

    return {
        "project_name": state.get("project_name", ""),
        "project_goal": state.get("project_goal", ""),
        "functional_requirements": state.get("functional_requirements", []),
        "non_functional_requirements": state.get("non_functional_requirements", []),
        "modules": modules,
        "api_endpoints": endpoints,
        "async_events": state.get("async_events", []),
        "guidelines": state.get("guidelines", []),
    }


def save_docs(state: dict, output_path: str) -> None:
    """Save the generated docs to a JSON file."""
    docs = state_to_docs_json(state)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(docs, f, indent=2, ensure_ascii=False)
    print(f"Saved documentation to {output_path}")
