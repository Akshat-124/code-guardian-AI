from langgraph.graph import StateGraph, END
from app.agents.nodes import (
    AgentState,
    security_agent_node,
    quality_agent_node,
    test_agent_node,
    doc_agent_node,
    supervisor_agent_node
)

def initialize_node(state: AgentState) -> dict:
    """Helper entry node to fan out execution."""
    print("[Initializer] Initializing CodeGuardian AI Graph review pipeline...")
    return {}

# 1. Initialize StateGraph
workflow = StateGraph(AgentState)

# 2. Add nodes
workflow.add_node("initializer", initialize_node)
workflow.add_node("security", security_agent_node)
workflow.add_node("quality", quality_agent_node)
workflow.add_node("test", test_agent_node)
workflow.add_node("doc", doc_agent_node)
workflow.add_node("supervisor", supervisor_agent_node)

# 3. Add Edges (Fan-Out from Initializer)
workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "security")
workflow.add_edge("initializer", "quality")
workflow.add_edge("initializer", "test")
workflow.add_edge("initializer", "doc")

# 4. Fan-In to Supervisor
workflow.add_edge("security", "supervisor")
workflow.add_edge("quality", "supervisor")
workflow.add_edge("test", "supervisor")
workflow.add_edge("doc", "supervisor")

# 5. Complete Execution
workflow.add_edge("supervisor", END)

# 6. Compile Graph
agent_graph = workflow.compile()
