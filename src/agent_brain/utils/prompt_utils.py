import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.agent_brain.config import settings

_ORDER_TOOLS = {"add_cart", "remove_cart", "clear_cart", "confirm_order", "delegate"}
_SEARCH_TOOLS = {"search", "delegate"}


def _format_tool_arg(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        items = []
        for el in v:
            if isinstance(el, dict):
                inner = ", ".join(f"{k}: {_format_tool_arg(v2)}" for k, v2 in el.items())
                items.append("{" + inner + "}")
            else:
                items.append(_format_tool_arg(el))
        return "[" + ", ".join(items) + "]"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f'"{v}"'


def last_n_turns(messages: list, n: int) -> list:
    """Return the last N HumanMessage-anchored spans.

    Each span: [HumanMessage, AIMessage?, ToolMessage?*].
    On retry (validator feedback loop), the ToolMessages injected
    after the last AIMessage stay in the final span — the worker
    still sees its own failed attempt + the validator feedback in
    the trimmed history.

    Returns all messages if there are fewer than N turns.
    """
    if n <= 0 or not messages:
        return []

    spans = []
    current = []
    for msg in messages:
        if isinstance(msg, HumanMessage) and current:
            spans.append(current)
            current = []
        current.append(msg)
    if current:
        spans.append(current)

    trimmed = []
    for span in spans[-n:]:
        trimmed.extend(span)
    return trimmed

def load_prompt(filename: str, sub_dir: str = "system_prompts") -> str:
    """
    Loads a markdown or text prompt file from the resources directory.
    Example: load_prompt("rewriter_agent.md") or load_prompt("hospitality.md", "skills")
    """
    path = settings.resources_dir / sub_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, encoding="utf-8") as f:
        return f.read()

def load_json_data(filename: str, sub_dir: str = "few_shots") -> list | dict:
    """
    Loads a JSON file (e.g. for few-shot examples).
    Example: load_json_data("router.json")
    """
    path = settings.resources_dir / sub_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with open(path, encoding="utf-8") as f:
        return json.load(f)

def build_system_prompt(core_prompt_name: str, active_skills: list[str] = None) -> SystemMessage:
    """
    Assembles static system prompts and skills. Since this content is static,
    its computed KV cache is fully reusable. Do not put dynamic variables here.
    """
    # Load technical skeleton prompt
    skeleton = load_prompt(core_prompt_name, sub_dir="system_prompts")

    # Load and merge active skills
    skills_text = []
    if active_skills:
        for skill in active_skills:
            skill_content = load_prompt(skill, sub_dir="skills")
            skills_text.append(skill_content)

    fused_content = skeleton
    if skills_text:
        fused_content += "\n\n" + "\n\n".join(skills_text)

    return SystemMessage(content=fused_content)

def build_few_shot_examples(filename: str, sub_dir: str = "few_shots") -> list[BaseMessage]:
    """Load few-shot examples as message pairs, wrapped in boundary markers.

    Each user message is prefixed with ``[EXAMPLE] `` so the LLM can distinguish
    training turns from real conversation history. Boundary SystemMessages
    further isolate the block to prevent context contamination.
    """
    raw_data = load_json_data(filename, sub_dir)

    has_add_cart = any("add_cart" in str(msg) for msg in raw_data)
    domain = "cart CRUD" if has_add_cart else "search"

    messages: list[BaseMessage] = [
        SystemMessage(content=(
            f"═══════ FEW-SHOT EXAMPLES START (domain: {domain}) ═══════\n"
            f"The messages below are TRAINING EXAMPLES only — they are NOT "
            f"part of the current conversation. Items mentioned here are NOT "
            f"in the customer's cart. Do NOT reference these items in your response."
        )),
    ]

    for msg in raw_data:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=f"[EXAMPLE] {content}"))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            lc_tool_calls = []
            for tc in tool_calls:
                lc_tool_calls.append({
                    "name": tc["name"],
                    "args": tc["args"],
                    "id": tc.get("id", f"call_{hash(tc['name'])}"),
                    "type": "tool_call",
                })
            messages.append(AIMessage(content=content, tool_calls=lc_tool_calls))

    messages.append(
        SystemMessage(content=(
            "═══════ FEW-SHOT EXAMPLES END ═══════\n"
            "The above were TRAINING examples. The REAL conversation follows below."
        )),
    )
    return messages

def build_few_shot_text(filename: str, sub_dir: str = "few_shots") -> str:
    """Format few-shot examples as a plain-text reference block.

    Unlike ``build_few_shot_examples``, this returns a single string meant to be
    appended to the system prompt — it does NOT create HumanMessage/AIMessage pairs
    that could be confused with real conversation history by the LLM.

    The output is a clearly demarcated section:
        ### TRAINING EXAMPLES (reference — NOT conversation history):
        Customer: ...
        → tool_name(args)
    """
    raw_data = load_json_data(filename, sub_dir)
    lines: list[str] = []

    # Detect whether these examples use order- or search-domain tools so the
    # prefix describes the right domain.
    has_add_cart = any("add_cart" in str(msg) for msg in raw_data)
    domain = "cart CRUD" if has_add_cart else "search"

    lines.append(
        f"### TRAINING EXAMPLES — {domain} (for reference ONLY — these are NOT "
        f"part of the current conversation and the items mentioned below are NOT "
        f"in the customer's cart):"
    )

    i = 0
    while i < len(raw_data):
        user_msg = raw_data[i]
        asst_msg = raw_data[i + 1] if i + 1 < len(raw_data) else None
        i += 2

        user_text = user_msg.get("content", "")
        tool_calls = (asst_msg or {}).get("tool_calls", [])

        lines.append("")
        lines.append(f"Customer: \"{user_text}\"")
        for tc in tool_calls:
            name = tc.get("name", "?")
            args = tc.get("args", {})
            args_parts = []
            for k, v in args.items():
                if v is not None and v != "":
                    args_parts.append(f"{k}={_format_tool_arg(v)}")
            args_str = ", ".join(args_parts)
            if not args_str and name in ("clear_cart", "delegate"):
                lines.append(f"  → {name}()")
            else:
                lines.append(f"  → {name}({args_str})")

    return "\n".join(lines)


def build_dynamic_suffix(table_id: str, dynamic_context: str = None) -> SystemMessage:
    """
    Assembles session metadata and any dynamic/uncached runtime context.
    Placed at the END of the prompt sequence to preserve prefix KV caching.
    """
    dynamic_text = f"SESSION METADATA:\n- Bàn phục vụ (Table ID): {table_id}"
    if dynamic_context:
        dynamic_text += f"\n\nDYNAMIC CONTEXT:\n{dynamic_context}"
    return SystemMessage(content=dynamic_text)
