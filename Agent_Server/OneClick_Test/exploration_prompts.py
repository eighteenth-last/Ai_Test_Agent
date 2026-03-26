"""Prompt helpers for browser-use page exploration.

This module intentionally keeps prompt construction lightweight and explicit:
1. Legacy precision exploration prompt for the old fallback path.
2. Page-level dispatcher prompt for BFS-managed exploration.
3. Single-task prompt for server-assigned task execution with effect validation.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List


EXPLORATION_SYSTEM_PROMPT = """你是页面探索 Agent。
目标:
- 在满足用户目标的前提下，尽量完整探索当前站点的可访问功能。
- 页面之间由服务端负责整体推进；页面内部需要做充分探索。

必须遵守:
1. 严格匹配用户指定目标，不要擅自切换课程、章节或对象。
2. 进入页面后先 `record_page()`，再探索按钮、链接、标签、分页、弹窗和表单。
3. 每完成一次有效动作，及时通过 `report_task_artifact()` 或 `report_page_observation()` 上报结果。
4. 同页交互优先在当前页完成；如果发生跳转，要如实上报。
5. 只有明显没有待探索能力时，才结束当前页或整次探索。
6. 不执行删除、退出登录、提交真实生产数据等高风险动作，除非任务明确要求且有验证标准。"""


TASK_DRIVEN_EXPLORATION_SYSTEM_PROMPT = """你是页面探索执行 Agent。
当前运行在 FastAPI 调度模式:
- FastAPI 负责页面队列、任务顺序、完成判定和知识沉淀。
- 你负责记录当前页、执行当前任务、验证效果、上报证据。

必须遵守:
1. 优先执行服务端下发的当前任务，不要擅自改写全局任务顺序。
2. 每次有效动作后，都调用 `report_task_artifact()` 上报结构化结果。
3. 如果发现新的按钮、链接、弹窗或模块，调用 `report_page_observation()`。
4. 只有服务端明确提示当前页没有 pending task 时，才调用 `mark_page_completed()`。
5. 优先把中间状态交给服务端，不要长期保留大量历史页面上下文。
6. 如果上下文提供了账号、密码或测试数据，必须优先使用真实数据，禁止编造 `testuser`、`123456`、`testpass` 一类占位值。"""


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
1. 如需登录，优先使用给定环境数据。
2. 进入页面后先 `record_page()`，记录完整交互元素。
3. 优先探索当前页可见功能:
   - 标签切换、展开/收起、分页、筛选、弹窗、表单
   - 列表页、详情入口、功能菜单、二级页面入口
4. 每完成一个明显动作后，调用 `report_task_artifact()`。
5. 若有新的页面观察结果，调用 `report_page_observation()`。
6. 如进入子页面，探索完成后返回继续当前分支，不要浅尝辄止。
7. 遇到用户明确指定的对象时，必须精确匹配文本，不要点击默认第一项。

停止条件:
- 当前页已无明显待探索功能，且没有新的有效跳转入口时，才允许结束。
- 无法继续时如实上报失败证据，不要静默跳过。"""


def _compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _extract_user_constraints(user_input: str) -> str:
    constraints: List[str] = []
    for pattern in (r"不要[^，。；;\n]+", r"禁止[^，。；;\n]+", r"只能[^，。；;\n]+", r"必须[^，。；;\n]+"):
        constraints.extend(re.findall(pattern, user_input or ""))
    if not constraints:
        return "无特殊约束"
    return "\n".join(f"- {item}" for item in dict.fromkeys(constraints))


def _parse_user_targets(user_input: str) -> str:
    text = user_input or ""
    targets: List[str] = []
    patterns = [
        (r"课程[:：]?\s*([^\s，。；;\n]+)", "目标课程"),
        (r"([^\s，。；;\n]+)课程", "目标课程"),
        (r"测试\d+", "目标课程"),
        (r"test\d+", "目标课程"),
        (r"章节[:：]?\s*([^\s，。；;\n]+)", "目标章节"),
        (r"第?[一二三四五六七八九十\d]+章", "目标章节"),
        (r"知识点[:：]?\s*([^\s，。；;\n]+)", "目标知识点"),
    ]
    for pattern, label in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            target = str(match).strip()
            if target and target not in {"课程", "所有", "全部"}:
                targets.append(f"- {label}: {target}")
    if not targets:
        return "无具体目标限制，探索所有可访问内容。"
    return "\n".join(dict.fromkeys(targets)) + "\n\n注意: 必须精确匹配上述目标。"


def _resolve_target_url(env: Dict[str, Any], target_url: str = "") -> str:
    return str(env.get("target_url") or env.get("base_url") or target_url or "")


def _extra_credentials_text(env: Dict[str, Any]) -> str:
    extra_credentials = env.get("extra_credentials") or {}
    if isinstance(extra_credentials, dict):
        return _compact_json(extra_credentials) if extra_credentials else "无"
    return str(extra_credentials) if extra_credentials else "无"


