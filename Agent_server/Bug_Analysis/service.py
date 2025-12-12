"""
Bug 分析服务

负责在测试执行过程中检测、分析和记录 Bug
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import BugReport, TestCase, TestResult


class BugAnalysisService:
    """Bug 分析服务"""
    
    # 严重程度定义
    SEVERITY_LEVELS = {
        "一级": {
            "name": "致命",
            "description": "系统崩溃/核心功能完全失效/数据丢失",
            "should_stop": True,
            "color": "#f56c6c"
        },
        "二级": {
            "name": "严重",
            "description": "主要功能异常/存在重大安全隐患",
            "should_stop": True,
            "color": "#e6a23c"
        },
        "三级": {
            "name": "一般",
            "description": "次要功能异常/用户体验显著下降",
            "should_stop": False,
            "color": "#FFFF00"
        },
        "四级": {
            "name": "轻微",
            "description": "优化建议/不影响使用的UI/文案问题",
            "should_stop": False,
            "color": "#808080"
        }
    }
    
    @staticmethod
    async def analyze_bug_from_execution(
        test_case_id: int,
        test_result_id: int,
        execution_history: Dict[str, Any],
        error_message: str,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        从测试执行结果中分析 Bug
        
        Args:
            test_case_id: 测试用例ID
            test_result_id: 测试结果ID
            execution_history: 执行历史
            error_message: 错误信息
            db: 数据库会话
        
        Returns:
            Bug 分析结果
        """
        try:
            # 获取测试用例信息
            test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
            if not test_case:
                return None
            
            # 使用 LLM 分析 Bug
            from Api_request.llm_client import get_llm_client
            llm_client = get_llm_client()
            
            # 构建分析提示
            analysis_prompt = BugAnalysisService._build_analysis_prompt(
                test_case, execution_history, error_message
            )
            
            # 调用 LLM 分析
            result = llm_client.analyze_bug(analysis_prompt)
            
            if not result.get('success'):
                print(f"[BugAnalysis] LLM 分析失败: {result.get('message')}")
                return None
            
            bug_data = result.get('data', {})
            
            # 提取最后一步的 URL 作为定位地址
            location_url = ""
            if execution_history and execution_history.get('steps'):
                last_step = execution_history['steps'][-1]
                location_url = last_step.get('url', '')
            
            # 提取复现步骤 - 直接使用测试用例中的步骤
            print(f"[BugAnalysis] 🔍 开始提取复现步骤...")
            print(f"[BugAnalysis] 测试用例步骤数: {len(json.loads(test_case.steps)) if test_case.steps else 0}")
            print(f"[BugAnalysis] 执行历史步骤数: {len(execution_history.get('steps', [])) if execution_history else 0}")
            
            reproduce_steps = BugAnalysisService._extract_reproduce_steps_from_test_case(
                test_case, execution_history
            )
            
            print(f"[BugAnalysis] 提取到的复现步骤:")
            for step in reproduce_steps:
                print(f"  - {step}")
            
            # 提取临时截图路径 - 从执行历史中查找 save_screenshot 或 save_pdf 动作
            temp_screenshot_path = BugAnalysisService._extract_screenshot_path(execution_history)
            
            # 获取错误类型和严重程度
            error_type = bug_data.get('error_type', '系统错误')
            severity_level = bug_data.get('severity_level', '一级')
            
            # 检查是否有重复的 Bug（相同的 bug_name, error_type, severity_level）
            duplicate_count = db.query(BugReport).filter(
                BugReport.bug_name == test_case.title,
                BugReport.error_type == error_type,
                BugReport.severity_level == severity_level
            ).count()
            
            # 生成标准化的截图文件名和路径
            final_screenshot_path = BugAnalysisService._save_screenshot_with_standard_name(
                temp_screenshot_path,
                bug_name=test_case.title,
                severity_level=severity_level,
                error_type=error_type,
                duplicate_count=duplicate_count
            )
            
            # 保存 Bug 到数据库
            bug_report = BugReport(
                bug_name=test_case.title,
                test_case_id=test_case_id,
                test_result_id=test_result_id,
                location_url=location_url,
                error_type=error_type,
                severity_level=severity_level,
                reproduce_steps=json.dumps(reproduce_steps, ensure_ascii=False),
                screenshot_path=final_screenshot_path,
                result_feedback=bug_data.get('result_feedback', ''),
                expected_result=test_case.expected,
                actual_result=bug_data.get('actual_result', error_message),
                status='待处理'
            )
            
            db.add(bug_report)
            db.commit()
            db.refresh(bug_report)
            
            print(f"[BugAnalysis] ✓ Bug 已记录: ID={bug_report.id}, 严重程度={bug_report.severity_level}")
            
            return {
                "bug_id": bug_report.id,
                "severity_level": bug_report.severity_level,
                "should_stop": BugAnalysisService.SEVERITY_LEVELS.get(
                    bug_report.severity_level, {}
                ).get('should_stop', True),
                "error_type": bug_report.error_type,
                "result_feedback": bug_report.result_feedback
            }
        
        except Exception as e:
            import traceback
            print(f"[BugAnalysis] ❌ 分析 Bug 失败: {str(e)}")
            print(traceback.format_exc())
            return None
    
    @staticmethod
    def _build_analysis_prompt(
        test_case: TestCase,
        execution_history: Dict[str, Any],
        error_message: str
    ) -> str:
        """构建 Bug 分析提示"""
        
        steps_text = "\n".join([
            f"{i+1}. {step}" for i, step in enumerate(json.loads(test_case.steps))
        ])
        
        history_text = ""
        if execution_history and execution_history.get('steps'):
            history_text = "\n".join([
                f"步骤{i+1}: {step.get('url', '')} - {step.get('thinking', '')}"
                for i, step in enumerate(execution_history['steps'])
            ])
        
        prompt = f"""
请分析以下测试执行中遇到的问题，并判断 Bug 的严重程度和类型。

【测试用例信息】
用例名称：{test_case.title}
预期结果：{test_case.expected}

【测试步骤】
{steps_text}

【执行历史】
{history_text}

【错误信息】
{error_message}

【严重程度判定标准】
- 一级（致命）：系统崩溃/核心功能完全失效/数据丢失（如登录功能无法使用、支付异常、数据库连接中断）
- 二级（严重）：主要功能异常/存在重大安全隐患（如数据未保存、越权访问、计算逻辑错误）
- 三级（一般）：次要功能异常/用户体验显著下降（如页面加载超时、输入校验缺失、显示异常）
- 四级（轻微）：优化建议/不影响使用的UI/文案问题（如颜色不对齐、提示语不友好、低分辨率显示错位）

【错误类型】
- 功能错误：功能无法正常工作
- 设计缺陷：设计不合理导致的问题
- 安全问题：存在安全隐患
- 系统错误：测试智能体自身的错误

请以 JSON 格式返回分析结果：
{{
    "error_type": "功能错误/设计缺陷/安全问题/系统错误",
    "severity_level": "一级/二级/三级/四级",
    "actual_result": "实际发生的结果描述",
    "result_feedback": "结合预期结果和实际结果的详细分析"
}}
"""
        return prompt
    
    @staticmethod
    def _extract_reproduce_steps_from_test_case(
        test_case: TestCase,
        execution_history: Dict[str, Any]
    ) -> list:
        """
        从测试用例中提取复现步骤，并标记失败的步骤
        
        Args:
            test_case: 测试用例对象
            execution_history: 执行历史数据
        
        Returns:
            复现步骤列表
        """
        reproduce_steps = []
        
        # 从测试用例中获取步骤
        try:
            test_steps = json.loads(test_case.steps) if test_case.steps else []
        except:
            test_steps = []
        
        if not test_steps:
            # 如果测试用例没有步骤，使用默认步骤
            reproduce_steps.append("步骤1：执行测试用例")
            reproduce_steps.append("步骤2：测试执行失败")
            return reproduce_steps
        
        # 找到失败的执行步骤和错误原因
        failed_execution_step, error_reason = BugAnalysisService._find_failed_step_with_reason(execution_history)
        
        print(f"[BugAnalysis] 失败的执行步骤: {failed_execution_step}, 错误原因: {error_reason}")
        
        # 将执行步骤映射到测试用例步骤
        failed_test_case_step = BugAnalysisService._map_execution_step_to_test_case_step(
            failed_execution_step, execution_history, test_steps
        )
        
        print(f"[BugAnalysis] 映射到测试用例步骤: {failed_test_case_step}")
        
        # 格式化测试用例中的步骤
        for i, step in enumerate(test_steps, 1):
            step_desc = f"步骤{i}：{step}"
            
            # 如果是失败的步骤，添加标记
            if failed_test_case_step is not None and i == failed_test_case_step:
                step_desc += " ❌"
                reproduce_steps.append(step_desc)
                # 在下一行添加错误信息
                if error_reason:
                    reproduce_steps.append(f"   执行错误：{error_reason}")
                else:
                    reproduce_steps.append(f"   执行错误：此步骤失败")
            elif failed_test_case_step is not None and i < failed_test_case_step:
                step_desc += " ✅"
                reproduce_steps.append(step_desc)
            else:
                reproduce_steps.append(step_desc)
        
        # 如果没有找到具体失败步骤，在最后添加说明
        if failed_test_case_step is None and execution_history:
            error_msg = execution_history.get('error', '')
            if error_msg:
                reproduce_steps.append(f"❌ 执行过程中遇到错误：{error_msg}")
        
        return reproduce_steps
    
    @staticmethod
    def _map_execution_step_to_test_case_step(
        failed_execution_step: Optional[int],
        execution_history: Dict[str, Any],
        test_steps: list
    ) -> Optional[int]:
        """
        将执行步骤映射到测试用例步骤
        
        由于 Agent 可能执行多个步骤（包括重试、额外操作等），
        需要通过分析动作类型来确定失败发生在测试用例的哪一步
        
        Args:
            failed_execution_step: 失败的执行步骤编号
            execution_history: 执行历史
            test_steps: 测试用例步骤列表
        
        Returns:
            测试用例步骤编号（从1开始）
        """
        if not failed_execution_step or not execution_history or not execution_history.get('steps'):
            return None
        
        steps = execution_history['steps']
        if failed_execution_step > len(steps):
            return None
        
        failed_step = steps[failed_execution_step - 1]
        
        # 分析失败步骤的动作类型
        actions = failed_step.get('actions', [])
        
        # 关键词映射：动作类型 -> 测试用例步骤关键词
        action_keywords = {
            'go_to_url': ['访问', '打开', '进入', '浏览器', '页面', 'url'],
            'input_text': ['输入', '填写', '账号', '密码', '用户名', '验证码'],
            'click_element': ['点击', '按钮', '登录', '提交', '确认'],
            'save_screenshot': ['截图', '保存', 'screenshot', '截取', '图片'],
            'done': ['完成', '结束']
        }
        
        # 检查失败步骤的动作
        for action in actions:
            for action_type, keywords in action_keywords.items():
                if action_type in action:
                    # 匹配测试用例步骤
                    for i, test_step in enumerate(test_steps, 1):
                        test_step_lower = test_step.lower()
                        # 检查测试步骤是否包含相关关键词
                        if any(keyword in test_step_lower for keyword in keywords):
                            print(f"[BugAnalysis] 动作 {action_type} 匹配到测试步骤 {i}: {test_step}")
                            return i
        
        # 如果无法通过动作类型匹配，尝试通过步骤数量估算
        # 假设执行步骤和测试步骤大致对应
        if len(test_steps) > 0:
            ratio = len(steps) / len(test_steps)
            estimated_step = min(int(failed_execution_step / ratio) + 1, len(test_steps))
            print(f"[BugAnalysis] 无法精确匹配，估算为测试步骤 {estimated_step}")
            return estimated_step
        
        return None
    
    @staticmethod
    def _save_screenshot_with_standard_name(
        temp_screenshot_path: str,
        bug_name: str,
        severity_level: str,
        error_type: str,
        duplicate_count: int
    ) -> str:
        """
        将临时截图移动到标准目录并按照规范命名
        
        命名格式: BUG+{BUG名称}+{严重程度}+{错误类型}+{重复数量}.png/pdf
        重复数量为0时不显示
        
        Args:
            temp_screenshot_path: 临时截图路径
            bug_name: Bug 名称
            severity_level: 严重程度
            error_type: 错误类型
            duplicate_count: 重复数量
        
        Returns:
            最终的截图路径
        """
        import os
        import shutil
        import re
        
        # 如果没有临时截图，返回空字符串
        if not temp_screenshot_path or not os.path.exists(temp_screenshot_path):
            print(f"[BugAnalysis] 未找到临时截图: {temp_screenshot_path}")
            return ''
        
        # 使用 PNG 扩展名
        ext = '.png'
        
        # 清理文件名中的非法字符
        safe_bug_name = re.sub(r'[<>:"/\\|?*]', '_', bug_name)
        safe_error_type = re.sub(r'[<>:"/\\|?*]', '_', error_type)
        
        # 构建文件名
        # 格式: BUG+{BUG名称}+{严重程度}+{错误类型}+{重复数量}.png
        if duplicate_count > 0:
            filename = f"BUG+{safe_bug_name}+{severity_level}+{safe_error_type}+{duplicate_count}.png"
        else:
            filename = f"BUG+{safe_bug_name}+{severity_level}+{safe_error_type}.png"
        
        # 目标目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_dir = os.path.join(base_dir, 'save_floder', 'bug_img')
        
        # 确保目标目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        # 目标文件路径
        target_path = os.path.join(target_dir, filename)
        
        try:
            # 移动文件
            shutil.move(temp_screenshot_path, target_path)
            print(f"[BugAnalysis] ✓ 截图已保存: {target_path}")
            return target_path
        except Exception as e:
            print(f"[BugAnalysis] ⚠️ 移动截图失败: {e}")
            # 如果移动失败，尝试复制
            try:
                shutil.copy2(temp_screenshot_path, target_path)
                print(f"[BugAnalysis] ✓ 截图已复制: {target_path}")
                return target_path
            except Exception as e2:
                print(f"[BugAnalysis] ❌ 复制截图也失败: {e2}")
                # 如果都失败，返回原路径
                return temp_screenshot_path
    
    @staticmethod
    def _extract_screenshot_path(execution_history: Dict[str, Any]) -> str:
        """
        从执行历史中提取截图路径
        
        Args:
            execution_history: 执行历史数据
        
        Returns:
            截图文件的完整路径，如果没有找到则返回空字符串
        """
        if not execution_history or not execution_history.get('steps'):
            return ''
        
        # 遍历所有步骤，查找 save_screenshot 动作
        for step in execution_history['steps']:
            actions = step.get('actions', [])
            for action in actions:
                # 检查是否是 save_screenshot 动作
                if 'save_screenshot' in action:
                    # 从结果中提取文件路径
                    results = step.get('results', [])
                    for result in results:
                        extracted_content = result.get('extracted_content', '')
                        
                        # 提取路径信息
                        # 格式: "Saved screenshot to /path/to/file.png"
                        if 'Saved screenshot to' in extracted_content:
                            path_part = extracted_content.split('Saved screenshot to')[-1].strip()
                            
                            import os
                            # 如果是绝对路径，直接返回
                            if os.path.isabs(path_part):
                                return path_part
                            # 如果是相对路径，转换为绝对路径
                            else:
                                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                                abs_path = os.path.abspath(os.path.join(base_dir, path_part))
                                return abs_path
        
        return ''
    
    @staticmethod
    def _find_failed_step(execution_history: Dict[str, Any]) -> Optional[int]:
        """
        从执行历史中找到失败的步骤编号
        
        Args:
            execution_history: 执行历史数据
        
        Returns:
            失败步骤的编号（从1开始），如果无法确定则返回 None
        """
        if not execution_history:
            return None
        
        # 如果有 steps 字段
        if execution_history.get('steps'):
            steps = execution_history['steps']
            
            # 检查最后一步是否成功
            if steps:
                last_step = steps[-1]
                
                # 检查是否有 done 动作且 success=false
                actions = last_step.get('actions', [])
                for action in actions:
                    if 'done' in action:
                        done_data = action['done']
                        if not done_data.get('success', True):
                            # 如果最后一步标记为失败，返回最后一步的编号
                            return len(steps)
                
                # 检查结果中是否有错误
                results = last_step.get('results', [])
                for result in results:
                    if not result.get('is_done', False) and result.get('error'):
                        return len(steps)
            
            # 如果 final_state 标记为失败
            final_state = execution_history.get('final_state', {})
            if not final_state.get('success', True):
                # 返回最后一步
                return len(steps) if steps else None
        
        # 如果有错误信息，返回第一步
        if execution_history.get('error'):
            return 1
        
        return None
    
    @staticmethod
    def _find_failed_step_with_reason(execution_history: Dict[str, Any]) -> tuple[Optional[int], str]:
        """
        从执行历史中找到失败的步骤编号和错误原因
        
        Args:
            execution_history: 执行历史数据
        
        Returns:
            (失败步骤的编号（从1开始），错误原因)，如果无法确定则返回 (None, '')
        """
        if not execution_history:
            print("[BugAnalysis] 没有执行历史数据")
            return None, ''
        
        error_reason = ''
        failed_step_index = None
        
        # 如果有 steps 字段
        if execution_history.get('steps'):
            steps = execution_history['steps']
            print(f"[BugAnalysis] 检查 {len(steps)} 个执行步骤...")
            
            # 从后往前遍历步骤，找到第一个失败的步骤
            for i in range(len(steps) - 1, -1, -1):
                step = steps[i]
                step_number = i + 1
                
                print(f"[BugAnalysis] 检查步骤 {step_number}...")
                
                # 1. 检查 evaluation 字段（最可靠的错误信息来源）
                evaluation = step.get('evaluation', '')
                print(f"[BugAnalysis]   - evaluation: {evaluation[:100] if evaluation else 'None'}")
                
                if evaluation:
                    # 检查是否包含失败关键词（注意：要排除"Success"相关的评价）
                    # 只有当 Verdict 明确为 Failed/Failure 时才认为是失败
                    if 'Verdict:' in evaluation:
                        verdict_part = evaluation.split('Verdict:')[1].strip().lower()
                        if any(keyword in verdict_part for keyword in ['fail', 'error', '失败', '错误']):
                            # 提取关键错误信息
                            # 例如："Clicked login button successfully, but received '密码错误' (Password Error) message."
                            import re
                            
                            # 动态提取错误原因
                            error_reason = BugAnalysisService._extract_error_reason(evaluation)
                            
                            failed_step_index = step_number
                            break
                
                # 2. 检查 done 动作
                actions = step.get('actions', [])
                for action in actions:
                    if 'done' in action:
                        done_data = action['done']
                        if not done_data.get('success', True):
                            error_reason = done_data.get('text', '') or done_data.get('reason', '')
                            failed_step_index = step_number
                            break
                
                if failed_step_index:
                    break
                
                # 3. 检查结果中的错误
                results = step.get('results', [])
                for result in results:
                    if not result.get('is_done', False):
                        error_msg = result.get('error', '')
                        if error_msg:
                            error_reason = error_msg
                            failed_step_index = step_number
                            break
                
                if failed_step_index:
                    break
            
            # 如果还没找到，检查 final_state
            if not failed_step_index:
                final_state = execution_history.get('final_state', {})
                if not final_state.get('success', True):
                    error_reason = final_state.get('reason', '') or final_state.get('message', '')
                    failed_step_index = len(steps) if steps else None
        
        # 如果有顶层错误信息
        if not failed_step_index and execution_history.get('error'):
            error_reason = execution_history.get('error', '')
            failed_step_index = 1
        
        return failed_step_index, error_reason
    
    @staticmethod
    def _extract_error_reason(evaluation: str) -> str:
        """
        动态提取错误原因
        
        使用正则表达式和关键词映射来提取错误信息，避免硬编码
        
        Args:
            evaluation: 评估文本
        
        Returns:
            提取的错误原因
        """
        import re
        
        # 定义错误类型映射（支持中英文和多种变体）
        ERROR_PATTERNS = [
            # 密码错误
            {
                'patterns': [r'密码错误', r'password\s*error', r'wrong\s*password', r'incorrect\s*password'],
                'reason': '密码错误'
            },
            # 用户名错误
            {
                'patterns': [r'用户名错误', r'username\s*error', r'wrong\s*username', r'incorrect\s*username', r'user\s*not\s*found'],
                'reason': '用户名错误'
            },
            # 验证码错误
            {
                'patterns': [r'验证码错误', r'captcha\s*error', r'wrong\s*captcha', r'incorrect\s*captcha', r'verification\s*code\s*error'],
                'reason': '验证码错误'
            },
            # 登录失败
            {
                'patterns': [r'登录失败', r'login\s*failed', r'authentication\s*failed', r'登录不成功'],
                'reason': '登录失败'
            },
            # 网络错误
            {
                'patterns': [r'网络错误', r'network\s*error', r'connection\s*error', r'timeout', r'超时'],
                'reason': '网络错误'
            },
            # 页面加载失败
            {
                'patterns': [r'页面.*?加载.*?失败', r'page.*?load.*?failed', r'加载超时', r'load.*?timeout'],
                'reason': '页面加载失败'
            },
            # 元素未找到
            {
                'patterns': [r'元素.*?未找到', r'element.*?not\s*found', r'找不到.*?元素', r'cannot\s*find\s*element'],
                'reason': '元素未找到'
            },
            # 权限错误
            {
                'patterns': [r'权限.*?错误', r'permission\s*denied', r'access\s*denied', r'unauthorized', r'无权限'],
                'reason': '权限错误'
            }
        ]
        
        evaluation_lower = evaluation.lower()
        
        # 遍历错误模式，找到第一个匹配的
        for error_config in ERROR_PATTERNS:
            for pattern in error_config['patterns']:
                if re.search(pattern, evaluation_lower, re.IGNORECASE):
                    return error_config['reason']
        
        # 如果没有匹配到预定义的错误类型，尝试提取引号中的错误信息
        quote_patterns = [
            r"['\"'](.*?)['\"]",  # 单引号或双引号
            r"「(.*?)」",  # 中文引号
            r"『(.*?)』"   # 中文书名号
        ]
        
        for pattern in quote_patterns:
            match = re.search(pattern, evaluation)
            if match:
                extracted = match.group(1).strip()
                if extracted and len(extracted) < 50:  # 避免提取过长的文本
                    return extracted
        
        # 尝试提取 Verdict 后的简短描述
        if 'Verdict:' in evaluation:
            verdict_text = evaluation.split('Verdict:')[1].strip()
            # 提取第一句话或前50个字符
            first_sentence = verdict_text.split('.')[0].split(',')[0]
            cleaned = first_sentence
            # 移除常见的失败关键词
            for keyword in ['Failed', 'Failure', 'failed', 'failure', 'Error', 'error']:
                cleaned = cleaned.replace(keyword, '')
            cleaned = cleaned.strip(' -:')
            if cleaned and len(cleaned) > 3:
                return cleaned[:50]
        
        # 默认返回
        return '执行失败'
    
    @staticmethod
    def get_bugs(
        db: Session,
        limit: int = 20,
        offset: int = 0,
        severity_level: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取 Bug 列表
        
        Args:
            db: 数据库会话
            limit: 每页数量
            offset: 偏移量
            severity_level: 严重程度筛选
            status: 状态筛选
        
        Returns:
            Bug 列表
        """
        query = db.query(BugReport)
        
        if severity_level:
            query = query.filter(BugReport.severity_level == severity_level)
        
        if status:
            query = query.filter(BugReport.status == status)
        
        total = query.count()
        bugs = query.order_by(BugReport.id.desc()).limit(limit).offset(offset).all()
        
        return {
            "success": True,
            "data": [
                {
                    "id": bug.id,
                    "bug_name": bug.bug_name,
                    "test_case_id": bug.test_case_id,
                    "location_url": bug.location_url,
                    "error_type": bug.error_type,
                    "severity_level": bug.severity_level,
                    "reproduce_steps": json.loads(bug.reproduce_steps) if bug.reproduce_steps else [],
                    "screenshot_path": bug.screenshot_path,
                    "result_feedback": bug.result_feedback,
                    "expected_result": bug.expected_result,
                    "actual_result": bug.actual_result,
                    "status": bug.status,
                    "created_at": bug.created_at.isoformat() if bug.created_at else None
                }
                for bug in bugs
            ],
            "total": total
        }
    
    @staticmethod
    def get_bug_by_id(db: Session, bug_id: int) -> Dict[str, Any]:
        """获取 Bug 详情"""
        bug = db.query(BugReport).filter(BugReport.id == bug_id).first()
        
        if not bug:
            return {
                "success": False,
                "message": "Bug 不存在"
            }
        
        return {
            "success": True,
            "data": {
                "id": bug.id,
                "bug_name": bug.bug_name,
                "test_case_id": bug.test_case_id,
                "test_result_id": bug.test_result_id,
                "location_url": bug.location_url,
                "error_type": bug.error_type,
                "severity_level": bug.severity_level,
                "reproduce_steps": json.loads(bug.reproduce_steps) if bug.reproduce_steps else [],
                "screenshot_path": bug.screenshot_path,
                "result_feedback": bug.result_feedback,
                "expected_result": bug.expected_result,
                "actual_result": bug.actual_result,
                "status": bug.status,
                "created_at": bug.created_at.isoformat() if bug.created_at else None,
                "updated_at": bug.updated_at.isoformat() if bug.updated_at else None
            }
        }
    
    @staticmethod
    def update_bug_status(db: Session, bug_id: int, status: str) -> Dict[str, Any]:
        """更新 Bug 状态"""
        bug = db.query(BugReport).filter(BugReport.id == bug_id).first()
        
        if not bug:
            return {
                "success": False,
                "message": "Bug 不存在"
            }
        
        bug.status = status
        db.commit()
        
        return {
            "success": True,
            "message": f"Bug 状态已更新为: {status}"
        }
