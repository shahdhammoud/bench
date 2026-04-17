from typing import Any, TypedDict
from langgraph.graph import StateGraph, END
from doc_generator.nodes import (
    inspect_files,
    identify_contracts,
    infer_requirements,
    generate_module_docs,
    run_critic,
    fix_docs,
)


class DocGenState(TypedDict):
    files: dict[str, str]
    client: Any
    model: str
    identified_modules: list
    endpoints: list
    async_events: list
    functional_requirements: list
    non_functional_requirements: list
    project_name: str
    project_goal: str
    module_docs: list
    critic_score: float
    critic_problems: list


def should_fix(state: DocGenState) -> str:
    if state.get("critic_score", 10) < 7:
        return "fix_docs"
    return END


def build_graph() -> StateGraph:
    graph = StateGraph(DocGenState)

    graph.add_node("inspect_files", inspect_files)
    graph.add_node("identify_contracts", identify_contracts)
    graph.add_node("infer_requirements", infer_requirements)
    graph.add_node("generate_module_docs", generate_module_docs)
    graph.add_node("run_critic", run_critic)
    graph.add_node("fix_docs", fix_docs)

    graph.set_entry_point("inspect_files")
    graph.add_edge("inspect_files", "identify_contracts")
    graph.add_edge("identify_contracts", "infer_requirements")
    graph.add_edge("infer_requirements", "generate_module_docs")
    graph.add_edge("generate_module_docs", "run_critic")
    graph.add_conditional_edges("run_critic", should_fix)
    graph.add_edge("fix_docs", END)

    return graph.compile()


def run_workflow(files: dict[str, str], client: Any, model: str) -> DocGenState:
    graph = build_graph()
    initial_state = DocGenState(
        files=files,
        client=client,
        model=model,
        identified_modules=[],
        endpoints=[],
        async_events=[],
        functional_requirements=[],
        non_functional_requirements=[],
        project_name="",
        project_goal="",
        module_docs=[],
        critic_score=10.0,
        critic_problems=[],
    )
    result = graph.invoke(initial_state)
    return result
