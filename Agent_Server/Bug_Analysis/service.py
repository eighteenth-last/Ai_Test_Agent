"""
Bug 分析服务

作者: Ai_Test_Agent Team
"""
import json
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime


class BugAnalysisService:
    """Bug 分析服务"""
    
    @staticmethod
    async def analyze_bug_from_execution(
        test_case_id: int,
        test_record_id: int,
        execution_history: Dict[str, Any],
        error_message: str,
        db: Session,
        execution_mode: str = '单量'
    ) -> Optional[Dict[str, Any]]:
        """
        根据执行历史分析 Bug
        
        Args:
            test_case_id: 测试用例 ID
            test_record_id: 执行记录 ID
            execution_history: 执行历史
            error_message: 错误信息
            db: 数据库会话
            execution_mode: 执行模式
        
        Returns:
            Bug 分析结果
        """
        from database.connection import TestCase, BugReport
        
        try:
            # 获取测试用例
            test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
            if not test_case:
                return None
            
            # 构建分析提示
            analysis_prompt = f"""
测试用例: {test_case.title}
预期结果: {test_case.expected}
执行历史: {json.dumps(execution_history, ensure_ascii=False)[:2000]}
错误信息: {error_message}

请分析这个测试失败的原因，返回 JSON 格式:
{{
    "error_type": "错误类型（功能错误/设计缺陷/安全问题/系统错误）",
    "severity_level": "严重程度（一级/二级/三级/四级）",
    "actual_result": "实际结果描述",
    "result_feedback": "问题分析和建议"
}}
"""
            
            # 调用 LLM 分析
            from llm import get_llm_client
            
            llm_client = get_llm_client()
            result = llm_client.analyze_bug(analysis_prompt)
            
            if not result.get('success'):
                # 使用默认值
                bug_data = {
                    "error_type": "系统错误",
                    "severity_level": "二级",
                    "actual_result": error_message,
                    "result_feedback": "测试执行失败，需要人工分析"
                }
            else:
                bug_data = result.get('data', {})
            
            # 提取步骤信息
            steps = execution_history.get('steps', [])
            reproduce_steps = []
            for step in steps[-5:]:  # 最后5步
                if isinstance(step, dict):
                    reproduce_steps.append(step.get('thinking', step.get('url', '')))
            
            # 创建 Bug 报告
            bug_report = BugReport(
                test_record_id=test_record_id,
                bug_name=f"[Bug] {test_case.title}",
                test_case_id=test_case_id,
                location_url=execution_history.get('final_state', {}).get('url', ''),
                error_type=bug_data.get('error_type', '功能错误'),
                severity_level=bug_data.get('severity_level', '二级'),
                reproduce_steps=json.dumps(reproduce_steps, ensure_ascii=False),
                result_feedback=bug_data.get('result_feedback', ''),
                expected_result=test_case.expected,
                actual_result=bug_data.get('actual_result', error_message),
                status='待处理',
                description=f"测试用例 [{test_case.title}] 执行失败",
                case_type=test_case.case_type,
                execution_mode=execution_mode
            )
            
            db.add(bug_report)
            db.commit()
            db.refresh(bug_report)
            
            # 判断是否应该停止后续测试
            should_stop = bug_data.get('severity_level', '二级') == '一级'
            
            return {
                "bug_id": bug_report.id,
                "error_type": bug_report.error_type,
                "severity_level": bug_report.severity_level,
                "result_feedback": bug_report.result_feedback,
                "should_stop": should_stop
            }
        
        except Exception as e:
            import traceback
            print(f"[BugAnalysis] 分析失败: {str(e)}")
            print(traceback.format_exc())
            return None
    
    @staticmethod
    def get_bug_reports(
        db: Session,
        limit: int = 20,
        offset: int = 0,
        status: str = None,
        severity: str = None
    ) -> Dict[str, Any]:
        """获取 Bug 报告列表"""
        from database.connection import BugReport
        
        query = db.query(BugReport)
        
        if status:
            query = query.filter(BugReport.status == status)
        if severity:
            query = query.filter(BugReport.severity_level == severity)
        
        total = query.count()
        bugs = query.order_by(BugReport.id.desc()).limit(limit).offset(offset).all()
        
        data = [
            {
                "id": bug.id,
                "bug_name": bug.bug_name,
                "test_case_id": bug.test_case_id,
                "error_type": bug.error_type,
                "severity_level": bug.severity_level,
                "status": bug.status,
                "location_url": bug.location_url,
                "expected_result": bug.expected_result,
                "actual_result": bug.actual_result,
                "result_feedback": bug.result_feedback,
                "case_type": bug.case_type,
                "execution_mode": bug.execution_mode,
                "created_at": bug.created_at.isoformat() if bug.created_at else None
            }
            for bug in bugs
        ]
        
        return {"data": data, "total": total}
