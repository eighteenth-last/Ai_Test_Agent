import json


def build_vision_worker_prompt(task_name: str, candidates: list[dict]) -> str:
    return (
        "你是视觉定位器。你的唯一任务是在截图中定位当前目标。\n"
        "只返回 JSON：{\"found\":true/false,\"candidate_id\":\"...\",\"confidence\":0.0,\"reason\":\"...\"}\n\n"
        f"目标任务:\n{task_name}\n\n"
        f"候选区域:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
