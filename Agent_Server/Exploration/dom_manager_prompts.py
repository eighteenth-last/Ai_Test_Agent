import json


def build_dom_manager_prompt(goal: str, snapshot: dict, candidates: list[dict]) -> str:
    return (
        "你是页面 DOM 交互元素整理器。\n"
        "你的任务是从候选 DOM 元素中，挑选出真正值得提交给后端生成任务队列的可交互元素。\n"
        "只返回 JSON，不要输出解释文字。\n\n"
        "输出 JSON schema:\n"
        "{\n"
        '  "interactive_elements": [\n'
        "    {\n"
        '      "candidate_id": "c1",\n'
        '      "interaction_type": "button|link|input|tab|menu|dialog_trigger|toggle|submit|other",\n'
        '      "confidence": 0.0,\n'
        '      "reason": "为什么它可交互，为什么值得进入任务队列",\n'
        '      "label_override": "可选，必要时纠正可见标签"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "筛选规则:\n"
        "1. 只保留用户或自动化可以直接操作的元素。\n"
        "2. 排除纯展示元素、标题、统计值、装饰图标。\n"
        "3. 如果元素看起来像头像或用户名，但旁边存在明确动作按钮，例如“退出登录”，优先保留动作按钮，不要误选头像。\n"
        "4. 如果一个候选没有明确交互意图，不要保留。\n"
        "5. 优先保留与当前页面目标相关、且能触发状态变化或导航的元素。\n\n"
        f"页面目标:\n{goal}\n\n"
        f"页面快照:\n{json.dumps(snapshot, ensure_ascii=False, indent=2)}\n\n"
        f"DOM 候选:\n{json.dumps(candidates, ensure_ascii=False, indent=2)}"
    )