def _credential_context_lines(env_info: Dict[str, Any]) -> List[str]:
    env = env_info or {}
    return [
        f"登录账号: {env.get('username') or '未提供'}",
        f"登录密码: {env.get('password') or '未提供'}",
        f"额外测试数据: {_extra_credentials_text(env)}",
        f"环境来源: {env.get('env_name') or env.get('_source', '默认环境')}",
    ]


def _session_context_lines(user_goal: str, env_info: Dict[str, Any], session_snapshot: Dict[str, Any]) -> List[str]:
    env = env_info or {}
    snapshot = session_snapshot or {}
    session_meta = snapshot.get("session") or {}
    current_page = snapshot.get("current_page") or {}
    current_meta = current_page.get("meta") or {}
    current_scan = current_page.get("scan_summary") or {}
    task_summary = current_page.get("task_status_summary") or {}
    return [
        f"用户目标: {user_goal}",
        f"目标地址: {_resolve_target_url(env)}",
        f"会话状态: {session_meta.get('status', '')}",
        f"frontier_size: {snapshot.get('frontier_size', 0)}",
        f"navigation_count: {snapshot.get('navigation_count', 0)}",
        f"当前页: {current_page.get('page_key', '')}",
        f"当前页 URL: {current_meta.get('url', '')}",
        f"当前页状态: {current_meta.get('status', '')}",
        f"当前页交互元素数: {current_scan.get('interactive_count', 0)}",
        f"当前页 state_signals: {', '.join(current_scan.get('state_signals') or []) or '无'}",
        f"当前页任务概览: pending={task_summary.get('pending', 0)}, retry_pending={task_summary.get('retry_pending', 0)}, accepted={task_summary.get('accepted', 0)}",
    ]


def _task_candidate_lines(task: Dict[str, Any]) -> List[str]:
    lines = ["候选元素池(按优先级排序):"]
    candidate_pool = task.get("candidate_pool") or []
    if not candidate_pool:
        lines.append("- 无候选元素，优先结合当前 DOM 重新定位并如实上报。")
        return lines
    for candidate in candidate_pool[:5]:
        lines.append(
            "- "
            f"label={candidate.get('label', '')}; "
            f"selector={candidate.get('selector', '')}; "
            f"candidate_id={candidate.get('candidate_id', '')}; "
            f"href={candidate.get('href', '')}; "
            f"confidence={candidate.get('confidence', '')}; "
            f"reason={candidate.get('reason', '')}"
        )
    return lines


def _task_memory_lines(task: Dict[str, Any]) -> List[str]:
    lines = ["本任务历史尝试:"]
    memory = task.get("task_memory") or []
    if not memory:
        lines.append("- 暂无历史尝试")
        return lines
    for item in memory[-5:]:
        lines.append(
            "- "
            f"attempt={item.get('attempt', '')}; "
            f"status={item.get('status', '')}; "
            f"effect_type={item.get('effect_type', '')}; "
            f"summary={item.get('summary', '')}"
        )
    return lines


