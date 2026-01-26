import os
import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import TestReport, TestResult, TestCode, TestCase
# MCP integration removed - using direct formatting if needed

load_dotenv()

SAVE_FOLDER_DIR = os.getenv('SAVE_FOLDER_DIR', '../save_floder')


class TestReportService:
    """Test report generation service"""
    
    @staticmethod
    @staticmethod
    async def generate_report(
        test_result_ids: List[int],
        db: Session,
        format_type: str = "markdown"
    ) -> Dict[str, Any]:
        """
        Generate test report based on test results
        
        Args:
            test_result_ids: Test result ID list
            db: Database session
            format_type: Report format (txt/markdown/html)
        
        Returns:
            Generated report data and file path
        """
        try:
            # Get test results
            test_results = db.query(TestResult).filter(
                TestResult.id.in_(test_result_ids)
            ).all()
            
            if not test_results:
                print("[ERROR] No test results found for report generation")
                return {
                    "success": False,
                    "message": "No test results found"
                }
            
            # Parse test results and get test case info
            results_data = []
            total = len(test_results)
            pass_count = 0
            fail_count = 0
            total_duration = 0
            total_steps = 0  # 总步数
            test_case_title = None  # 用于存储测试用例标题
            
            for result in test_results:
                if result.status == 'pass':
                    pass_count += 1
                elif result.status == 'fail':
                    fail_count += 1
                
                total_duration += result.duration or 0
                
                # 获取测试用例信息
                if result.test_case_id and not test_case_title:
                    test_case = db.query(TestCase).filter(TestCase.id == result.test_case_id).first()
                    if test_case:
                        test_case_title = test_case.title
                
                # 尝试解析 execution_log (如果是 JSON 格式的 Agent 历史)
                log_content = result.execution_log
                try:
                    if log_content and (log_content.startswith('{') or log_content.startswith('[')):
                        log_data = json.loads(log_content)
                        log_content = log_data
                        # 从 execution_log 提取步数
                        if isinstance(log_data, dict):
                            if 'steps' in log_data and isinstance(log_data['steps'], list):
                                total_steps += len(log_data['steps'])
                            elif 'total_steps' in log_data:
                                total_steps += log_data['total_steps']
                            elif 'step_count' in log_data:
                                total_steps += log_data['step_count']
                except Exception:
                    pass  # 保持原样如果是普通文本或解析失败

                results_data.append({
                    "id": result.id,
                    "test_code_id": result.test_code_id,
                    "status": result.status,
                    "execution_log": log_content,
                    "screenshots": result.screenshots,
                    "error_message": result.error_message,
                    "duration": result.duration,
                    "executed_at": result.executed_at.isoformat() if result.executed_at else None
                })
            
            # Summary data - 包含状态、耗时和总步数
            summary = {
                "status": "通过" if pass_count == total else "失败",
                "duration": total_duration,
                "total_steps": total_steps
            }
            
            print(f"[INFO] Generating report for {total} test results (pass: {pass_count}, fail: {fail_count})")
            
            # 直接使用 LLM API 生成测试报告
            from Api_request.llm_client import get_llm_client
            
            llm_client = get_llm_client()
            
            # 调用 LLM 生成报告
            result = llm_client.generate_test_report(
                test_results=results_data,
                summary=summary,
                format_type="markdown"
            )
            
            print(f"[INFO] LLM result: {result.get('success')}")
            
            if not result.get('success'):
                error_msg = result.get('message', 'Failed to generate report')
                print(f"[ERROR] LLM generation failed: {error_msg}")
                return {
                    "success": False,
                    "message": error_msg
                }
            
            report_content = result.get('content', '')
            
            if not report_content:
                print("[ERROR] Empty report content received from LLM")
                return {
                    "success": False,
                    "message": "Empty report content"
                }
            
            
            # Markdown 转 HTML 处理
            final_content = report_content
            final_format = format_type
            
            if format_type == 'markdown':
                try:
                    import markdown
                    # 转换 Markdown 为 HTML，启用常用扩展
                    html_content = markdown.markdown(
                        report_content, 
                        extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists']
                    )
                    # 包装在样式容器中
                    final_content = f'<div class="markdown- report">{html_content}</div>'
                    final_format = 'html'  # 更新存储格式为 HTML
                except ImportError:
                    print("[Warning] markdown module not found, saving as raw markdown")
            
            # Save report file (still save original content to file if needed, or save html? Let's save what we put in DB)
            file_path = TestReportService._save_report_file(
                content=final_content,
                format_type=final_format
            )
            
            # Save to database - 使用测试用例标题作为报告标题
            report_title = test_case_title if test_case_title else f"Test Report {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            test_report = TestReport(
                title=report_title,
                summary=summary,
                details=final_content,
                file_path=file_path,
                format_type=final_format,
                total_steps=total_steps
            )
            
            db.add(test_report)
            db.commit()
            db.refresh(test_report)
            
            print(f"[INFO] Report saved successfully: {file_path}")
            
            return {
                "success": True,
                "message": "Test report generated successfully",
                "data": {
                    "id": test_report.id,
                    "title": test_report.title,
                    "summary": test_report.summary,
                    "details": test_report.details,
                    "file_path": test_report.file_path,
                    "format_type": test_report.format_type,
                    "created_at": test_report.created_at.isoformat() if test_report.created_at else None
                }
            }
        
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"[ERROR] Exception in generate_report: {str(e)}")
            print(error_traceback)
            return {
                "success": False,
                "message": f"Exception: {str(e)}",
                "error_details": error_traceback
            }
    
    @staticmethod
    def _save_report_file(
        content: str,
        format_type: str
    ) -> str:
        """
        Save report to file
        
        Args:
            content: Report content
            format_type: File format
        
        Returns:
            File path
        """
        # Create directory
        os.makedirs(SAVE_FOLDER_DIR, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = 'txt' if format_type == 'txt' else format_type
        filename = f"test_report_{timestamp}.{ext}"
        file_path = os.path.join(SAVE_FOLDER_DIR, filename)
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            if format_type == 'html':
                # Convert Markdown to HTML (simple conversion)
                html_content = TestReportService._markdown_to_html(content)
                f.write(html_content)
            else:
                f.write(content)
        
        return file_path
    
    @staticmethod
    def _markdown_to_html(markdown_content: str) -> str:
        """
        Convert Markdown to HTML (simple version)
        
        Args:
            markdown_content: Markdown content
        
        Returns:
            HTML content
        """
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px;
            line-height: 1.8;
            background-color: #f5f7fa;
        }}
        
        #content {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            color: #2c3e50;
            font-size: 32px;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #4CAF50;
        }}
        
        h2 {{
            color: #34495e;
            font-size: 24px;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-top: 20px;
        }}
        
        h3 {{
            color: #555;
            font-size: 20px;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        
        h4 {{
            color: #666;
            font-size: 18px;
            margin-top: 25px;
            margin-bottom: 12px;
        }}
        
        p {{
            margin: 15px 0;
            color: #333;
        }}
        
        ul, ol {{
            margin: 20px 0;
            padding-left: 30px;
        }}
        
        li {{
            margin: 10px 0;
            line-height: 1.8;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #e0e0e0;
            margin: 40px 0;
        }}
        
        blockquote {{
            background-color: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 20px 25px;
            margin: 25px 0;
            border-radius: 4px;
        }}
        
        code {{
            background-color: #f4f4f4;
            padding: 3px 8px;
            border-radius: 3px;
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 14px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 15px 20px;
            text-align: left;
        }}
        
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: 600;
        }}
        
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        
        tr:hover {{
            background-color: #f5f5f5;
        }}
        
        .pass {{
            color: #4CAF50;
            font-weight: bold;
        }}
        
        .fail {{
            color: #f44336;
            font-weight: bold;
        }}
        
        strong {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div id="content">
        {markdown_content}
    </div>
</body>
</html>
"""
        return html_template
    
    @staticmethod
    def get_reports(
        db: Session,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get test report list
        
        Args:
            db: Database session
            limit: Number of records per page
            offset: Offset
        
        Returns:
            Test report list
        """
        from database.connection import TestResult
        
        reports = db.query(TestReport).order_by(
            TestReport.id.desc()
        ).limit(limit).offset(offset).all()
        
        result = []
        for report in reports:
            # 尝试查找关联的测试结果（通过标题匹配）
            execution_log = None
            test_result = db.query(TestResult).join(
                TestCase, TestResult.test_case_id == TestCase.id
            ).filter(TestCase.title == report.title).order_by(
                TestResult.executed_at.desc()
            ).first()
            
            if test_result:
                execution_log = test_result.execution_log
            
            result.append({
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "file_path": report.file_path,
                "format_type": report.format_type,
                "total_steps": report.total_steps or 0,
                "execution_log": execution_log,
                "created_at": report.created_at.isoformat() if report.created_at else None
            })
        
        return result
    
    @staticmethod
    def get_report_by_id(
        report_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Get full test report details by ID
        
        Args:
            report_id: Report ID
            db: Database session
        
        Returns:
            Full report data including details/content
        """
        from database.connection import TestResult
        
        report = db.query(TestReport).filter(TestReport.id == report_id).first()
        
        if not report:
            return {
                "success": False,
                "message": "Report not found"
            }
        
        # 尝试查找关联的测试结果（通过标题匹配）
        execution_log = None
        test_result = db.query(TestResult).join(
            TestCase, TestResult.test_case_id == TestCase.id
        ).filter(TestCase.title == report.title).order_by(
            TestResult.executed_at.desc()
        ).first()
        
        if test_result:
            execution_log = test_result.execution_log
        
        return {
            "success": True,
            "data": {
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "details": report.details,
                "file_path": report.file_path,
                "format_type": report.format_type,
                "total_steps": report.total_steps or 0,
                "execution_log": execution_log,
                "created_at": report.created_at.isoformat() if report.created_at else None
            }
        }
    
    @staticmethod
    async def generate_mixed_report(
        report_ids: List[int],
        bug_report_ids: List[int],
        db: Session
    ) -> Dict[str, Any]:
        """
        生成综合评估报告（使用 LLM 分析）
        
        Args:
            report_ids: 运行测试报告 ID 列表
            bug_report_ids: Bug 报告 ID 列表（可选）
            db: Database session
        
        Returns:
            LLM 生成的综合分析报告
        """
        try:
            from Api_request.llm_client import LLMClient
            from database.connection import BugReport
            
            # 1. 获取所有选中的测试报告
            test_reports = db.query(TestReport).filter(
                TestReport.id.in_(report_ids)
            ).all()
            
            if not test_reports:
                return {
                    "success": False,
                    "message": "未找到选中的测试报告"
                }
            
            # 2. 获取 Bug 报告（如果有）
            bugs = []
            if bug_report_ids:
                bugs = db.query(BugReport).filter(
                    BugReport.id.in_(bug_report_ids)
                ).all()
            else:
                # 如果未指定，获取所有 Bug
                bugs = db.query(BugReport).limit(100).all()
            
            # 3. 整理测试数据
            test_data = []
            total_tests = 0
            pass_tests = 0
            fail_tests = 0
            total_duration = 0
            total_steps = 0
            
            for report in test_reports:
                try:
                    summary = json.loads(report.summary) if isinstance(report.summary, str) else report.summary
                except:
                    summary = {}
                
                report_total = summary.get('total', 0)
                report_pass = summary.get('pass', 0)
                report_fail = summary.get('fail', 0)
                report_duration = summary.get('duration', 0)
                
                total_tests += report_total
                pass_tests += report_pass
                fail_tests += report_fail
                total_duration += report_duration
                total_steps += report.total_steps or 0
                
                test_data.append({
                    "id": report.id,
                    "title": report.title,
                    "total": report_total,
                    "pass": report_pass,
                    "fail": report_fail,
                    "duration": report_duration,
                    "created_at": report.created_at.isoformat() if report.created_at else None
                })
            
            # 4. 整理 Bug 数据
            bug_data = []
            severity_stats = {"一级": 0, "二级": 0, "三级": 0, "四级": 0}
            
            for bug in bugs:
                if bug.severity_level in severity_stats:
                    severity_stats[bug.severity_level] += 1
                
                bug_data.append({
                    "id": bug.id,
                    "name": bug.bug_name,
                    "severity": bug.severity_level,
                    "error_type": bug.error_type,
                    "status": bug.status,
                    "location": bug.location_url,
                    "actual_result": bug.actual_result,
                    "expected_result": bug.expected_result
                })
            
            # 5. 构建 LLM 提示词
            pass_rate = round((pass_tests / total_tests * 100), 1) if total_tests > 0 else 0
            
            prompt = f"""请作为专业的测试分析师，对以下测试数据进行综合评估分析：

## 测试数据概览
- 总测试用例数：{total_tests}
- 通过数：{pass_tests}
- 失败数：{fail_tests}
- 通过率：{pass_rate}%
- 总执行时长：{total_duration}秒
- 总执行步数：{total_steps}
- 测试时间：{datetime.now().strftime('%Y年%m月%d日')}

## 详细测试报告
{json.dumps(test_data, ensure_ascii=False, indent=2)}

## Bug 分析
- 总 Bug 数：{len(bugs)}
- 一级（严重）：{severity_stats['一级']}个
- 二级（重要）：{severity_stats['二级']}个
- 三级（一般）：{severity_stats['三级']}个
- 四级（轻微）：{severity_stats['四级']}个

### Bug 详情
{json.dumps(bug_data[:10], ensure_ascii=False, indent=2)}

## 请提供以下内容：

1. **测试概要**（150-200字）
   - 简要描述本次测试的整体情况
   - 提及覆盖的主要功能模块
   - 说明测试周期和执行情况

2. **质量评估**
   - 根据通过率给出质量评级（优秀/良好/一般/较差）
   - 分析通过率和 Bug 数量的关系
   - 指出主要的质量问题

3. **AI 分析结论**（200-300字）
   - 深入分析测试结果揭示的问题
   - 评估系统稳定性和可靠性
   - 针对严重 Bug 给出优先级建议
   - 提供改进建议和下一步行动建议

请用专业、客观的语言，提供有洞察力的分析。输出格式为 JSON：
{{
  "summary": "测试概要文字",
  "quality_rating": "优秀/良好/一般/较差",
  "pass_rate": {pass_rate},
  "bug_count": {len(bugs)},
  "duration": "{total_duration // 60}min {total_duration % 60}s",
  "conclusion": "AI 分析结论文字"
}}
"""
            
            # 6. 调用 LLM 生成分析
            print("[MixedReport] 正在调用 LLM 生成综合分析...")
            
            llm_client = LLMClient()
            messages = [
                {"role": "system", "content": "你是一位专业的测试分析师，擅长从测试数据中提炼关键信息和洞察。"},
                {"role": "user", "content": prompt}
            ]
            
            llm_result = llm_client.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            if not llm_result:
                # 如果 LLM 调用失败，返回基础统计数据
                print("[MixedReport] LLM 调用失败，返回基础统计数据")
                return {
                    "success": True,
                    "data": {
                        "summary": f"本次测试共执行 {total_tests} 个测试用例，通过率 {pass_rate}%，发现 {len(bugs)} 个缺陷。",
                        "quality_rating": "良好" if pass_rate >= 80 else "一般",
                        "pass_rate": pass_rate,
                        "bug_count": len(bugs),
                        "duration": f"{total_duration // 60}min {total_duration % 60}s",
                        "conclusion": f"整体测试结果{'良好' if pass_rate >= 80 else '需要改进'}，建议关注严重级别的 Bug。"
                    }
                }
            
            # 7. 解析 LLM 返回结果
            try:
                # 尝试从返回结果中提取 JSON
                llm_text = llm_result if isinstance(llm_result, str) else str(llm_result)
                
                # 查找 JSON 块
                import re
                json_match = re.search(r'\{[\s\S]*\}', llm_text)
                if json_match:
                    analysis_result = json.loads(json_match.group())
                else:
                    # 如果没有找到 JSON，使用默认值
                    analysis_result = {
                        "summary": llm_text[:200] if len(llm_text) > 200 else llm_text,
                        "quality_rating": "良好" if pass_rate >= 80 else "一般",
                        "pass_rate": pass_rate,
                        "bug_count": len(bugs),
                        "duration": f"{total_duration // 60}min {total_duration % 60}s",
                        "conclusion": llm_text[200:] if len(llm_text) > 200 else "系统运行稳定。"
                    }
            except Exception as e:
                print(f"[MixedReport] 解析 LLM 结果失败: {e}")
                analysis_result = {
                    "summary": f"本次测试共执行 {total_tests} 个测试用例。",
                    "quality_rating": "良好" if pass_rate >= 80 else "一般",
                    "pass_rate": pass_rate,
                    "bug_count": len(bugs),
                    "duration": f"{total_duration // 60}min {total_duration % 60}s",
                    "conclusion": llm_result if isinstance(llm_result, str) else "测试完成。"
                }
            
            print("[MixedReport] 综合报告生成成功")
            return {
                "success": True,
                "data": analysis_result
            }
            
        except Exception as e:
            import traceback
            print(f"[MixedReport] 生成综合报告失败: {e}")
            print(traceback.format_exc())
            return {
                "success": False,
                "message": f"生成综合报告失败: {str(e)}"
            }
    
    @staticmethod
    async def send_report_to_contacts(
        report_content: Dict[str, Any],
        contact_ids: List[int],
        db: Session
    ) -> Dict[str, Any]:
        """
        发送综合评估报告给指定联系人
        """
        try:
            from database.connection import Contact
            from Email_manage.service import EmailService
            
            contacts = db.query(Contact).filter(Contact.id.in_(contact_ids)).all()
            
            if not contacts:
                return {
                    "success": False,
                    "message": "未找到指定的联系人"
                }
            
            subject = f"测试综合评估报告 - {datetime.now().strftime('%Y年%m月%d日')}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: 'Microsoft YaHei', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                        background-color: #f5f5f5;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 30px;
                        border-radius: 10px;
                        margin-bottom: 30px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                    }}
                    .metrics {{
                        display: grid;
                        grid-template-columns: repeat(4, 1fr);
                        gap: 15px;
                        margin: 30px 0;
                    }}
                    .metric-card {{
                        background: white;
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                        border-left: 4px solid #667eea;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .metric-value {{
                        font-size: 28px;
                        font-weight: bold;
                        color: #667eea;
                        margin: 10px 0;
                    }}
                    .metric-label {{
                        font-size: 12px;
                        color: #6c757d;
                        text-transform: uppercase;
                    }}
                    .section {{
                        background: white;
                        padding: 25px;
                        border-radius: 8px;
                        margin-bottom: 20px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .section h2 {{
                        color: #667eea;
                        margin-top: 0;
                        border-bottom: 2px solid #667eea;
                        padding-bottom: 10px;
                    }}
                    .conclusion {{
                        background: #f0f7ff;
                        padding: 20px;
                        border-radius: 8px;
                        border-left: 4px solid #667eea;
                        white-space: pre-wrap;
                    }}
                    .footer {{
                        text-align: center;
                        color: #6c757d;
                        font-size: 12px;
                        margin-top: 40px;
                        padding-top: 20px;
                        border-top: 1px solid #dee2e6;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎯 测试综合评估报告</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">
                        生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}
                    </p>
                </div>
                
                <div class="section">
                    <h2>📋 测试概要</h2>
                    <p>{report_content.get('summary', '暂无摘要')}</p>
                </div>
                
                <div class="metrics">
                    <div class="metric-card">
                        <div class="metric-label">质量评级</div>
                        <div class="metric-value">{report_content.get('quality_rating', '-')}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">通过率</div>
                        <div class="metric-value">{report_content.get('pass_rate', 0)}%</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Bug 数量</div>
                        <div class="metric-value" style="color: #dc3545;">{report_content.get('bug_count', 0)}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">执行时长</div>
                        <div class="metric-value" style="color: #17a2b8; font-size: 20px;">{report_content.get('duration', '-')}</div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>🤖 AI 分析结论</h2>
                    <div class="conclusion">
                        {report_content.get('conclusion', '暂无结论')}
                    </div>
                </div>
                
                <div class="footer">
                    <p>此邮件由御策天检自动化测试平台自动发送</p>
                    <p>如有疑问，请联系测试团队</p>
                </div>
            </body>
            </html>
            """
            
            result = EmailService.send_email(
                contact_ids=contact_ids,
                subject=subject,
                html_content=html_content,
                email_type='report',
                db=db
            )
            
            return result
            
        except Exception as e:
            import traceback
            print(f"[SendReport] 发送报告失败: {e}")
            print(traceback.format_exc())
            return {
                "success": False,
                "message": f"发送报告失败: {str(e)}"
            }

