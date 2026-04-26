#!/usr/bin/env python3
"""
Replicate API 直接调用测试（简化版）
使用requests直接调用REST API，绕过replicate库兼容性问题

使用方法:
    export REPLICATE_API_TOKEN='你的Token'
    python3 test_replicate_simple.py
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime


def check_setup():
    """检查环境"""
    print("="*60)
    print("🔍 环境检查")
    print("="*60)

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("❌ REPLICATE_API_TOKEN未设置")
        return None
    print(f"✅ API Token已设置")
    return token


def create_prediction(token: str, prompt: str, model: str = "flux-dev"):
    """创建图片生成任务"""

    # 模型版本映射
    models = {
        "flux-dev": "black-forest-labs/flux-dev",
        "flux-schnell": "black-forest-labs/flux-schnell"
    }

    version = models.get(model, model)

    url = "https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }

    data = {
        "version": version,
        "input": {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "output_format": "png",
            "num_inference_steps": 50 if model == "flux-dev" else 4,
            "guidance_scale": 3.5
        }
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 429:
        print("   ⏳ 触发限流，等待10秒...")
        time.sleep(10)
        return create_prediction(token, prompt, model)

    response.raise_for_status()
    return response.json()


def get_prediction(token: str, prediction_id: str):
    """获取任务结果"""

    url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
    headers = {"Authorization": f"Token {token}"}

    while True:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        result = response.json()

        status = result.get("status")

        if status == "succeeded":
            return result
        elif status == "failed":
            raise Exception(f"生成失败: {result.get('error')}")
        elif status in ["starting", "processing"]:
            print("   ⏳ 生成中...", end="\r")
            time.sleep(1)
        else:
            raise Exception(f"未知状态: {status}")


def download_image(url: str, path: Path):
    """下载图片"""
    response = requests.get(url)
    response.raise_for_status()
    path.write_bytes(response.content)


def test_single_image(token: str, prompt: str, name: str, model: str = "flux-dev"):
    """测试单张图片生成"""

    print(f"\n生成: {name}")
    print(f"模型: {model}")
    print(f"提示词: {prompt[:60]}...")

    try:
        # 创建任务
        prediction = create_prediction(token, prompt, model)
        prediction_id = prediction["id"]

        print(f"   任务ID: {prediction_id[:20]}...")

        # 等待结果
        result = get_prediction(token, prediction_id)

        # 下载图片
        output_url = result["output"]
        if isinstance(output_url, list):
            output_url = output_url[0]

        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)

        img_path = output_dir / f"{name.replace(' ', '_')}.png"
        download_image(output_url, img_path)

        print(f"   ✅ 成功!")
        print(f"   💾 保存: {img_path}")

        return True

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False


def main():
    print("="*60)
    print("🚀 Replicate API 直接调用测试")
    print("="*60)

    # 检查环境
    token = check_setup()
    if not token:
        sys.exit(1)

    # 测试提示词
    test_cases = [
        {
            "name": "test_flux_schnell",
            "prompt": "Professional business news graphic, stock market chart going up with green arrows, modern clean design, dark blue background, cinematic lighting, 9:16 vertical format",
            "model": "flux-schnell"
        },
        {
            "name": "test_flux_dev",
            "prompt": "Cinematic financial news style, golden coins stacking up showing billions, professional business atmosphere, dramatic lighting, 8k quality, 9:16 vertical",
            "model": "flux-dev"
        }
    ]

    print("\n" + "="*60)
    print("🎨 开始测试图片生成")
    print("="*60)

    results = []
    for test in test_cases:
        success = test_single_image(token, test["prompt"], test["name"], test["model"])
        results.append((test["name"], success))
        time.sleep(2)  # 避免限流

    # 总结
    print("\n" + "="*60)
    print("📋 测试总结")
    print("="*60)

    success_count = sum(1 for _, s in results if s)
    print(f"\n成功: {success_count}/{len(results)}")

    for name, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {name}")

    if success_count > 0:
        print(f"\n图片已保存到: {Path('test_output').absolute()}")
        print("\n💡 查看生成的图片质量，满意后可以开始批量使用")
    else:
        print("\n❌ 全部失败，可能需要:")
        print("   1. 访问 https://replicate.com/account/billing 添加支付方式")
        print("   2. 检查API Token是否正确")


if __name__ == "__main__":
    main()
