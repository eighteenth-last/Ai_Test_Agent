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
            reproduce_steps = BugAnalysisService._extract_reproduce_steps_from_test_case(
                test_case, execution_history
            )
            
            # 提取截图路径 - 从执行历史中查找 save_pdf 动作
            screenshot_path = BugAnalysisService._extract_screenshot_path(execution_history)
            
            # 保存 Bug 到数据库
            bug_report = BugReport(
                bug_name=test_case.title,
                test_case_id=test_case_id,
                test_result_id=test_result_id,
                location_url=location_url,
                error_type=bug_data.get('error_type', '系统错误'),
                severity_level=bug_data.get('severity_level', '一级'),
                reproduce_steps=json.dumps(reproduce_steps, ensure_ascii=False),
                screenshot_path=screenshot_path,
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
        
        # 判断在哪一步失败
        failed_step_index = BugAnalysisService._find_failed_step(execution_history)
        
        # 格式化测试用例中的步骤
        for i, step in enumerate(test_steps, 1):
            step_desc = f"步骤{i}：{step}"
            
            # 如果是失败的步骤，添加标记
            if failed_step_index is not None and i == failed_step_index:
                step_desc += " ❌ [此步骤失败]"
            elif failed_step_index is not None and i < failed_step_index:
                step_desc += " ✅"
            
            reproduce_steps.append(step_desc)
        
        # 如果没有找到具体失败步骤，在最后添加说明
        if failed_step_index is None and execution_history:
            error_msg = execution_history.get('error', '')
            if error_msg:
                reproduce_steps.append(f"❌ 执行过程中遇到错误：{error_msg}")
        
        return reproduce_steps
    
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
        
        # 遍历所有步骤，查找 save_pdf 动作
        for step in execution_history['steps']:
            actions = step.get('actions', [])
            for action in actions:
                # 检查是否是 save_pdf 动作
                if 'save_pdf' in action:
                    # 从结果中提取文件路径
                    results = step.get('results', [])
                    for result in results:
                        extracted_content = result.get('extracted_content', '')
                        # 提取路径信息，格式类似："Saved PDF to ../save_floder/bug_floder/xxx.pdf"
                        if 'Saved PDF to' in extracted_content:
                            # 提取路径部分
                            path_part = extracted_content.split('Saved PDF to')[-1].strip()
                            # 转换为绝对路径
                            import os
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
