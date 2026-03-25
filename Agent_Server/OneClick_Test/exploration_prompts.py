"""Prompt helpers for browser-use page exploration.

The file keeps two prompt families:
1. Legacy precision exploration prompt for the old oneclick fallback path.
2. Lean task-driven prompts for the exploration v2 dispatcher flow.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict


EXPLORATION_SYSTEM_PROMPT = """你是页面探索 Agent。

目标：
- 在满足用户目标的前提下，尽量完整探索当前站点的可访问功能。
- 页面之间由服务端负责整体推进；页面内部需要做充分探索。

必须遵守：
1. 严格匹配用户指定目标，不要擅自换成其他课程、章节或对象。
2. 进入页面后先 record_page()，再探索当前页的按钮、链接、标签、分页、弹窗和表单。
3. 每完成一次有效动作，都及时上报结果，不要长期把大量元素留在上下文里。
4. 遇到同页交互优先在当前页完成；遇到跳转结果如实上报。
5. 只有明显没有可继续探索的任务时，才结束当前页或整次探索。
6. 不执行删除、退出、提交高风险真实数据等危险操作。
"""


TASK_DRIVEN_EXPLORATION_SYSTEM_PROMPT = """你是页面探索执行 Agent。

当前处于服务端任务调度模式：
- FastAPI 负责页面队列、任务顺序、完成判定和知识沉淀
- 你负责记录当前页、执行当前任务、上报结果

你必须遵守：
1. 优先执行服务端返回的当前任务，不要自行改写全局任务顺序。
2. 每次有效动作后都调用 report_task_artifact() 上报结果。
3. 如果发现新增按钮、链接、弹窗、模块，调用 report_page_observation()。
4. 只有当服务端明确提示当前页没有 pending task 时，才调用 mark_page_completed()。
5. 不要把大量历史页面元素长期保留在上下文里，优先把中间态交给服务端。
"""


EXPLORATION_TASK_TEMPLATE = """
## 探索任务

用户目标: {user_goal}
目标地址: {target_url}
登录账号: {username}
登录密码: {password}
额外测试数据: {extra_credentials}
环境来源: {env_source}

目标解析:
{parsed_targets}

用户约束:
{user_constraints}

执行要求:
1. 如需要，先完成登录。
2. 进入页面后先 record_page()，尽量记录完整的交互元素。
3. 当前页优先探索：
   - 标签切换、展开/收起、分页、筛选、弹窗、表单
   - 列表项、详情入口、功能菜单、二级页面入口
4. 每完成一个明显动作后，调用 report_task_artifact()。
5. 若有新的页面观察结果，调用 report_page_observation()。
6. 如进入子页面，探索完后再返回继续当前分支；不要浅尝辄止。
7. 遇到用户明确指定的对象时，必须精确匹配文本，不要点击默认第一项。

