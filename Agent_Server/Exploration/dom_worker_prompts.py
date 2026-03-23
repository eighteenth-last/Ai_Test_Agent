import json


def build_dom_worker_prompt(task_name: str, candidates: list[dict]) -> str:
    return (
        "你是 DOM 定位器。你的唯一任务是定位当前目标，不做任何额外动作。\n"
        "只返回 JSON：{\"found\":true/false,\"candidate_id\":\"...\",\"confidence\":0.0,\"reason\":\"...\"}\n\n"
        f"目标任务:\n{task_name}\n\n"
        f"候选元素:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
