import json


def build_vision_manager_prompt(goal: str, snapshot: dict, candidates: list[dict]) -> str:
    return (
        "你是视觉任务管理器。结合截图和候选区域，选择当前页面最值得探索的安全任务。\n"
        "只返回 JSON：{\"tasks\":[{\"candidate_id\":\"...\",\"target_name\":\"...\",\"priority\":0,\"semantic_group\":\"...\"}]}\n\n"
        f"用户目标:\n{goal}\n\n"
        f"页面快照:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"候选区域:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
