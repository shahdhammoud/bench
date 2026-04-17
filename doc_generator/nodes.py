import json
import os
from typing import Any
from openai import OpenAI
from doc_generator.prompts import (
    INSPECT_FILES_PROMPT,
    IDENTIFY_CONTRACTS_PROMPT,
    INFER_REQUIREMENTS_PROMPT,
    MODULE_DOC_PROMPT,
    CRITIC_PROMPT,
    FIX_DOCS_PROMPT,
)


def _call_llm(client: OpenAI, model: str, prompt: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()


def _parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def _format_file_contents(files: dict[str, str]) -> str:
    parts = []
    for filename, code in files.items():
        parts.append(f"=== {filename} ===\n{code}")
    return "\n\n".join(parts)


def inspect_files(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    file_list = "\n".join(files.keys())
    prompt = INSPECT_FILES_PROMPT.format(file_list=file_list)
    response = _call_llm(client, model, prompt)

    try:
        parsed = _parse_json(response)
        modules = parsed.get("modules", [])
    except Exception:
        modules = []

    return {**state, "identified_modules": modules}


def identify_contracts(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    code = _format_file_contents(files)
    prompt = IDENTIFY_CONTRACTS_PROMPT.format(code=code[:8000])
    response = _call_llm(client, model, prompt)

    try:
        parsed = _parse_json(response)
        endpoints = parsed.get("endpoints", [])
        async_events = parsed.get("async_events", [])
    except Exception:
        endpoints = []
        async_events = []

    return {**state, "endpoints": endpoints, "async_events": async_events}


def infer_requirements(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    code_summary = _format_file_contents(files)
    prompt = INFER_REQUIREMENTS_PROMPT.format(code_summary=code_summary[:8000])
    response = _call_llm(client, model, prompt)

    try:
        parsed = _parse_json(response)
        functional = parsed.get("functional_requirements", [])
        non_functional = parsed.get("non_functional_requirements", [])
        project_name = parsed.get("project_name", "Unknown Project")
        project_goal = parsed.get("project_goal", "")
    except Exception:
        functional = []
        non_functional = []
        project_name = "Unknown Project"
        project_goal = ""

    return {
        **state,
        "functional_requirements": functional,
        "non_functional_requirements": non_functional,
        "project_name": project_name,
        "project_goal": project_goal,
    }


def generate_module_docs(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]
    identified_modules = state.get("identified_modules", [])

    module_docs = []
    for module in identified_modules:
        module_name = module.get("name", "Unknown")
        module_files = module.get("files", [])
        code_parts = {}
        for fname in module_files:
            if fname in files:
                code_parts[fname] = files[fname]
        if not code_parts:
            code_parts = files

        code = _format_file_contents(code_parts)
        prompt = MODULE_DOC_PROMPT.format(module_name=module_name, code=code[:6000])
        response = _call_llm(client, model, prompt)

        try:
            parsed = _parse_json(response)
            parsed["name"] = module_name
            module_docs.append(parsed)
        except Exception:
            module_docs.append({"name": module_name, "purpose": "Could not parse documentation."})

    return {**state, "module_docs": module_docs}


def run_critic(state: dict) -> dict:
    client = state["client"]
    model = state["model"]

    docs_summary = json.dumps({
        "project_name": state.get("project_name"),
        "project_goal": state.get("project_goal"),
        "functional_requirements": state.get("functional_requirements"),
        "modules": state.get("module_docs"),
        "endpoints": state.get("endpoints"),
    }, indent=2)

    prompt = CRITIC_PROMPT.format(docs=docs_summary[:8000])
    response = _call_llm(client, model, prompt)

    try:
        parsed = _parse_json(response)
        score = parsed.get("score", 5)
        problems = parsed.get("problems", [])
    except Exception:
        score = 5
        problems = ["Could not parse critic response."]

    return {**state, "critic_score": score, "critic_problems": problems}


def fix_docs(state: dict) -> dict:
    client = state["client"]
    model = state["model"]
    problems = state.get("critic_problems", [])

    docs_summary = json.dumps({
        "project_name": state.get("project_name"),
        "project_goal": state.get("project_goal"),
        "functional_requirements": state.get("functional_requirements"),
        "non_functional_requirements": state.get("non_functional_requirements"),
        "modules": state.get("module_docs"),
        "endpoints": state.get("endpoints"),
        "async_events": state.get("async_events"),
    }, indent=2)

    prompt = FIX_DOCS_PROMPT.format(
        problems="\n".join(f"- {p}" for p in problems),
        docs=docs_summary[:8000],
    )
    response = _call_llm(client, model, prompt)

    try:
        parsed = _parse_json(response)
        return {
            **state,
            "project_name": parsed.get("project_name", state.get("project_name")),
            "project_goal": parsed.get("project_goal", state.get("project_goal")),
            "functional_requirements": parsed.get("functional_requirements", state.get("functional_requirements")),
            "non_functional_requirements": parsed.get("non_functional_requirements", state.get("non_functional_requirements")),
            "module_docs": parsed.get("modules", state.get("module_docs")),
            "endpoints": parsed.get("endpoints", state.get("endpoints")),
            "async_events": parsed.get("async_events", state.get("async_events")),
        }
    except Exception:
        return state
