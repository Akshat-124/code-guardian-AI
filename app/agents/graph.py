from langgraph.graph import StateGraph, END
from app.agents.nodes import (
    AgentState,
    devsecops_agent_node,
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
workflow.add_node("devsecops", devsecops_agent_node)
workflow.add_node("supervisor", supervisor_agent_node)

# 3. Connect sequential pipeline
workflow.set_entry_point("initializer")
workflow.add_edge("initializer", "devsecops")
workflow.add_edge("devsecops", "supervisor")
workflow.add_edge("supervisor", END)

# 4. Compile Graph
agent_graph = workflow.compile()
