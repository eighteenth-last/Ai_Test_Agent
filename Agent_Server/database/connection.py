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
    security_status = Column(String(20), default='待测试', comment='安全测试状态: 待测试/通过/bug')
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
    tokens_input_total = Column(Integer, default=0, comment='总输入TOKEN')
    tokens_output_total = Column(Integer, default=0, comment='总输出TOKEN')
    request_count_total = Column(Integer, default=0, comment='总请求次数')
    request_count_today = Column(Integer, default=0, comment='今日请求次数')
    failure_count_total = Column(Integer, default=0, comment='总失败次数')
    last_failure_reason = Column(String(50), comment='最近失败原因')
    last_used_at = Column(DateTime, comment='最近使用时间')
    auto_switch_enabled = Column(Integer, default=1, comment='是否参与自动切换')
    status = Column(String(50), default='待命', comment='模型状态')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class TokenUsageLog(Base):
    """Token 使用日志表（按次记录）"""
    __tablename__ = 'token_usage_logs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_id = Column(Integer, nullable=False, comment='模型ID')
    model_name = Column(String(100), comment='模型名称')
    provider = Column(String(50), comment='供应商')
    prompt_tokens = Column(Integer, default=0, comment='输入Token')
    completion_tokens = Column(Integer, default=0, comment='输出Token')
    total_tokens = Column(Integer, default=0, comment='总Token')
    source = Column(String(50), comment='来源: chat/browser_use/oneclick/api_test')
    session_id = Column(Integer, comment='关联会话ID')
    success = Column(Integer, default=1, comment='是否成功')
    error_type = Column(String(50), comment='错误类型')
    duration_ms = Column(Integer, default=0, comment='耗时毫秒')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


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


class OneclickSession(Base):
    """一键测试会话表"""
    __tablename__ = 'oneclick_sessions'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    user_input = Column(Text, nullable=False, comment='用户输入的自然语言指令')
    status = Column(String(20), default='init', comment='会话状态')
    target_url = Column(String(500), comment='目标测试地址')
    login_info = Column(JSON, comment='登录信息')
    page_analysis = Column(JSON, comment='页面分析结果')
    generated_cases = Column(JSON, comment='LLM生成的测试用例')
    confirmed_cases = Column(JSON, comment='用户确认后的测试用例')
    execution_result = Column(JSON, comment='执行结果')
    report_id = Column(Integer, comment='关联报告ID')
    skill_ids = Column(JSON, comment='使用的Skills ID列表')
    messages = Column(JSON, comment='对话消息历史')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class TestEnvironment(Base):
    """测试环境配置表 — 存储被测系统的 URL、账号密码等"""
    __tablename__ = 'test_environments'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='环境名称（如：开发环境、测试环境）')
    base_url = Column(String(500), nullable=False, comment='系统首页URL')
    login_url = Column(String(500), comment='登录页URL（为空则与base_url相同）')
    username = Column(String(200), comment='登录账号')
    password = Column(String(200), comment='登录密码')
    extra_credentials = Column(JSON, comment='额外凭据（如验证码、token等）')
    description = Column(Text, comment='环境描述')
    is_default = Column(Integer, default=0, comment='是否为默认环境（0:否 1:是）')
    is_active = Column(Integer, default=1, comment='是否启用')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class SecurityScanTask(Base):
    """安全扫描任务表"""
    __tablename__ = 'security_scan_tasks'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    scan_type = Column(String(30), nullable=False, comment='扫描类型: web_scan/api_attack/dependency_scan/baseline_check')
    target = Column(String(500), nullable=False, comment='扫描目标URL或路径')
    status = Column(String(20), default='pending', comment='状态: pending/running/finished/failed/stopped')
    progress = Column(Integer, default=0, comment='进度百分比 0-100')
    config = Column(JSON, comment='扫描配置')
    risk_score = Column(Integer, comment='风险评分 0-100')
    risk_level = Column(String(10), comment='风险等级: A/B/C/D')
    vuln_summary = Column(JSON, comment='漏洞统计摘要')
    vulnerabilities = Column(LONGTEXT, comment='漏洞详情列表(JSON)')
    report_content = Column(LONGTEXT, comment='报告内容(Markdown/HTML)')
    error_message = Column(Text, comment='错误信息')
    start_time = Column(DateTime, comment='开始时间')
    end_time = Column(DateTime, comment='结束时间')
    duration = Column(Integer, comment='耗时(秒)')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class Skill(Base):
    """Skills管理表"""
    __tablename__ = 'skills'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    name = Column(String(100), nullable=False, comment='Skill名称')
    slug = Column(String(200), comment='Skill标识(owner/repo)')
    source = Column(String(200), nullable=False, comment='来源URL')
    version = Column(String(50), comment='版本')
    description = Column(Text, comment='描述')
    category = Column(String(50), comment='分类')
    content = Column(LONGTEXT, comment='Skill内容(Markdown)')
    config = Column(JSON, comment='配置信息')
    author = Column(String(100), comment='作者')
    is_active = Column(Integer, default=1, comment='是否启用')
    install_count = Column(Integer, default=0, comment='安装次数')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')



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
            'token_usage_logs': TokenUsageLog,
            'model_providers': ModelProvider,
            'contacts': Contact,
            'email_records': EmailRecord,
            'email_config': EmailConfig,
            'api_specs': ApiSpec,
            'api_spec_versions': ApiSpecVersion,
            'api_endpoints': ApiEndpoint,
            'oneclick_sessions': OneclickSession,
            'test_environments': TestEnvironment,
            'skills': Skill,
            'security_scan_tasks': SecurityScanTask
        }
        
        for table_name in tables_to_create:
            if table_name not in existing_tables:
                Base.metadata.tables[table_name].create(bind=engine, checkfirst=True)
                print(f"✓ 表 '{table_name}' 创建成功")
            else:
                print(f"✓ 表 '{table_name}' 已存在，跳过创建")

        # 自动迁移：为已有表添加缺失的列
        _upgrade_existing_tables(inspector)
        
        print("\n数据库初始化完成！")
    except Exception as e:
        print(f"数据库初始化出错：{str(e)}")
        raise


