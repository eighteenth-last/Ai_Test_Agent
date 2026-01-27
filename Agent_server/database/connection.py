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


# 数据库模型
class ExecutionCase(Base):
    """用例详情表 - 存储所有测试用例（替代原 test_cases 表）"""
    __tablename__ = 'execution_cases'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 用例标题，必填
    title = Column(String(200), nullable=False, comment='用例标题')
    # 所属模块名称
    module = Column(String(100), comment='所属模块')
    # 前置条件描述
    precondition = Column(Text, comment='前置条件')
    # 测试步骤，格式为JSON数组
    steps = Column(Text, nullable=False, comment='测试步骤（JSON格式）')
    # 预期结果
    expected = Column(Text, nullable=False, comment='预期结果')
    # 关键词标签
    keywords = Column(String(200), comment='关键词')
    # 用例类型：功能测试/接口测试/单元测试等
    case_type = Column(String(50), comment='用例类型')
    # 优先级：1-4级（1级最高，3级为默认）
    priority = Column(String(20), comment='优先级', default='3')
    # 适用测试阶段
    stage = Column(String(50), comment='适用阶段')
    # 测试数据JSON对象
    test_data = Column(JSON, comment='测试数据（JSON格式）')
    # 对应的CSV文件路径
    csv_file_path = Column(String(500), comment='CSV文件路径')
    # 创建时间，默认为当前时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间，每次更新时自动更新
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class ExecutionBatch(Base):
    """执行批次中间表 - 用例与批次的对应关系（纯映射表）"""
    __tablename__ = 'execution_batches'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 关联用例ID
    execution_case_id = Column(Integer, nullable=False, index=True, comment='用例ID')
    # 执行批次号
    batch = Column(String(50), nullable=False, index=True, comment='批次号')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class TestRecord(Base):
    """执行记录表 - 记录单条/批量执行的汇总信息"""
    __tablename__ = 'test_records'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 关联中间表ID
    batch_id = Column(Integer, nullable=False, index=True, comment='中间表ID（execution_batches.id）')
    # 关联用例ID（冗余字段，方便查询）
    test_case_id = Column(Integer, comment='关联用例ID')
    # 执行模式：单量/批量
    execution_mode = Column(String(20), default='单量', comment='执行模式（单量/批量）')
    # 执行的用例总数
    total_cases = Column(Integer, default=1, comment='用例总数')
    # 通过的用例数
    passed_cases = Column(Integer, default=0, comment='通过数')
    # 失败的用例数
    failed_cases = Column(Integer, default=0, comment='失败数')
    # 测试执行日志（汇总）
    execution_log = Column(LONGTEXT, comment='执行日志')
    # 测试结果状态：pass(全部通过)/fail(全部失败)/partial(部分通过)/error(错误)
    status = Column(String(20), comment='测试结果')
    # 错误信息或异常堆栈
    error_message = Column(LONGTEXT, comment='错误信息')
    # 测试执行时间
    executed_at = Column(DateTime, default=datetime.now, comment='执行时间')
    # 测试执行耗时，单位为秒
    duration = Column(Integer, comment='执行耗时（秒）')
    # 执行步数
    test_steps = Column(Integer, default=0, comment='执行步数')


# 保留 TestCase 作为别名，兼容旧代码
TestCase = ExecutionCase


# 保留 TestResult 作为别名，兼容旧代码
TestResult = TestRecord


class TestReport(Base):
    """测试报告表"""
    __tablename__ = 'test_reports'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 报告标题
    title = Column(String(200), nullable=False, comment='报告标题')
    # 测试统计摘要，JSON格式包含total/pass/fail/duration
    summary = Column(JSON, comment='测试统计摘要（JSON格式）')
    # 详细的报告内容
    details = Column(Text, comment='报告详细内容')
    # 报告文件的保存路径
    file_path = Column(String(500), comment='报告文件路径')
    # 报告格式：txt/html/markdown
    format_type = Column(String(20), comment='报告格式')
    # 总步数
    total_steps = Column(Integer, default=0, comment='总步数')
    # 报告生成时间
    created_at = Column(DateTime, default=datetime.now, comment='生成时间')


