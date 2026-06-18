import json
from typing import Any
from openai import OpenAI
from langchain_core.output_parsers import PydanticOutputParser
from doc_generator.models import (
    InspectFilesOutput,
    IdentifyContractsOutput,
    InferRequirementsOutput,
    ModuleDocOutput,
    CriticOutput,
    GeneratedDocs,
)
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


def _format_file_contents(files: dict[str, str]) -> str:
    parts = []
    for filename, code in files.items():
        parts.append(f"=== {filename} ===\n{code}")
    return "\n\n".join(parts)


def inspect_files(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    parser = PydanticOutputParser(pydantic_object=InspectFilesOutput)
    file_list = "\n".join(files.keys())
    prompt = INSPECT_FILES_PROMPT.format(
        file_list=file_list,
        format_instructions=parser.get_format_instructions(),
    )
    response = _call_llm(client, model, prompt)

    try:
        parsed = parser.parse(response)
        modules = parsed.modules
    except Exception as e:
        print(f"Warning: inspect_files parse error: {e}")
        modules = []

    return {**state, "identified_modules": modules}


def identify_contracts(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    parser = PydanticOutputParser(pydantic_object=IdentifyContractsOutput)
    code = _format_file_contents(files)
    prompt = IDENTIFY_CONTRACTS_PROMPT.format(
        code=code[:8000],
        format_instructions=parser.get_format_instructions(),
    )
    response = _call_llm(client, model, prompt)

    try:
        parsed = parser.parse(response)
        endpoints = parsed.endpoints
        async_events = parsed.async_events
    except Exception as e:
        print(f"Warning: identify_contracts parse error: {e}")
        endpoints = []
        async_events = []

    return {**state, "endpoints": endpoints, "async_events": async_events}


def infer_requirements(state: dict) -> dict:
    files = state["files"]
    client = state["client"]
    model = state["model"]

    parser = PydanticOutputParser(pydantic_object=InferRequirementsOutput)
    code_summary = _format_file_contents(files)
    prompt = INFER_REQUIREMENTS_PROMPT.format(
        code_summary=code_summary[:8000],
        format_instructions=parser.get_format_instructions(),
    )
    response = _call_llm(client, model, prompt)

    try:
        parsed = parser.parse(response)
        functional = parsed.functional_requirements
        non_functional = parsed.non_functional_requirements
        project_name = parsed.project_name
        project_goal = parsed.project_goal
    except Exception as e:
        print(f"Warning: infer_requirements parse error: {e}")
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

    parser = PydanticOutputParser(pydantic_object=ModuleDocOutput)
    module_docs = []

    for module in identified_modules:
        module_name = module.get("name", "Unknown") if isinstance(module, dict) else str(module)
        module_files = module.get("files", []) if isinstance(module, dict) else []
        code_parts = {f: files[f] for f in module_files if f in files} or files

        code = _format_file_contents(code_parts)
        prompt = MODULE_DOC_PROMPT.format(
            module_name=module_name,
            code=code[:6000],
            format_instructions=parser.get_format_instructions(),
        )
        response = _call_llm(client, model, prompt)

        try:
            parsed = parser.parse(response)
            doc = parsed.model_dump()
            doc["name"] = module_name
            module_docs.append(doc)
        except Exception as e:
            print(f"Warning: generate_module_docs parse error for {module_name}: {e}")
            module_docs.append({"name": module_name, "purpose": "Could not parse documentation."})

    return {**state, "module_docs": module_docs}


def run_critic(state: dict) -> dict:
    client = state["client"]
    model = state["model"]

    parser = PydanticOutputParser(pydantic_object=CriticOutput)
    docs_summary = json.dumps({
        "project_name": state.get("project_name"),
        "project_goal": state.get("project_goal"),
        "functional_requirements": state.get("functional_requirements"),
        "modules": state.get("module_docs"),
        "endpoints": state.get("endpoints"),
    }, indent=2)

    prompt = CRITIC_PROMPT.format(
        docs=docs_summary[:8000],
        format_instructions=parser.get_format_instructions(),
    )
    response = _call_llm(client, model, prompt)

    try:
        parsed = parser.parse(response)
        score = parsed.score
        problems = parsed.problems
    except Exception as e:
        print(f"Warning: run_critic parse error: {e}")
        score = 5
        problems = ["Could not parse critic response."]

    return {**state, "critic_score": score, "critic_problems": problems}


def fix_docs(state: dict) -> dict:
    client = state["client"]
    model = state["model"]
    problems = state.get("critic_problems", [])

    parser = PydanticOutputParser(pydantic_object=GeneratedDocs)
    docs_summary = json.dumps({
        "project_name": state.get("project_name"),
        "project_goal": state.get("project_goal"),
        "functional_requirements": state.get("functional_requirements"),
        "non_functional_requirements": state.get("non_functional_requirements"),
        "modules": state.get("module_docs"),
        "endpoints": state.get("endpoints"),
        "async_events": state.get("async_events"),
    }, indent=2)
    source_code = "\n".join(f"{fname}:\n{code}" for fname, code in state.get("files", {}).items())

    prompt = FIX_DOCS_PROMPT.format(
        problems="\n".join(f"- {p}" for p in problems),
        docs=docs_summary[:6000],
        source_code=source_code[:4000],
        format_instructions=parser.get_format_instructions(),
    )
    response = _call_llm(client, model, prompt)

    try:
        fixed = parser.parse(response)
        return {
            **state,
            "project_name": fixed.project_name,
            "project_goal": fixed.project_goal,
            "functional_requirements": fixed.functional_requirements,
            "non_functional_requirements": fixed.non_functional_requirements,
            "module_docs": [m.model_dump() for m in fixed.modules],
            "endpoints": [e.model_dump() for e in fixed.api_endpoints],
            "async_events": fixed.async_events,
            "fix_iteration": state.get("fix_iteration", 0) + 1,
        }
    except Exception as e:
        print(f"Warning: fix_docs parse error: {e}")
        return {**state, "fix_iteration": state.get("fix_iteration", 0) + 1}
