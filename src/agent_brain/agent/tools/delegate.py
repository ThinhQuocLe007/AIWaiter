from langchain_core.tools import tool


@tool
def delegate(reason: str) -> str:
    """
    Escape hatch: call when the customer utterance does NOT match your
    worker's responsibility. Routes to the conversational chat system.

    Use when:
      - The customer is asking a question, not requesting an action
      - The intent is unclear or outside your scope
      - The customer is making small talk or greetings

    Do NOT use when the customer clearly requests an action you can handle.
    """
    return reason