def build_exploration_prompt(
    user_goal: str,
    target_url: str = "",
    username: str = "",
    password: str = "",
    pages: list | None = None,  # 保留兼容参数
    env_info: dict | None = None,
) -> str:
    """Build the concise legacy exploration prompt."""
    del pages
    env = env_info or {}
    extra_credentials_text = _extra_credentials_text(env)
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
        "当前模式为服务端任务调度模式: FastAPI 负责会话、页面、任务顺序和完成判定；你负责记录页面、执行当前任务并上报结果。",
        "",
        "执行原则:",
        "1. 先调用 `record_page()` 记录当前页。",
        "2. 优先遵循服务端返回的 next task，或主动调用 `dispatch_next_task()` 领取任务。",
        "3. 每完成一次有效动作，都调用 `report_task_artifact()`。",
        "4. 如果发现新的按钮、链接、弹窗、模块，调用 `report_page_observation()`。",
        "5. 只有服务端明确提示当前页没有 pending task 时，才调用 `mark_page_completed()`。",
        "",
        *_session_context_lines(user_goal, env_info or {}, snapshot),
        *_credential_context_lines(env_info or {}),
        "如果遇到登录、查询、创建等需要测试数据的场景，优先使用给定环境数据；未提供时再明确上报缺失。",
    ]
    if next_tasks:
        lines.append("当前页待执行任务预览:")
        for task in next_tasks[:5]:
            lines.append(
                "- "
                f"{task.get('task_id', '')} | "
                f"{task.get('task_group', '')} | "
                f"{task.get('task_type', '')} | "
                f"{task.get('task_goal', '')}"
            )
    else:
        lines.append("当前页还没有缓存任务，请先 `record_page()`，再根据服务端返回推进。")
    lines.extend(
        [
            "",
            "不要长期保留大量历史元素在上下文里；优先通过 `report_*` 工具把中间状态交给服务端。",
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
    page_summary = task.get("page_summary") or {}
    success_criteria = task.get("success_criteria") or []
    failure_signals = task.get("failure_signals") or []
    forbidden_targets = task.get("forbidden_targets") or []
    expected_effects = task.get("expected_effects") or []
    is_validation_task = bool(task.get("is_validation_task"))
    validation_goal = str(task.get("validation_goal") or "").strip()
    validation_signals = task.get("validation_success_signals") or []
    resume_after_validation = bool(task.get("resume_after_validation"))
    current_page = snapshot.get("current_page") or {}
    page_key = task.get("page_key") or current_page.get("page_key") or ""

    lines = [
        "你是页面探索执行 Agent。",
        "当前轮次必须优先围绕服务端分配的单个任务执行，不要重新规划整页探索顺序。",
        "",
        "执行要求:",
        "1. 如果当前浏览器上下文还没有记录当前页，先调用 `record_page()`。",
        "2. 只围绕下面这个服务端任务执行，不要跳到未分配任务。",
        "3. 执行后必须调用 `report_task_artifact()` 上报结果。",
        "4. 如果执行后发现新的按钮、链接、弹窗或模块，再调用 `report_page_observation()`。",
        "5. 任务失败时要如实上报失败证据，不要静默跳过。",
        "6. 如果动作导致跳转，在 `report_task_artifact()` 中带上 `navigated/new_url/target_page_name`。",
        "7. 如果点错元素或没有效果，要在 `effect_type` 中明确写 `wrong_target` 或 `no_effect`，并填写 `replan_reason`。",
        "",
        *_session_context_lines(user_goal, env_info or {}, snapshot),
        *_credential_context_lines(env_info or {}),
        "如果当前任务涉及登录或表单输入，必须优先使用上述真实环境数据，禁止自行编造占位值。",
        "",
        "当前服务端任务:",
        f"- page_id/page_key: {page_key}",
        f"- task_id: {task.get('task_id', '')}",
        f"- task_group: {task.get('task_group', '')}",
        f"- task_type: {task.get('task_type', '')}",
        f"- task_goal: {task.get('task_goal', '')}",
        f"- task_description: {task.get('task_description', '')}",
        f"- element_label: {task.get('element_label', '')}",
        f"- selector: {action_payload.get('selector', '')}",
        f"- candidate_id: {action_payload.get('candidate_id', '')}",
        f"- href: {action_payload.get('href', '')}",
        f"- max_attempts: {task.get('max_attempts', '')}",
        f"- attempt_count: {task.get('attempt_count', '')}",
        f"- expected_effects: {', '.join(expected_effects) or '未指定'}",
        f"- is_validation_task: {is_validation_task}",
        f"- validation_goal: {validation_goal or '无'}",
        f"- resume_after_validation: {resume_after_validation}",
        f"- page_state_signals: {', '.join(page_summary.get('state_signals') or []) or '无'}",
        f"- key_sections: {', '.join(page_summary.get('key_sections') or []) or '无'}",
        "",
        *_task_candidate_lines(task),
        "",
        "成功判定标准:",
    ]
    if success_criteria:
        lines.extend(f"- {item}" for item in success_criteria[:6])
    else:
        lines.append("- 没有显式标准时，也要根据 DOM、URL、弹窗、内容变化判断是否真的达成目标。")

    lines.extend(["", "失败信号:"])
    if failure_signals:
        lines.extend(f"- {item}" for item in failure_signals[:6])
    else:
        lines.append("- 没有显式失败信号时，如实描述未发生预期变化。")

    if is_validation_task:
        lines.extend(["", "验证任务要求:"])
        if validation_signals:
            lines.extend(f"- {item}" for item in validation_signals[:6])
        else:
            lines.append("- 只验证这个小任务的效果，不扩展成新的探索任务。")
        lines.extend(
            [
                "- 这是单个小任务的验证模式，执行后不要重新获取页面元素，不要 `record_page()`，不要生成新队列。",
                "- 如果验证通过且需要恢复会话，先恢复到执行前会话，再立即调用 `report_task_artifact()` 提交终态。",
                "- `report_task_artifact()` 中必须填写 `is_validation_task=true`。",
                "- 如果验证通过，填写 `validation_passed=true`；如果恢复成功，填写 `session_restored=true`。",
                "- 这类任务提交后必须终态完成，避免再次派发。",
            ]
        )

    lines.extend(["", "禁止重复命中的目标:"])
    if forbidden_targets:
        lines.extend(f"- {item}" for item in forbidden_targets[:8])
    else:
        lines.append("- 暂无")

    lines.extend(["", *_task_memory_lines(task), ""])
    lines.extend(
        [
            "结果上报要求:",
            f"- `report_task_artifact(page_id='{page_key}', task_id=..., task_group=...)` 中至少填写:",
            "  `validation_status`, `effect_type`, `observed_result`, `executed_target`, `before_state`, `after_state`, `evidence`。",
            "- `validation_status` 只能使用 `accepted`、`retry_pending`、`failed`、`skipped`。",
            "- `effect_type` 优先使用 `navigation_detected`、`dialog_opened`、`dialog_closed`、`content_expanded`、`form_submitted`、`state_changed`、`no_effect`、`wrong_target`、`failed`。",
            "- 如果当前任务没有成功，但还有合理重试空间，请返回 `validation_status=retry_pending` 并说明新的尝试方向。",
        ]
    )
    return "\n".join(lines)
