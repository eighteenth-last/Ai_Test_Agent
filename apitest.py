"""
*@BelongsProject: Ai_Test_Agent
*@BelongsPackage: 
*@Author: 程序员Eighteen
*@CreateTime: 2026-03-04  10:01
*@Description: TODO
*@Version: 1.0
"""
from openai import OpenAI

# 直接写入测试 key（仅测试用）
api_key = "sk-bdizvndprpoykyssjfjfiizvgvntemsysnngfdhyasnrjgxv"

client = OpenAI(
    api_key=api_key,
    base_url="https://api.siliconflow.cn/v1"
)

# 测试文本
text = "登录页面包含用户名输入框、密码输入框和登录按钮"

# 调用 embedding
response = client.embeddings.create(
    model="Qwen/Qwen3-Embedding-4B",
    input=text
)

# 获取向量
embedding_vector = response.data[0].embedding

print("向量维度:", len(embedding_vector))
print("前10个向量值:", embedding_vector[:10])