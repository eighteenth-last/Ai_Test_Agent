#!/usr/bin/env python3
"""
扫描工具安装检测脚本

检测 nuclei 和 sqlmap 的实际安装路径
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

async def check_nuclei():
    """检测 Nuclei 安装"""
    print("🔍 检测 Nuclei 安装...")
    
    import subprocess
    
    # 动态获取Go路径
    go_paths = []
    try:
        result = subprocess.run(["go", "env", "GOPATH"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            gopath = result.stdout.strip()
            if gopath:
                go_paths.append(os.path.join(gopath, "bin"))
                print(f"   📁 Go GOPATH: {gopath}")
    except:
        pass
    
    # 添加常见Go安装路径
    go_paths.extend([
        "E:\\GoLang\\bin",
        "E:\\GoLang\\GoModulesCache\\bin", 
        "C:\\Go\\bin"
    ])
    
    # 可能的nuclei路径
    possible_paths = ["nuclei", "nuclei.exe"]
    
    # 添加Go路径下的nuclei
    for go_path in go_paths:
        if os.path.exists(go_path):
            print(f"   📁 检查Go目录: {go_path}")
            possible_paths.extend([
                os.path.join(go_path, "nuclei"),
                os.path.join(go_path, "nuclei.exe")
            ])
    
    # 检查系统PATH
    print("   检查系统PATH...")
    try:
        result = subprocess.run(["where", "nuclei"], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            path = result.stdout.strip().split('\n')[0]
            print(f"   ✅ 在PATH中找到: {path}")
            return path
    except:
        pass
    
    # 检查可能的路径
    print("   检查可能的安装路径...")
    for path in possible_paths:
        try:
            if os.path.exists(path):
                print(f"   ✅ 找到文件: {path}")
                # 测试是否可执行
                try:
                    result = subprocess.run([path, "-version"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"   ✅ 可执行，版本: {result.stdout.strip()}")
                        return path
                    else:
                        print(f"   ❌ 文件存在但无法执行")
                except Exception as e:
                    print(f"   ❌ 执行测试失败: {e}")
        except Exception as e:
            print(f"   ❌ 检查路径失败 {path}: {e}")
    
    print("   ❌ 未找到可用的 Nuclei")
    return None

async def check_sqlmap():
    """检测 SQLMap 安装"""
    print("\n🔍 检测 SQLMap 安装...")
    
    import sys
    import site
    
    # 动态获取Python路径
    python_paths = [
        sys.executable,  # 当前Python解释器
        "python",
        "python3"
    ]
    
    # 添加常见虚拟环境路径
    python_paths.extend([
        "E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\python.exe",
        "E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\Scripts\\python.exe"
    ])
    
    # 动态检测SQLMap脚本路径
    sqlmap_scripts = []
    
    # 检查当前Python环境的site-packages
    try:
        for site_dir in site.getsitepackages():
            sqlmap_path = os.path.join(site_dir, "sqlmap", "sqlmap.py")
            if os.path.exists(sqlmap_path):
                sqlmap_scripts.append(sqlmap_path)
                print(f"   📁 找到SQLMap脚本: {sqlmap_path}")
    except:
        pass
    
    # 测试Python和SQLMap组合
    for python_path in python_paths:
        try:
            print(f"   测试Python路径: {python_path}")
            
            # 检查Python是否可用
            result = subprocess.run([python_path, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                python_version = result.stdout.strip()
                print(f"   ✅ Python可用: {python_version}")
                
                # 测试SQLMap脚本
                for sqlmap_script in sqlmap_scripts:
                    try:
                        result = subprocess.run([python_path, sqlmap_script, "--version"], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            print(f"   ✅ SQLMap脚本可用: {result.stdout.strip()}")
                            return f"{python_path} + {sqlmap_script}"
                    except Exception as e:
                        print(f"   ❌ SQLMap脚本测试失败: {e}")
                
                # 测试模块方式
                try:
                    result = subprocess.run([python_path, "-m", "sqlmap", "--version"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        print(f"   ✅ SQLMap模块可用: {result.stdout.strip()}")
                        return f"{python_path} -m sqlmap"
                except Exception as e:
                    print(f"   ❌ SQLMap模块测试失败: {e}")
            else:
                print(f"   ❌ Python不可用: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"   ❌ 测试失败 {python_path}: {e}")
    
    # 检查是否直接安装了sqlmap
    print("   检查直接安装的sqlmap...")
    try:
        result = subprocess.run(["sqlmap", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"   ✅ 直接安装的SQLMap可用: {result.stdout.strip()}")
            return "sqlmap"
    except:
        pass
    
    print("   ❌ 未找到可用的 SQLMap")
    return None

async def main():
    """主函数"""
    print("=" * 60)
    print("🔧 扫描工具安装检测")
    print("=" * 60)
    
    # 检测Nuclei
    nuclei_path = await check_nuclei()
    
    # 检测SQLMap
    sqlmap_path = await check_sqlmap()
    
    print("\n" + "=" * 60)
    print("📋 检测结果总结")
    print("=" * 60)
    
    if nuclei_path:
        print(f"✅ Nuclei: {nuclei_path}")
    else:
        print("❌ Nuclei: 未找到")
        print("💡 安装建议:")
        print("   go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest")
        print("   或下载预编译版本到 E:\\GoLang\\GoModulesCache\\bin\\")
    
    if sqlmap_path:
        print(f"✅ SQLMap: {sqlmap_path}")
    else:
        print("❌ SQLMap: 未找到")
        print("💡 安装建议:")
        print("   E:\\Interpreter\\Python_Conda\\envs\\Ai_Test_Agent\\Scripts\\activate")
        print("   pip install sqlmapapi")
        print("   或 git clone https://github.com/sqlmapproject/sqlmap.git")
    
    print("\n🔧 配置建议:")
    if nuclei_path:
        print(f"   Nuclei路径: {nuclei_path}")
    if sqlmap_path:
        print(f"   SQLMap Python路径: {sqlmap_path}")
    
    return nuclei_path, sqlmap_path

if __name__ == "__main__":
    asyncio.run(main())