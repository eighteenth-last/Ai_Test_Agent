"""
数据库连接和模型定义

作者: Ai_Test_Agent Team
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, JSON, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import LONGTEXT
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库连接配置
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'ai_test_agent')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


# ============================================
# 数据库模型定义
# ============================================

class ExecutionCase(Base):
    """用例详情表 - 存储所有测试用例"""
    __tablename__ = 'execution_cases'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    title = Column(String(200), nullable=False, comment='用例标题')
    module = Column(String(100), comment='所属模块')
    precondition = Column(Text, comment='前置条件')
    steps = Column(Text, nullable=False, comment='测试步骤（JSON格式）')
    expected = Column(Text, nullable=False, comment='预期结果')
    keywords = Column(String(200), comment='关键词')
    case_type = Column(String(50), comment='用例类型')
    priority = Column(String(20), comment='优先级', default='3')
    stage = Column(String(50), comment='适用阶段')
    test_data = Column(JSON, comment='测试数据（JSON格式）')
    csv_file_path = Column(String(500), comment='CSV文件路径')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class ExecutionBatch(Base):
    """执行批次中间表 - 用例与批次的对应关系"""
    __tablename__ = 'execution_batches'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    execution_case_id = Column(Integer, nullable=False, index=True, comment='用例ID')
    batch = Column(String(50), nullable=False, index=True, comment='批次号')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class TestRecord(Base):
    """执行记录表 - 记录单条/批量执行的汇总信息"""
    __tablename__ = 'test_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    batch_id = Column(Integer, nullable=False, index=True, comment='中间表ID')
    test_case_id = Column(Integer, comment='关联用例ID')
    execution_mode = Column(String(20), default='单量', comment='执行模式')
    total_cases = Column(Integer, default=1, comment='用例总数')
    passed_cases = Column(Integer, default=0, comment='通过数')
    failed_cases = Column(Integer, default=0, comment='失败数')
    execution_log = Column(LONGTEXT, comment='执行日志')
    status = Column(String(20), comment='测试结果')
    error_message = Column(LONGTEXT, comment='错误信息')
    executed_at = Column(DateTime, default=datetime.now, comment='执行时间')
    duration = Column(Integer, comment='执行耗时（秒）')
    test_steps = Column(Integer, default=0, comment='执行步数')


# 别名（兼容旧代码）
TestCase = ExecutionCase
TestResult = TestRecord


class TestReport(Base):
    """测试报告表"""
    __tablename__ = 'test_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    title = Column(String(200), nullable=False, comment='报告标题')
    summary = Column(JSON, comment='测试统计摘要')
    details = Column(Text, comment='报告详细内容')
    file_path = Column(String(500), comment='报告文件路径')
    format_type = Column(String(20), comment='报告格式')
    total_steps = Column(Integer, default=0, comment='总步数')
    created_at = Column(DateTime, default=datetime.now, comment='生成时间')


class BugReport(Base):
    """Bug报告表"""
    __tablename__ = 'bug_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    test_record_id = Column(Integer, comment='关联执行记录ID')
    bug_name = Column(String(200), nullable=False, comment='Bug名称')
    test_case_id = Column(Integer, comment='关联测试用例ID')
    location_url = Column(String(500), comment='定位地址')
    error_type = Column(String(50), nullable=False, comment='错误类型')
    severity_level = Column(String(20), nullable=False, comment='严重程度')
    reproduce_steps = Column(Text, nullable=False, comment='复现步骤')
    screenshot_path = Column(String(500), comment='失败截图路径')
    result_feedback = Column(Text, comment='结果反馈')
    expected_result = Column(Text, comment='预期结果')
    actual_result = Column(Text, comment='实际结果')
    status = Column(String(20), default='待处理', comment='Bug状态')
    description = Column(Text, comment='问题描述')
    case_type = Column(String(50), comment='测试类型')
    execution_mode = Column(String(20), default='单量', comment='执行模式')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class LLMModel(Base):
    """LLM模型配置表"""
    __tablename__ = 'llm_models'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    model_name = Column(String(100), nullable=False, comment='模型名称')
    api_key = Column(String(500), nullable=False, comment='API密钥')
    base_url = Column(String(500), comment='API基础URL')
    provider = Column(String(50), comment='模型供应商code')
    is_active = Column(Integer, default=0, comment='是否激活（0:否 1:是）')
    priority = Column(Integer, default=1, comment='优先级')
    utilization = Column(Integer, default=100, comment='利用率百分比')
    tokens_used_total = Column(Integer, default=0, comment='总消耗TOKEN')
    tokens_used_today = Column(Integer, default=0, comment='今日消耗TOKEN')
    status = Column(String(50), default='待命', comment='模型状态')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class ModelProvider(Base):
    """模型供应商表"""
    __tablename__ = 'model_providers'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    name = Column(String(100), nullable=False, unique=True, comment='供应商名称')
    code = Column(String(50), nullable=False, unique=True, comment='供应商代码')
    display_name = Column(String(100), nullable=False, comment='显示名称')
    default_base_url = Column(String(500), comment='默认API基础URL')
    is_active = Column(Integer, default=1, comment='是否启用')
    sort_order = Column(Integer, default=0, comment='排序顺序')
    description = Column(Text, comment='备注')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class Contact(Base):
    """联系人表"""
    __tablename__ = 'contacts'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='姓名')
    email = Column(String(200), nullable=False, comment='邮箱')
    role = Column(String(50), comment='角色')
    auto_receive_bug = Column(Integer, default=0, comment='自动接收BUG')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class EmailRecord(Base):
    """邮件发送记录表"""
    __tablename__ = 'email_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    subject = Column(String(200), nullable=False, comment='邮件主题')
    recipients = Column(JSON, nullable=False, comment='收件人列表')
    status = Column(String(20), nullable=False, comment='发送状态')
    success_count = Column(Integer, default=0, comment='成功发送数量')
    failed_count = Column(Integer, default=0, comment='失败发送数量')
    total_count = Column(Integer, nullable=False, comment='总接收人数')
    email_type = Column(String(50), default='report', comment='邮件类型')
    content_summary = Column(Text, comment='邮件内容摘要')
    email_ids = Column(JSON, comment='邮件ID列表')
    failed_details = Column(JSON, comment='失败详情')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class EmailConfig(Base):
    """邮件发送配置表"""
    __tablename__ = 'email_config'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    config_name = Column(String(50), unique=True, nullable=False, comment='配置名称')
    provider = Column(String(20), default='resend', nullable=False, comment='邮箱服务商')
    api_key = Column(String(200), nullable=False, comment='API Key')
    secret_key = Column(String(200), comment='Secret Key')
    sender_email = Column(String(200), nullable=False, comment='发件人邮箱')
    test_email = Column(String(200), comment='测试邮箱')
    test_mode = Column(Integer, default=1, comment='测试模式')
    is_active = Column(Integer, default=0, comment='是否激活')
    description = Column(Text, comment='备注说明')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class ApiSpec(Base):
    """接口文件索引表"""
    __tablename__ = 'api_specs'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    service_name = Column(String(100), comment='服务名称')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class ApiSpecVersion(Base):
    """接口文件版本表"""
    __tablename__ = 'api_spec_versions'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    spec_id = Column(Integer, nullable=False, comment='关联 api_specs.id')
    original_filename = Column(String(255), nullable=False, comment='原始文件名')
    minio_bucket = Column(String(100), nullable=False, comment='MinIO Bucket')
    minio_key = Column(String(500), nullable=False, comment='MinIO 对象 Key')
    file_hash = Column(String(64), nullable=False, comment='文件 SHA256')
    file_size = Column(Integer, default=0, comment='文件大小(字节)')
    etag = Column(String(200), comment='MinIO ETag')
    parse_summary = Column(Text, comment='解析摘要(用于 LLM 匹配)')
    endpoint_count = Column(Integer, default=0, comment='接口数量')
    parse_warnings = Column(JSON, comment='解析警告')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class ApiEndpoint(Base):
    """接口资产表"""
    __tablename__ = 'api_endpoints'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    spec_version_id = Column(Integer, nullable=False, comment='关联 api_spec_versions.id')
    method = Column(String(10), nullable=False, comment='HTTP 方法')
    path = Column(String(300), nullable=False, comment='接口路径')
    summary = Column(String(300), comment='接口摘要')
    description = Column(Text, comment='接口描述')
    params = Column(JSON, comment='参数定义')
    success_example = Column(JSON, comment='成功响应示例')
    error_example = Column(JSON, comment='错误响应示例')
    notes = Column(Text, comment='备注')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


# ============================================
# 数据库初始化和会话管理
# ============================================

def init_db():
    """初始化数据库表"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        tables_to_create = {
            'execution_cases': ExecutionCase,
            'execution_batches': ExecutionBatch,
            'test_records': TestRecord,
            'test_reports': TestReport,
            'bug_reports': BugReport,
            'llm_models': LLMModel,
            'model_providers': ModelProvider,
            'contacts': Contact,
            'email_records': EmailRecord,
            'email_config': EmailConfig,
            'api_specs': ApiSpec,
            'api_spec_versions': ApiSpecVersion,
            'api_endpoints': ApiEndpoint
        }
        
        for table_name in tables_to_create:
            if table_name not in existing_tables:
                Base.metadata.tables[table_name].create(bind=engine, checkfirst=True)
                print(f"✓ 表 '{table_name}' 创建成功")
            else:
                print(f"✓ 表 '{table_name}' 已存在，跳过创建")
        
        print("\n数据库初始化完成！")
    except Exception as e:
        print(f"数据库初始化出错：{str(e)}")
        raise


def get_db():
    """获取数据库会话（FastAPI依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
