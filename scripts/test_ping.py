#!/usr/bin/env python3
"""
測試 Llama.cpp 伺服器連線的簡易腳本

使用方法:
    python test_ping.py --host localhost --port 8080
"""

import requests
import json
import argparse
import sys


def test_health(host: str = "localhost", port: int = 8000) -> bool:
    """測試伺服器健康狀態"""
    try:
        url = f"http://{host}:{port}/health"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"✓ 伺服器健康檢查成功")
            return True
        else:
            print(f"✗ 伺服器回應異常 (HTTP {response.status_code})")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ 無法連接到伺服器 {host}:{port}")
        return False
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return False


def test_completion(host: str = "localhost", port: int = 8000) -> bool:
    """測試 Chat Completions API"""
    try:
        url = f"http://{host}:{port}/v1/chat/completions"
        payload = {
            "model": "default",
            "messages": [
                {"role": "system", "content": "你是木柵市場賣菜的陳阿姨，講話帶台灣國語。回答限制在50字以內。"},
                {"role": "user", "content": "你好，菜怎麼賣？"},
            ],
            "max_tokens": 100,
            "temperature": 0.7,
        }

        print("\n測試 Chat Completions 請求...")
        response = requests.post(url, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            print(f"✓ Chat 補全成功")
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                print(f"  陳阿姨回應: {content}")
            return True
        else:
            print(f"✗ API 回應異常 (HTTP {response.status_code})")
            print(f"  回應內容: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ 錯誤: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="測試 Llama.cpp 伺服器連線"
    )
    parser.add_argument("--host", default="localhost", help="伺服器主機名 (預設: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="伺服器埠號 (預設: 8000)")
    parser.add_argument("--full", action="store_true", help="執行完整測試")
    
    args = parser.parse_args()
    
    print(f"連接到 {args.host}:{args.port}\n")
    
    # 初始化健康檢查
    if not test_health(args.host, args.port):
        print("\n伺服器未啟動或無法連接")
        sys.exit(1)
    
    # 選項：完整測試
    if args.full:
        if not test_completion(args.host, args.port):
            sys.exit(1)
    
    print("\n✓ 所有測試通過！")
    sys.exit(0)


if __name__ == "__main__":
    main()
