"""
路由注册模块
"""
from fastapi import FastAPI

# 导入所有路由
from Build_Use_case.router import router as test_cases_router
from Execute_test.router import router as execute_router
from Build_Report.router import router as report_router
from Bug_Analysis.router import router as bug_router
from Model_manage.router import router as model_router
from Email_manage.router import router as email_router
from Contact_manage.router import router as contact_router
from Dashboard.router import router as dashboard_router
from Api_Spec.router import router as spec_router
from Api_Test.router import router as api_test_router
from OneClick_Test.router import router as oneclick_router
from Security_Test.router import router as security_router
from Page_Knowledge.router import router as knowledge_router
from Project_manage.router import router as project_platform_router
from Project_manage.platforms.jira.router import router as jira_router
from Project_manage.platforms.zentao.router import router as project_router
from Project_manage.case_template.router import router as case_template_router
from Project_manage.project_router import router as project_manage_router


def register_routes(app: FastAPI):
    """注册所有路由到应用"""
    app.include_router(test_cases_router)
    app.include_router(execute_router)
    app.include_router(report_router)
    app.include_router(bug_router)
    app.include_router(model_router)
    app.include_router(email_router)
    app.include_router(contact_router)
    app.include_router(dashboard_router)
    app.include_router(spec_router)
    app.include_router(api_test_router)
    app.include_router(oneclick_router)
    app.include_router(security_router)
    app.include_router(knowledge_router)
    app.include_router(project_platform_router)
    app.include_router(jira_router)
    app.include_router(project_router)
    app.include_router(case_template_router)
    app.include_router(project_manage_router)
