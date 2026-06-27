from ai_waiter_core.agent.graph import AIWaiterGraph

def get_agent_app():
    """
    Helper function to get the compiled LangGraph application from AIWaiterGraph.
    Ensures backward compatibility with older tests, websocket servers, and scripts.
    """
    agent = AIWaiterGraph()
    return agent.app
