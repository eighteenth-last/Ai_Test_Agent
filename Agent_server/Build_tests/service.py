import os
import csv
import json
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import sys

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
            
            # 调用 LLM 生成测试用例
            result = llm_client.generate_test_cases(
                requirement=requirement,
                count=3,
                priority="high"
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
                    priority=case_data.get('priority', 'medium'),
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
                    case.get('priority', 'medium'),
                    case.get('case_type', ''),
                    case.get('stage', '')
                ]
                writer.writerow(row)
        
        return file_path
    
    @staticmethod
    def get_test_cases(
        db: Session,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get test case list
        
        Args:
            db: Database session
            limit: Number of records per page
            offset: Offset
        
        Returns:
            Test case list
        """
        cases = db.query(TestCase).order_by(
            TestCase.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return [
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