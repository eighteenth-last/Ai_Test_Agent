import os
import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import TestReport, TestResult, TestCode
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
            
            # Parse test results
            results_data = []
            total = len(test_results)
            pass_count = 0
            fail_count = 0
            total_duration = 0
            
            for result in test_results:
                if result.status == 'pass':
                    pass_count += 1
                elif result.status == 'fail':
                    fail_count += 1
                
                total_duration += result.duration or 0
                
                # 尝试解析 execution_log (如果是 JSON 格式的 Agent 历史)
                log_content = result.execution_log
                try:
                    if log_content and (log_content.startswith('{') or log_content.startswith('[')):
                        log_content = json.loads(log_content)
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
            
            # Summary data
            summary = {
                "total": total,
                "pass": pass_count,
                "fail": fail_count,
                "duration": total_duration
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
            
            # Save to database
            test_report = TestReport(
                title=f"Test Report {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                summary=summary,
                details=final_content,
                file_path=file_path,
                format_type=final_format
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
        reports = db.query(TestReport).order_by(
            TestReport.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
            {
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "file_path": report.file_path,
                "format_type": report.format_type,
                "created_at": report.created_at.isoformat() if report.created_at else None
            }
            for report in reports
        ]
    
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
        report = db.query(TestReport).filter(TestReport.id == report_id).first()
        
        if not report:
            return {
                "success": False,
                "message": "Report not found"
            }
        
        return {
            "success": True,
            "data": {
                "id": report.id,
                "title": report.title,
                "summary": report.summary,
                "details": report.details,
                "file_path": report.file_path,
                "format_type": report.format_type,
                "created_at": report.created_at.isoformat() if report.created_at else None
            }
        }