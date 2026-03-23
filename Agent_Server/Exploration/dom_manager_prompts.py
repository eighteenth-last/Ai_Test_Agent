import json


def build_dom_manager_prompt(goal: str, snapshot: dict, candidates: list[dict]) -> str:
    return (
        "基于当前页面 DOM 摘要，选择最值得探索的安全任务。\n"
        "只返回 JSON：{\"tasks\":[{\"candidate_id\":\"...\",\"target_name\":\"...\",\"priority\":0,\"semantic_group\":\"...\"}]}\n\n"
        f"用户目标:\n{goal}\n\n"
        f"页面快照:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"候选操作:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