class BugReport(Base):
    """Bug报告表
    
    记录测试执行过程中发现的 Bug
    execution_mode 字段通过关联 test_records 表的 execution_mode 来显示
    """
    __tablename__ = 'bug_reports'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 关联的执行记录ID
    test_record_id = Column(Integer, comment='关联执行记录ID')
    # Bug名称（使用测试用例名称）
    bug_name = Column(String(200), nullable=False, comment='Bug名称')
    # 关联的测试用例ID
    test_case_id = Column(Integer, comment='关联测试用例ID')
    # 定位地址（出错的URL）
    location_url = Column(String(500), comment='定位地址')
    # 错误类型：功能错误/设计缺陷/安全问题/系统错误
    error_type = Column(String(50), nullable=False, comment='错误类型')
    # 严重程度：一级/二级/三级/四级
    severity_level = Column(String(20), nullable=False, comment='严重程度')
    # 复现步骤（JSON数组格式）
    reproduce_steps = Column(Text, nullable=False, comment='复现步骤（JSON格式）')
    # 失败截图路径
    screenshot_path = Column(String(500), comment='失败截图路径')
    # 结果反馈（LLM分析的实际结果vs预期结果）
    result_feedback = Column(Text, comment='结果反馈')
    # 预期结果
    expected_result = Column(Text, comment='预期结果')
    # 实际结果
    actual_result = Column(Text, comment='实际结果')
    # Bug状态：待处理/已确认/已修复/已关闭
    status = Column(String(20), default='待处理', comment='Bug状态')
    # 问题描述（包含具体的用例信息）
    description = Column(Text, comment='问题描述')
    # 测试类型（从用例继承）
    case_type = Column(String(50), comment='测试类型')
    # 执行模式：单量/批量（通过 test_record_id 关联 test_records 表获取）
    execution_mode = Column(String(20), default='单量', comment='执行模式')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class LLMModel(Base):
    """LLM模型配置表"""
    __tablename__ = 'llm_models'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 模型名称
    model_name = Column(String(100), nullable=False, comment='模型名称')
    # API密钥
    api_key = Column(String(500), nullable=False, comment='API密钥')
    # API基础URL
    base_url = Column(String(500), comment='API基础URL')
    # 模型供应商：使用model_providers表中的code值
    provider = Column(String(50), comment='模型供应商code')
    # 是否当前激活
    is_active = Column(Integer, default=0, comment='是否激活（0:否 1:是）')
    # 优先级：Priority 1/2/3
    priority = Column(Integer, default=1, comment='优先级')
    # 利用率百分比
    utilization = Column(Integer, default=100, comment='利用率百分比')
    # 总消耗TOKEN数
    tokens_used_total = Column(Integer, default=0, comment='总消耗TOKEN')
    # 今日消耗TOKEN数
    tokens_used_today = Column(Integer, default=0, comment='今日消耗TOKEN')
    # 模型状态：待命/Redis缓存
    status = Column(String(50), default='待命', comment='模型状态')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class ModelProvider(Base):
    """模型供应商表"""
    __tablename__ = 'model_providers'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 供应商名称
    name = Column(String(100), nullable=False, unique=True, comment='供应商名称')
    # 供应商代码（用于程序识别）
    code = Column(String(50), nullable=False, unique=True, comment='供应商代码')
    # 显示名称（用于界面显示）
    display_name = Column(String(100), nullable=False, comment='显示名称')
    # 默认 base_url（可选）
    default_base_url = Column(String(500), comment='默认API基础URL')
    # 是否启用
    is_active = Column(Integer, default=1, comment='是否启用（0:否 1:是）')
    # 排序顺序
    sort_order = Column(Integer, default=0, comment='排序顺序')
    # 备注
    description = Column(Text, comment='备注')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class Contact(Base):
    """联系人表"""
    __tablename__ = 'contacts'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 联系人姓名
    name = Column(String(100), nullable=False, comment='姓名')
    # 邮箱地址
    email = Column(String(200), nullable=False, comment='邮箱')
    # 角色：测试负责人/开发人员/产品经理等
    role = Column(String(50), comment='角色')
    # 是否自动接收BUG
    auto_receive_bug = Column(Integer, default=0, comment='自动接收BUG（0:否 1:是）')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


class EmailRecord(Base):
    """邮件发送记录表"""
    __tablename__ = 'email_records'
    
    # 主键ID，自动递增
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 邮件主题
    subject = Column(String(200), nullable=False, comment='邮件主题')
    # 收件人列表（JSON格式：[{"name": "张三", "email": "test@example.com"}]）
    recipients = Column(JSON, nullable=False, comment='收件人列表')
    # 发送状态：success/partial/failed
    status = Column(String(20), nullable=False, comment='发送状态')
    # 成功数量
    success_count = Column(Integer, default=0, comment='成功发送数量')
    # 失败数量
    failed_count = Column(Integer, default=0, comment='失败发送数量')
    # 总数量
    total_count = Column(Integer, nullable=False, comment='总接收人数')
    # 邮件类型：report/bug/custom
    email_type = Column(String(50), default='report', comment='邮件类型')
    # 邮件内容摘要
    content_summary = Column(Text, comment='邮件内容摘要')
    # Resend Email IDs（JSON数组）
    email_ids = Column(JSON, comment='Resend邮件ID列表')
    # 失败详情（JSON格式）
    failed_details = Column(JSON, comment='失败详情')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')


class EmailConfig(Base):
    """邮件发送配置表"""
    __tablename__ = 'email_config'
    
    # 主键ID
    id = Column(Integer, primary_key=True, autoincrement=True, comment='主键ID')
    # 配置名称（唯一）
    config_name = Column(String(50), unique=True, nullable=False, comment='配置名称')
    # 邮箱服务商类型：resend/aliyun
    provider = Column(String(20), default='resend', nullable=False, comment='邮箱服务商')
    # API Key（Resend）或 Access Key（阿里云）
    api_key = Column(String(200), nullable=False, comment='API Key/Access Key')
    # Secret Key（仅阿里云需要）
    secret_key = Column(String(200), comment='Secret Key（阿里云）')
    # 发件人邮箱
    sender_email = Column(String(200), nullable=False, comment='发件人邮箱')
    # 测试邮箱（用于测试模式）
    test_email = Column(String(200), comment='测试邮箱')
    # 是否启用测试模式（0:否 1:是）
    test_mode = Column(Integer, default=1, comment='测试模式（0:否 1:是）')
    # 是否为激活配置（0:否 1:是）
    is_active = Column(Integer, default=0, comment='是否激活（0:否 1:是）')
    # 备注说明
    description = Column(Text, comment='备注说明')
    # 创建时间
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    # 更新时间
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')


def init_db():
    """初始化数据库表
    
    使用SQLAlchemy的create_all方法创建不存在的表。
    如果表已存在，则不重复创建，直接跳过。
    """
    try:
        # 检查数据库连接
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # 需要创建的表
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
            'email_config': EmailConfig
        }
        
        # 仅创建不存在的表
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
    """获取数据库会话（FastAPI依赖注入）
    
    返回一个数据库会话，在请求完成后自动关闭连接。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()