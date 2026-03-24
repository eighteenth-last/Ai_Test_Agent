"""
API 文档导入功能测试

测试 Postman 和 Swagger 格式的解析

作者: 程序员Eighteen
"""
import json
from importers import PostmanImporter, OpenAPIImporter
from converter import to_markdown


# 测试 Postman Collection
def test_postman():
    postman_data = {
        "info": {
            "name": "Test API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [
            {
                "name": "用户登录",
                "request": {
                    "method": "POST",
                    "url": "https://api.example.com/api/login",
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps({
                            "username": "test",
                            "password": "123456"
                        })
                    }
                },
                "response": [
                    {
                        "name": "Success",
                        "code": 200,
                        "body": json.dumps({
                            "code": 200,
                            "token": "xxx"
                        })
                    }
                ]
            }
        ]
    }
    
    importer = PostmanImporter()
    parsed = importer.parse(postman_data)
    markdown = to_markdown(parsed)
    
    print("=== Postman 解析结果 ===")
    print(f"服务名: {parsed['service_name']}")
    print(f"接口数: {len(parsed['endpoints'])}")
    print("\n=== Markdown 输出 ===")
    print(markdown)


# 测试 Swagger/OpenAPI
def test_swagger():
    swagger_data = {
        "swagger": "2.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0"
        },
        "paths": {
            "/api/login": {
                "post": {
                    "summary": "用户登录",
                    "parameters": [
                        {
                            "in": "body",
                            "name": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "username": {"type": "string"},
                                    "password": {"type": "string"}
                                }
                            }
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "成功",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "integer"},
                                    "token": {"type": "string"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    importer = OpenAPIImporter()
    parsed = importer.parse(swagger_data)
    markdown = to_markdown(parsed)
    
    print("\n\n=== Swagger 解析结果 ===")
    print(f"服务名: {parsed['service_name']}")
    print(f"接口数: {len(parsed['endpoints'])}")
    print("\n=== Markdown 输出 ===")
    print(markdown)


if __name__ == '__main__':
    test_postman()
    test_swagger()
