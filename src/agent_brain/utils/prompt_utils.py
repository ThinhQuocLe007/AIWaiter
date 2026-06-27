import json
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from src.agent_brain.config import settings

def load_prompt(filename: str, sub_dir: str = "system_prompts") -> str:
    """
    Loads a markdown or text prompt file from the resources directory.
    Example: load_prompt("router_agent.md") or load_prompt("hospitality.md", "skills")
    """
    path = settings.resources_dir / sub_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_json_data(filename: str, sub_dir: str = "few_shots") -> list | dict:
    """
    Loads a JSON file (e.g. for few-shot examples).
    Example: load_json_data("router.json")
    """
    path = settings.resources_dir / sub_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
        
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_system_prompt(core_prompt_name: str, active_skills: List[str] = None) -> SystemMessage:
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

def build_few_shot_examples(filename: str, sub_dir: str = "few_shots") -> List[BaseMessage]:
    """
    Loads few-shot dataset and converts it directly to LangChain BaseMessage objects.
    Enables prefix caching of static training trajectories.
    """
    raw_data = load_json_data(filename, sub_dir)
    messages = []
    for msg in raw_data:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            tool_calls = msg.get("tool_calls", [])
            lc_tool_calls = []
            for tc in tool_calls:
                lc_tool_calls.append({
                    "name": tc["name"],
                    "args": tc["args"],
                    "id": tc.get("id", f"call_{hash(tc['name'])}"),
                    "type": "tool_call"
                })
            messages.append(AIMessage(content=content, tool_calls=lc_tool_calls))
    return messages

def build_dynamic_suffix(table_id: str, dynamic_context: str = None) -> SystemMessage:
    """
    Assembles session metadata and any dynamic/uncached runtime context.
    Placed at the END of the prompt sequence to preserve prefix KV caching.
    """
    dynamic_text = f"SESSION METADATA:\n- Bàn phục vụ (Table ID): {table_id}"
    if dynamic_context:
        dynamic_text += f"\n\nDYNAMIC CONTEXT:\n{dynamic_context}"
    return SystemMessage(content=dynamic_text)