停止条件:
- 当前页已无明显待探索功能，且没有新的有效跳转入口时，才允许结束。
- 不执行危险操作；无法继续时如实上报失败证据，不要静默跳过。
"""


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _extract_user_constraints(user_input: str) -> str:
    constraints = []
    for pattern in (r"不要[^，。；！\n]+", r"禁止[^，。；！\n]+", r"只[^，。；！\n]+", r"仅[^，。；！\n]+"):
        constraints.extend(re.findall(pattern, user_input))
    if not constraints:
        return "无特殊约束"
    return "\n".join(f"- {item}" for item in dict.fromkeys(constraints))


def _parse_user_targets(user_input: str) -> str:
    targets = []
    patterns = [
        (r"课程[：:]\s*([^\s，。；！\n]+)", "目标课程"),
        (r"([^\s，。；！\n]+)课程", "目标课程"),
        (r"测试\d+", "目标课程"),
        (r"test\d+", "目标课程"),
        (r"章节[：:]\s*([^\s，。；！\n]+)", "目标章节"),
        (r"第([一二三四五六七八九十\d]+)章", "目标章节"),
        (r"知识点[：:]\s*([^\s，。；！\n]+)", "目标知识点"),
    ]
    for pattern, label in patterns:
        matches = re.findall(pattern, user_input, re.IGNORECASE)
        for match in matches:
            text = str(match).strip()
            if text and text not in {"课程", "所有", "全部"}:
                targets.append(f"- {label}: {text}")
    if not targets:
        return "无具体目标限制，探索所有可访问内容"
    return "\n".join(dict.fromkeys(targets)) + "\n\n⚠️ 必须精确匹配上述目标。"


def _resolve_target_url(env: Dict[str, Any], target_url: str = "") -> str:
    return str(env.get("target_url") or env.get("base_url") or target_url or "")


def _session_context_lines(user_goal: str, env_info: Dict[str, Any], session_snapshot: Dict[str, Any]) -> list[str]:
    env = env_info or {}
    snapshot = session_snapshot or {}
    session_meta = snapshot.get("session") or {}
    current_page = snapshot.get("current_page") or {}
    current_meta = current_page.get("meta") or {}
    return [
        f"用户目标: {user_goal}",
        f"目标地址: {_resolve_target_url(env)}",
        f"会话状态: {session_meta.get('status', '')}",
        f"frontier_size: {snapshot.get('frontier_size', 0)}",
        f"navigation_count: {snapshot.get('navigation_count', 0)}",
        f"当前页: {current_page.get('page_key', '')}",
        f"当前页URL: {current_meta.get('url', '')}",
        f"当前页状态: {current_meta.get('status', '')}",
    ]


def build_exploration_prompt(
    user_goal: str,
    target_url: str = "",
    username: str = "",
    password: str = "",
    pages: list | None = None,  # 保留兼容参数
    env_info: dict | None = None,
) -> str:
    """Build the concise legacy precision-exploration prompt."""
    env = env_info or {}
    extra_credentials = env.get("extra_credentials") or {}
    extra_credentials_text = "无"
    if isinstance(extra_credentials, dict) and extra_credentials:
        extra_credentials_text = _compact_json(extra_credentials)
    elif extra_credentials:
        extra_credentials_text = str(extra_credentials)

    return EXPLORATION_TASK_TEMPLATE.format(
        user_goal=user_goal,
        target_url=_resolve_target_url(env, target_url),
        username=env.get("username") or username,
        password=env.get("password") or password,
        extra_credentials=extra_credentials_text,
        env_source=env.get("env_name") or env.get("_source", "默认环境"),
        parsed_targets=_parse_user_targets(user_goal),
        user_constraints=_extract_user_constraints(user_goal),
    )


def build_task_driven_exploration_prompt(
    user_goal: str,
    env_info: dict | None = None,
    session_snapshot: dict | None = None,
) -> str:
    """Build a page-level prompt for the v2 task-dispatch flow."""
    snapshot = session_snapshot or {}
    current_page = snapshot.get("current_page") or {}
    next_tasks = current_page.get("next_pending_tasks") or []
    lines = [
        "你是页面探索执行 Agent。",
        "当前模式为服务端任务调度模式：FastAPI 负责会话、页面、任务顺序和完成判定，你负责记录页面、执行当前任务、上报结果。",
        "",
        "执行原则：",
        "1. 先调用 record_page() 记录当前页。",
        "2. 优先遵循服务端返回的 next task 或 dispatch_next_task() 返回任务。",
        "3. 每完成一次有效动作，都调用 report_task_artifact()。",
        "4. 如果发现新按钮、链接、弹窗、模块，请调用 report_page_observation()。",
        "5. 只有当服务端明确提示当前页没有 pending task 时，才调用 mark_page_completed()。",
        "",
        *_session_context_lines(user_goal, env_info or {}, snapshot),
    ]
    if next_tasks:
        lines.append("当前页待执行任务预览:")
        for task in next_tasks[:5]:
            lines.append(
                f"- {task.get('task_id', '')} | {task.get('task_group', '')} | "
                f"{task.get('task_type', '')} | {task.get('element_label', '')}"
            )
    else:
        lines.append("当前页暂未缓存到 pending task，请先 record_page()，再按服务端返回推进。")
    lines.extend(
        [
            "",
            "不要长期把大量页面元素留在上下文里；优先通过 report_* 工具把中间态交给服务端。",
            "如果 controller 的返回已经给出了下一步任务，优先直接执行那个任务。",
        ]
    )
    return "\n".join(lines)


def build_single_task_round_prompt(
    user_goal: str,
    env_info: dict | None = None,
    session_snapshot: dict | None = None,
    assigned_task: dict | None = None,
) -> str:
    """Build a narrow prompt for one server-assigned exploration task."""
    snapshot = session_snapshot or {}
    task = assigned_task or {}
    action_payload = task.get("action_payload") or {}
    lines = [
        "你是页面探索执行 Agent。",
        "当前轮次必须优先围绕服务端分配的单个任务执行，而不是重新规划整页探索顺序。",
        "",
        "执行要求：",
        "1. 如果当前浏览器上下文还没有记录当前页，先调用 record_page()。",
        "2. 仅围绕下面这个服务端任务执行。",
        "3. 执行后必须调用 report_task_artifact() 上报结果。",
        "4. 如果执行后发现新的按钮、链接、弹窗、模块，再调用 report_page_observation()。",
        "5. 不要跳到其他未分配任务，除非服务端返回了新的 next task。",
        "",
        *_session_context_lines(user_goal, env_info or {}, snapshot),
        "",
        "当前服务端任务:",
        f"- task_id: {task.get('task_id', '')}",
        f"- task_group: {task.get('task_group', '')}",
        f"- task_type: {task.get('task_type', '')}",
        f"- element_label: {task.get('element_label', '')}",
        f"- selector: {action_payload.get('selector', '')}",
        f"- candidate_id: {action_payload.get('candidate_id', '')}",
        f"- href: {action_payload.get('href', '')}",
        "",
        "如果这个任务执行失败，请如实上报失败证据；不要静默跳过。",
        "如果这个任务导致跳转，请在 report_task_artifact() 里带上 navigated/new_url/target_page_name。",
    ]
    return "\n".join(lines)
