#!/usr/bin/env python3
"""
Replicate图片生成测试脚本
测试FLUX.1模型生成视频封面/素材图片

使用方法:
    export REPLICATE_API_TOKEN='你的Token'
    python3 test_replicate.py
"""

import os
import sys
import time
import urllib.request
from pathlib import Path
from datetime import datetime
from replicate.exceptions import ReplicateError

def check_setup():
    """检查环境和配置"""
    print("="*60)
    print("🔍 环境检查")
    print("="*60)

    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要3.8+")
        return False
    print(f"✅ Python版本: {sys.version_info.major}.{sys.version_info.minor}")

    # 检查replicate库
    try:
        import replicate
        print("✅ replicate库已安装")
    except ImportError:
        print("❌ replicate库未安装")
        print("   运行: pip3 install replicate")
        return False

    # 检查API Token
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        print("❌ REPLICATE_API_TOKEN未设置")
        print("   运行: export REPLICATE_API_TOKEN='你的Token'")
        print("   获取Token: https://replicate.com/account/api-tokens")
        return False
    print(f"✅ API Token已设置 ({token[:10]}...)")

    return True

def test_flux_dev():
    """测试FLUX.1 [dev]模型"""

    import replicate

    print("\n" + "="*60)
    print("🎨 测试 FLUX.1 [dev] 模型")
    print("="*60)
    print("模型特点: 高质量，速度快，适合专业场景")
    print("成本: ~$0.03/张")
    print("-"*60)

    # 测试提示词（财经新闻风格）
    test_prompts = [
        {
            "name": "封面图-审计巨头",
            "prompt": "Cinematic financial news style, PricewaterhouseCoopers logo shattered like glass, red numbers 10 billion floating in the air, dark blue background with spotlight effects, professional business atmosphere, dramatic lighting, 8k quality, photorealistic"
        },
        {
            "name": "数据展示-金币堆叠",
            "prompt": "3D render of golden coins stacking up, showing 4.4 billion + 3.1 billion + 10 billion = 17.5 billion, financial chart background, blue and gold color scheme, clean professional style, 9:16 vertical composition, high detail"
        },
        {
            "name": "场景-股民维权",
            "prompt": "Silhouette of determined investors holding signs, courthouse in background, golden hour lighting, dramatic cinematic style, representing justice and rights protection, 9:16 vertical format, photorealistic, 8k"
        }
    ]

    output_dir = Path("test_output")
    output_dir.mkdir(exist_ok=True)

    results = []
    total_cost = 0

    for i, test in enumerate(test_prompts, 1):
        print(f"\n[{i}/{len(test_prompts)}] 生成: {test['name']}")
        print(f"提示词: {test['prompt'][:80]}...")

        start_time = time.time()

        try:
            # 检查限流
            if i > 1:
                wait_time = 10  # 新账号需要等待10秒避免429
                print(f"   ⏳ 等待{wait_time}秒避免限流...")
                time.sleep(wait_time)

            # 调用FLUX.1 dev模型
            output = replicate.run(
                "black-forest-labs/flux-dev",
                input={
                    "prompt": test['prompt'],
                    "aspect_ratio": "9:16",  # 竖屏视频比例
                    "output_format": "png",
                    "num_inference_steps": 50,
                    "guidance_scale": 3.5
                }
            )

            elapsed = time.time() - start_time

            # 下载图片 - 处理不同返回格式
            img_path = output_dir / f"test_{i:02d}_{test['name']}.png"

            # replicate输出可能是字符串URL或列表
            if isinstance(output, list) and len(output) > 0:
                image_url = output[0]
            elif isinstance(output, str):
                image_url = output
            else:
                raise ValueError(f"未知的输出格式: {type(output)}")

            urllib.request.urlretrieve(image_url, img_path)

            # 估算成本 (FLUX dev约$0.03/张)
            estimated_cost = 0.03
            total_cost += estimated_cost

            print(f"   ✅ 成功! ({elapsed:.1f}s)")
            print(f"   💾 保存: {img_path}")
            print(f"   💰 预估成本: ${estimated_cost:.3f}")

            results.append({
                "name": test['name'],
                "success": True,
                "path": str(img_path),
                "time": elapsed,
                "cost": estimated_cost
            })

            time.sleep(1)  # 避免限流

        except ReplicateError as e:
            print(f"   ❌ API错误: {e}")
            if "429" in str(e):
                print("   💡 提示: 新账号限流，需要添加支付方式或等待")
            results.append({
                "name": test['name'],
                "success": False,
                "error": str(e)
            })
        except Exception as e:
            print(f"   ❌ 失败: {e}")
            results.append({
                "name": test['name'],
                "success": False,
                "error": str(e)
            })

    return results, total_cost