def _upgrade_existing_tables(inspector):
    """
    自动迁移：检查已有表是否缺少新增列，自动 ALTER TABLE 添加

    解决 SQLAlchemy create_all(checkfirst=True) 不会为已有表添加新列的问题
    """
    from sqlalchemy import text

    # 定义需要检查的新增列: (表名, 列名, SQL类型, 默认值)
    new_columns = [
        ('llm_models', 'tokens_input_total', 'INT DEFAULT 0', None),
        ('llm_models', 'tokens_output_total', 'INT DEFAULT 0', None),
        ('llm_models', 'request_count_total', 'INT DEFAULT 0', None),
        ('llm_models', 'request_count_today', 'INT DEFAULT 0', None),
        ('llm_models', 'failure_count_total', 'INT DEFAULT 0', None),
        ('llm_models', 'last_failure_reason', 'VARCHAR(50) DEFAULT NULL', None),
        ('llm_models', 'last_used_at', 'DATETIME DEFAULT NULL', None),
        ('llm_models', 'auto_switch_enabled', 'INT DEFAULT 1', None),
        ('execution_cases', 'security_status', "VARCHAR(20) DEFAULT '待测试'", None),
    ]

    with engine.connect() as conn:
        for table_name, col_name, col_type, _ in new_columns:
            try:
                existing_cols = [c['name'] for c in inspector.get_columns(table_name)]
                if col_name not in existing_cols:
                    sql = f"ALTER TABLE `{table_name}` ADD COLUMN `{col_name}` {col_type}"
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"  ✓ 已添加列 {table_name}.{col_name}")
            except Exception as e:
                print(f"  ⚠ 添加列 {table_name}.{col_name} 失败: {e}")


def get_db():
    """获取数据库会话（FastAPI依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
