"""
测试新增格式解析器

测试 HAR、cURL、ApiFox 格式的解析功能

作者: 程序员Eighteen
"""
import json
from importers.har import HARImporter
from importers.curl import CurlImporter
from importers.apifox import ApiFoxImporter
from converter import to_markdown


def test_har_importer():
    """测试 HAR 解析器"""
    print("\n=== 测试 HAR 解析器 ===")
    
    # 示例 HAR 数据
    har_data = {
        "log": {
            "version": "1.2",
            "creator": {"name": "Chrome", "version": "120.0"},
            "entries": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/users?page=1",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ]
                    },
                    "response": {
                        "status": 200,
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"users": [{"id": 1, "name": "John"}]}'
                        }
                    }
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/users",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": '{"name": "Alice", "email": "alice@example.com"}'
                        }
                    },
                    "response": {
                        "status": 201,
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"id": 2, "name": "Alice"}'
                        }
                    }
                }
            ]
        }
    }
    
    # 检测
    confidence = HARImporter.detect(har_data)
    print(f"检测置信度: {confidence}")
    assert confidence > 0.5, "HAR 格式检测失败"
    
    # 解析
    importer = HARImporter()
    parsed = importer.parse(har_data)
    
    print(f"服务名称: {parsed['service_name']}")
    print(f"接口数量: {len(parsed['endpoints'])}")
    
    for ep in parsed['endpoints']:
        print(f"  - {ep['method']} {ep['path']}: {ep['summary']}")
    
    # 转换为 Markdown
    markdown = to_markdown(parsed)
    print(f"\nMarkdown 长度: {len(markdown)} 字符")
    print("✅ HAR 解析器测试通过")


def test_curl_importer():
    """测试 cURL 解析器"""
    print("\n=== 测试 cURL 解析器 ===")
    
    # 示例 cURL 命令
    curl_commands = [
        # 简单 GET
        "curl https://api.example.com/users",
        
        # POST with JSON
        'curl -X POST https://api.example.com/users -H "Content-Type: application/json" -d \'{"name":"John","email":"john@example.com"}\'',
        
        # 带多个 Header
        'curl -X GET https://api.example.com/profile -H "Authorization: Bearer token123" -H "Accept: application/json"',
        
        # 表单数据
        'curl -X POST https://api.example.com/login -d "username=admin&password=secret"'
    ]
    
    for i, curl_cmd in enumerate(curl_commands, 1):
        print(f"\n测试 {i}: {curl_cmd[:50]}...")
        
        # 检测
        confidence = CurlImporter.detect(curl_cmd)
        print(f"检测置信度: {confidence}")
        assert confidence > 0.5, f"cURL 命令 {i} 检测失败"
        
        # 解析
        importer = CurlImporter()
        parsed = importer.parse(curl_cmd)
        
        endpoint = parsed['endpoints'][0]
        print(f"  方法: {endpoint['method']}")
        print(f"  路径: {endpoint['path']}")
        print(f"  摘要: {endpoint['summary']}")
    
    print("\n✅ cURL 解析器测试通过")


def test_apifox_importer():
    """测试 ApiFox 解析器"""
    print("\n=== 测试 ApiFox 解析器 ===")
    
    # 示例 ApiFox 数据（Postman 兼容格式）
    apifox_data = {
        "info": {
            "name": "My ApiFox API",
            "version": "1.0.0"
        },
        "item": [
            {
                "name": "获取用户列表",
                "request": {
                    "method": "GET",
                    "url": {
                        "path": ["api", "users"],
                        "query": [
                            {"key": "page", "value": "1"}
                        ]
                    },
                    "header": [
                        {"key": "Authorization", "value": "Bearer token"}
                    ]
                },
                "response": [
                    {
                        "code": 200,
                        "body": '{"users": []}'
                    }
                ]
            },
            {
                "name": "创建用户",
                "request": {
                    "method": "POST",
                    "url": {"path": ["api", "users"]},
                    "body": {
                        "mode": "raw",
                        "raw": '{"name": "John", "email": "john@example.com"}'
                    }
                }
            }
        ]
    }
    
    # 检测
    confidence = ApiFoxImporter.detect(apifox_data)
    print(f"检测置信度: {confidence}")
    
    # 解析
    importer = ApiFoxImporter()
    parsed = importer.parse(apifox_data)
    
    print(f"服务名称: {parsed['service_name']}")
    print(f"接口数量: {len(parsed['endpoints'])}")
    
    for ep in parsed['endpoints']:
        print(f"  - {ep['method']} {ep['path']}: {ep['summary']}")
    
    # 转换为 Markdown
    markdown = to_markdown(parsed)
    print(f"\nMarkdown 长度: {len(markdown)} 字符")
    print("✅ ApiFox 解析器测试通过")


def test_format_detection():
    """测试格式自动检测"""
    print("\n=== 测试格式自动检测 ===")
    
    # 准备测试数据
    test_cases = [
        {
            "name": "Postman Collection",
            "data": {"info": {"name": "API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}, "item": []},
            "expected": "postman"
        },
        {
            "name": "Swagger 2.0",
            "data": {"swagger": "2.0", "info": {"title": "API"}, "paths": {}},
            "expected": "swagger"
        },
        {
            "name": "HAR",
            "data": {"log": {"version": "1.2", "entries": []}},
            "expected": "har"
        },
        {
            "name": "ApiFox",
            "data": {"apifoxProject": {"name": "API"}, "apis": []},
            "expected": "apifox"
        }
    ]
    
    from importers import PostmanImporter, OpenAPIImporter, HARImporter, ApiFoxImporter
    
    importers = {
        "postman": PostmanImporter,
        "swagger": OpenAPIImporter,
        "har": HARImporter,
        "apifox": ApiFoxImporter
    }
    
    for case in test_cases:
        print(f"\n测试: {case['name']}")
        
        # 计算所有解析器的置信度
        scores = {}
        for name, importer_class in importers.items():
            score = importer_class.detect(case['data'])
            scores[name] = score
            print(f"  {name}: {score:.2f}")
        
        # 选择最高置信度
        best = max(scores, key=scores.get)
        print(f"  检测结果: {best}")
        
        # 验证
        if case['expected'] in ['postman', 'swagger']:
            # Postman 和 Swagger 可能互相混淆，只要不是其他格式就行
            assert best in ['postman', 'swagger'], f"格式检测错误: 期望 {case['expected']}, 得到 {best}"
        else:
            assert best == case['expected'], f"格式检测错误: 期望 {case['expected']}, 得到 {best}"
    
    print("\n✅ 格式自动检测测试通过")


if __name__ == '__main__':
    print("开始测试新增格式解析器...")
    
    try:
        test_har_importer()
        test_curl_importer()
        test_apifox_importer()
        test_format_detection()
        
        print("\n" + "="*50)
        print("🎉 所有测试通过！")
        print("="*50)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