def test_flux_schnell():
    """测试FLUX.1 [schnell]模型（更快更便宜）"""

    import replicate

    print("\n" + "="*60)
    print("⚡ 测试 FLUX.1 [schnell] 模型")
    print("="*60)
    print("模型特点: 速度更快，成本更低，质量略低于dev")
    print("成本: ~$0.003/张 (只有dev的1/10)")
    print("-"*60)

    test_prompt = "Professional business news graphic, stock market chart going up, green and blue colors, clean modern design, 9:16 vertical, high quality"

    print(f"\n生成测试图...")
    print(f"提示词: {test_prompt[:60]}...")

    start_time = time.time()

    try:
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": test_prompt,
                "aspect_ratio": "9:16",
                "output_format": "png"
            }
        )

        elapsed = time.time() - start_time

        output_dir = Path("test_output")
        img_path = output_dir / "test_schnell_speed_test.png"
        urllib.request.urlretrieve(output[0], img_path)

        print(f"   ✅ 成功! 仅用时 {elapsed:.1f}s")
        print(f"   💾 保存: {img_path}")
        print(f"   💰 预估成本: $0.003 (超便宜)")

        return True, 0.003

    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False, 0

def compare_models():
    """对比不同模型"""

    print("\n" + "="*60)
    print("📊 Replicate模型对比")
    print("="*60)

    models = [
        {
            "name": "FLUX.1 [dev]",
            "cost": "$0.03/张",
            "speed": "中等 (~10-20s)",
            "quality": "⭐⭐⭐⭐⭐ 最佳",
            "recommend": "精品内容"
        },
        {
            "name": "FLUX.1 [schnell]",
            "cost": "$0.003/张",
            "speed": "超快 (~2-5s)",
            "quality": "⭐⭐⭐⭐ 很好",
            "recommend": "日常快讯"
        },
        {
            "name": "SDXL",
            "cost": "$0.01/张",
            "speed": "快 (~5-10s)",
            "quality": "⭐⭐⭐ 良好",
            "recommend": "预算有限"
        }
    ]

    for m in models:
        print(f"\n{m['name']}:")
        print(f"   成本: {m['cost']}")
        print(f"   速度: {m['speed']}")
        print(f"   质量: {m['quality']}")
        print(f"   推荐: {m['recommend']}")

def main():
    """主函数"""

    print("="*60)
    print("🚀 Replicate图片生成测试")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查环境
    if not check_setup():
        print("\n❌ 环境检查失败，请修复后重试")
        sys.exit(1)

    # 测试FLUX dev
    results, total_cost = test_flux_dev()

    # 测试FLUX schnell
    schnell_success, schnell_cost = test_flux_schnell()
    total_cost += schnell_cost

    # 显示对比
    compare_models()

    # 总结
    print("\n" + "="*60)
    print("📋 测试总结")
    print("="*60)

    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)

    print(f"\n生成结果:")
    print(f"   成功: {success_count}/{total_count}")
    print(f"   失败: {total_count - success_count}/{total_count}")

    print(f"\n成本统计:")
    print(f"   本次测试花费: ${total_cost:.3f}")
    print(f"   预估月成本(30条/天): ${total_cost * 30:.2f}")

    print(f"\n文件位置:")
    print(f"   测试图片保存: {Path('test_output').absolute()}")

    if success_count > 0:
        print("\n✅ 测试完成！图片质量满意吗？")
        print("   满意 → 可以开始批量使用")
        print("   不满意 → 可以调整提示词或换模型")
    else:
        print("\n❌ 全部失败，请检查错误信息")

    print("\n" + "="*60)
    print("💡 下一步建议:")
    print("="*60)
    print("1. 查看生成的图片质量")
    print("2. 如果满意，可以开始用在hybrid_pipeline.py")
    print("3. 尝试修改提示词，测试不同风格")
    print("4. 对比FLUX dev和schnell的质量差异")

if __name__ == "__main__":
    main()
