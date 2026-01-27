import os
import csv
import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import sys
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import TestCase, get_db
# MCP integration removed - using direct LLM if needed

load_dotenv()

SAVE_FOLDER_DIR = os.getenv('SAVE_FOLDER_DIR', '../save_floder')

# CSV template fields
TEMPLATE_FIELDS = [
    "module", "title", "precondition", "steps", "expected",
    "keywords", "priority", "case_type", "stage"
]


class TestCaseService:
    """Test case generation service"""
    
    @staticmethod
    async def generate_test_cases(
        requirement: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generate test cases based on requirements
        
        Args:
            requirement: User requirements or test points
            db: Database session
        
        Returns:
            Generated test case data and file path
        """
        try:
            # 直接使用 LLM API 生成测试用例
            from Api_request.llm_client import get_llm_client
            
            llm_client = get_llm_client()
            
            # 调用 LLM 生成测试用例（让模型根据需求复杂度自行决定生成数量）
            result = llm_client.generate_test_cases(
                requirement=requirement,
                priority="3"
            )
            
            if not result.get('success'):
                error_msg = result.get('message', 'Failed to generate test cases')
                print(f"[ERROR] LLM generation failed: {error_msg}")
                return {
                    "success": False,
                    "message": error_msg,
                    "test_cases": []
                }
            
            test_cases_data = result.get('test_cases', [])
            
            if not test_cases_data:
                print(f"[ERROR] No test cases returned from LLM")
                return {
                    "success": False,
                    "message": "No test cases generated",
                    "test_cases": []
                }
            
            # Save to database and CSV
            saved_cases = []
            csv_file_path = TestCaseService._save_to_csv(test_cases_data)
            
            for case_data in test_cases_data:
                # Save to database
                test_case = TestCase(
                    module=case_data.get('module', ''),
                    title=case_data.get('title', ''),
                    precondition=case_data.get('precondition', ''),
                    steps=json.dumps(case_data.get('steps', []), ensure_ascii=False),
                    expected=case_data.get('expected', ''),
                    keywords=case_data.get('keywords', ''),
                    priority=case_data.get('priority', '3'),
                    case_type=case_data.get('case_type', ''),
                    stage=case_data.get('stage', ''),
                    test_data=case_data.get('test_data', {}),
                    csv_file_path=csv_file_path
                )
                
                db.add(test_case)
                db.commit()
                db.refresh(test_case)
                
                saved_cases.append({
                    "id": test_case.id,
                    "module": test_case.module,
                    "title": test_case.title,
                    "precondition": test_case.precondition,
                    "steps": json.loads(test_case.steps),
                    "expected": test_case.expected,
                    "keywords": test_case.keywords,
                    "priority": test_case.priority,
                    "case_type": test_case.case_type,
                    "stage": test_case.stage,
                    "test_data": test_case.test_data,
                    "created_at": test_case.created_at.isoformat() if test_case.created_at else None
                })
            
            return {
                "success": True,
                "message": f"Successfully generated {len(saved_cases)} test cases",
                "test_cases": saved_cases,
                "csv_file_path": csv_file_path
            }
        
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"[ERROR] Exception in generate_test_cases: {str(e)}")
            print(error_traceback)
            return {
                "success": False,
                "message": f"Exception: {str(e)}",
                "test_cases": [],
                "error_details": error_traceback
            }
    
    @staticmethod
    def _save_to_csv(test_cases: List[Dict[str, Any]]) -> str:
        """
        Save test cases to CSV file
        
        Args:
            test_cases: Test case data list
        
        Returns:
            CSV file path
        """
        # Create directory
        os.makedirs(SAVE_FOLDER_DIR, exist_ok=True)
        
        # Generate filename: test_case_timestamp.csv
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"test_case_{timestamp}.csv"
        file_path = os.path.join(SAVE_FOLDER_DIR, filename)
        
        # Write CSV file
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            # Write header
            headers = [
                "Module", "Case Name", "Precondition", "Steps", "Expected",
                "Keywords", "Priority", "Case Type", "Stage"
            ]
            writer.writerow(headers)
            
            # Write data
            for case in test_cases:
                steps = case.get('steps', [])
                steps_str = '\n'.join([f"{i+1}. {step}" for i, step in enumerate(steps)])
                
                row = [
                    case.get('module', ''),
                    case.get('title', ''),
                    case.get('precondition', ''),
                    steps_str,
                    case.get('expected', ''),
                    case.get('keywords', ''),
                    case.get('priority', '3'),
                    case.get('case_type', ''),
                    case.get('stage', '')
                ]
                writer.writerow(row)
        
        return file_path
    
    @staticmethod
    def get_test_cases(
        db: Session,
        limit: int = 20,
        offset: int = 0,
        module: str = None,
        search: str = None,
        priority: str = None,
        case_type: str = None
    ) -> Dict[str, Any]:
        """
        Get test case list with filters
        
        Args:
            db: Database session
            limit: Number of records per page
            offset: Offset
            module: Filter by module name
            search: Search by case title
            priority: Filter by priority level
            case_type: Filter by case type
        
        Returns:
            Dict with data and total count
        """
        # 构建查询
        query = db.query(TestCase)
        
        # 应用筛选条件
        if module:
            query = query.filter(TestCase.module.like(f"%{module}%"))
        
        if search:
            query = query.filter(TestCase.title.like(f"%{search}%"))
        
        if priority:
            query = query.filter(TestCase.priority == priority)
        
        if case_type:
            query = query.filter(TestCase.case_type == case_type)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        cases = query.order_by(
            TestCase.id.desc()
        ).limit(limit).offset(offset).all()
        
        data = [
            {
                "id": case.id,
                "module": case.module,
                "title": case.title,
                "precondition": case.precondition,
                "steps": json.loads(case.steps) if case.steps else [],
                "expected": case.expected,
                "keywords": case.keywords,
                "priority": case.priority,
                "case_type": case.case_type,
                "stage": case.stage,
                "test_data": case.test_data,
                "created_at": case.created_at.isoformat() if case.created_at else None
            }
            for case in cases
        ]
        
        return {
            "data": data,
            "total": total
        }
    
    @staticmethod
    def get_test_case_by_id(
        db: Session,
        case_id: int
    ) -> Dict[str, Any]:
        """
        Get test case by ID
        
        Args:
            db: Database session
            case_id: Test case ID
        
        Returns:
            Test case data
        """
        case = db.query(TestCase).filter(TestCase.id == case_id).first()
        
        if not case:
            return None
        
        return {
            "id": case.id,
            "module": case.module,
            "title": case.title,
            "precondition": case.precondition,
            "steps": json.loads(case.steps) if case.steps else [],
            "expected": case.expected,
            "keywords": case.keywords,
            "priority": case.priority,
            "case_type": case.case_type,
            "stage": case.stage,
            "test_data": case.test_data,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "csv_file_path": case.csv_file_path
        }
    
    @staticmethod
    async def process_uploaded_file(
        filename: str,
        content: bytes,
        db: Session
    ) -> Dict[str, Any]:
        """
        处理上传的文件并生成测试用例
        
        Args:
            filename: 文件名
            content: 文件内容（字节）
            db: 数据库会话
        
        Returns:
            处理结果
        """
        try:
            file_ext = os.path.splitext(filename)[1].lower()
            
            # 解析文件内容
            if file_ext == '.txt' or file_ext == '.md':
                # 纯文本或Markdown
                text_content = content.decode('utf-8')
            elif file_ext == '.pdf':
                # PDF文件
                text_content = TestCaseService._extract_text_from_pdf(content)
            elif file_ext == '.docx':
                # Word 2007+
                text_content = TestCaseService._extract_text_from_docx(content)
            elif file_ext == '.doc':
                # Word 2003
                text_content = TestCaseService._extract_text_from_doc(content)
            else:
                return {
                    "success": False,
                    "message": f"不支持的文件格式: {file_ext}"
                }
            
            if not text_content or not text_content.strip():
                return {
                    "success": False,
                    "message": "文件内容为空或无法解析"
                }
            
            # 保存上传的文件
            upload_dir = os.path.join(SAVE_FOLDER_DIR, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            saved_filename = f"{timestamp}_{filename}"
            saved_path = os.path.join(upload_dir, saved_filename)
            
            with open(saved_path, 'wb') as f:
                f.write(content)
            
            print(f"[INFO] 文件已保存: {saved_path}")
            print(f"[INFO] 解析的文本内容长度: {len(text_content)} 字符")
            
            # 使用解析的文本内容生成测试用例
            result = await TestCaseService.generate_test_cases(
                requirement=text_content,
                db=db
            )
            
            if result.get('success'):
                result['uploaded_file'] = saved_path
                result['message'] = f"成功从文件 '{filename}' 生成 {len(result.get('test_cases', []))} 个测试用例"
            
            return result
        
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(f"[ERROR] 处理上传文件失败: {str(e)}")
            print(error_traceback)
            return {
                "success": False,
                "message": f"处理文件失败: {str(e)}",
                "error_details": error_traceback
            }
    
    @staticmethod
    def _extract_text_from_pdf(content: bytes) -> str:
        """从PDF提取文本"""
        try:
            import PyPDF2
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        except ImportError:
            return "错误：需要安装 PyPDF2 库。请运行: pip install PyPDF2"
        except Exception as e:
            return f"PDF解析错误: {str(e)}"
    
    @staticmethod
    def _extract_text_from_docx(content: bytes) -> str:
        """从DOCX提取文本"""
        try:
            from docx import Document
            docx_file = io.BytesIO(content)
            doc = Document(docx_file)
            
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return text.strip()
        except ImportError:
            return "错误：需要安装 python-docx 库。请运行: pip install python-docx"
        except Exception as e:
            return f"DOCX解析错误: {str(e)}"
    
    @staticmethod
    def _extract_text_from_doc(content: bytes) -> str:
        """从DOC提取文本"""
        try:
            import textract
            # textract 可以处理 .doc 文件
            text = textract.process(content).decode('utf-8')
            return text.strip()
        except ImportError:
            return "错误：需要安装 textract 库。请运行: pip install textract"
        except Exception as e:
            return f"DOC解析错误: {str(e)}。提示：.doc格式较老，建议转换为.docx格式"

    
    @staticmethod
    def update_test_case(
        db: Session,
        case_id: int,
        module: str,
        title: str,
        precondition: str,
        steps: List[str],
        expected: str,
        keywords: str,
        priority: str,
        case_type: str,
        stage: str
    ) -> Dict[str, Any]:
        """
        更新测试用例
        
        Args:
            db: 数据库会话
            case_id: 测试用例 ID
            module: 模块名称
            title: 用例标题
            precondition: 前置条件
            steps: 测试步骤列表
            expected: 预期结果
            keywords: 关键词
            priority: 优先级
            case_type: 用例类型
            stage: 适用阶段
        
        Returns:
            更新结果
        """
        try:
            # 查找测试用例
            case = db.query(TestCase).filter(TestCase.id == case_id).first()
            
            if not case:
                return {
                    "success": False,
                    "message": f"测试用例 ID {case_id} 不存在"
                }
            
            # 更新字段
            case.module = module
            case.title = title
            case.precondition = precondition
            case.steps = json.dumps(steps, ensure_ascii=False)
            case.expected = expected
            case.keywords = keywords
            case.priority = priority
            case.case_type = case_type
            case.stage = stage
            
            # 提交更改
            db.commit()
            db.refresh(case)
            
            return {
                "success": True,
                "message": "测试用例更新成功",
                "data": {
                    "id": case.id,
                    "module": case.module,
                    "title": case.title,
                    "precondition": case.precondition,
                    "steps": json.loads(case.steps) if case.steps else [],
                    "expected": case.expected,
                    "keywords": case.keywords,
                    "priority": case.priority,
                    "case_type": case.case_type,
                    "stage": case.stage,
                    "updated_at": case.updated_at.isoformat() if case.updated_at else None
                }
            }
        
        except Exception as e:
            db.rollback()
            import traceback
            error_trace = traceback.format_exc()
            print(f"[ERROR] 更新测试用例失败: {str(e)}")
            print(error_trace)
            return {
                "success": False,
                "message": f"更新测试用例失败: {str(e)}"
            }
