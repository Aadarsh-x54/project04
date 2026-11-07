from typing import Literal, Dict, Any, Callable

try:
    from langgraph.graph import StateGraph, START, END

    LANGGRAPH_ENGINE = "langgraph.graph.StateGraph"
except ImportError:
    START = "__start__"
    END = "__end__"
    LANGGRAPH_ENGINE = "langgraph_compatible_state_graph"

    class CompiledStateGraph:
        def __init__(self, nodes: Dict[str, Callable], edges: Dict[str, str], conditional_edges: Dict[str, Any]):
            self.nodes = nodes
            self.edges = edges
            self.conditional_edges = conditional_edges

        def invoke(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
            state = dict(initial_state)
            current = self.edges.get(START)
            steps = 0
            max_steps = 50
            while current and current != END and steps < max_steps:
                steps += 1
                node_fn = self.nodes[current]
                updates = node_fn(state)
                if isinstance(updates, dict):
                    state.update(updates)
                if current in self.conditional_edges:
                    router_fn, route_map = self.conditional_edges[current]
                    route_key = router_fn(state)
                    current = route_map.get(route_key, route_key)
                else:
                    current = self.edges.get(current, END)
            return state

    class StateGraph:  # type: ignore[no-redef]
        def __init__(self, _state_schema: Any):
            self.nodes: Dict[str, Callable] = {}
            self.edges: Dict[str, str] = {}
            self.conditional_edges: Dict[str, Any] = {}

        def add_node(self, name: str, fn: Callable) -> None:
            self.nodes[name] = fn

        def add_edge(self, src: str, dst: str) -> None:
            self.edges[src] = dst

        def add_conditional_edges(self, src: str, router_fn: Callable, route_map: Dict[str, str]) -> None:
            self.conditional_edges[src] = (router_fn, route_map)

        def compile(self) -> CompiledStateGraph:
            return CompiledStateGraph(self.nodes, self.edges, self.conditional_edges)


from app.agents.state import SWEAgentState
from app.agents.nodes import (
    code_understanding_node,
    debugging_node,
    code_generation_node,
    testing_node,
    code_review_node,
)


def should_retry_or_review(
    state: SWEAgentState,
) -> Literal["code_generation_agent", "code_review_agent"]:
    """
    Conditional edge implementing the self-healing test loop:
    If pytest failed and we have remaining iterations, route back to `code_generation_agent`
    so it can inspect the failure output, refine its proposed patch, and re-run tests.
    """
    passed = bool(state.get("tests_passed", False))
    iteration = int(state.get("iteration", 1))
    max_iterations = int(state.get("max_iterations", 3))

    if not passed and iteration < max_iterations:
        return "code_generation_agent"
    return "code_review_agent"


def build_swe_agent_graph():
    """Build and compile the 5-agent LangGraph StateGraph workflow."""
    workflow = StateGraph(SWEAgentState)

    # Register the 5 specialized agents
    workflow.add_node("code_understanding_agent", code_understanding_node)
    workflow.add_node("debugging_agent", debugging_node)
    workflow.add_node("code_generation_agent", code_generation_node)
    workflow.add_node("testing_agent", testing_node)
    workflow.add_node("code_review_agent", code_review_node)

    # Sequential & Self-healing edges
    workflow.add_edge(START, "code_understanding_agent")
    workflow.add_edge("code_understanding_agent", "debugging_agent")
    workflow.add_edge("debugging_agent", "code_generation_agent")
    workflow.add_edge("code_generation_agent", "testing_agent")

    # Conditional Self-Healing Loop: Testing Agent -> Code Generation Agent OR Code Review Agent
    workflow.add_conditional_edges(
        "testing_agent",
        should_retry_or_review,
        {
            "code_generation_agent": "code_generation_agent",
            "code_review_agent": "code_review_agent",
        },
    )

    workflow.add_edge("code_review_agent", END)

    return workflow.compile()


swe_agent_graph = build_swe_agent_graph()
