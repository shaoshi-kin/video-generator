"""LLM 润色模块：原始口述 → 结构化口播稿"""

import os
import re
from datetime import datetime
from pathlib import Path

import requests

from presets import get_preset, resolve_voice

# LLM 提供商配置
PROVIDERS = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com',
        'model': 'deepseek-chat',
        'env_key': 'DEEPSEEK_API_KEY',
    },
    'kimi': {
        'base_url': 'https://api.moonshot.cn/v1',
        'model': 'moonshot-v1-8k',
        'env_key': 'KIMI_API_KEY',
    },
}

SYSTEM_PROMPT = """你是一位资深短视频口播脚本专家。用户提供了一段真实的个人经历/见闻，请将其润色为一篇适合 AI 配音的口播脚稿。

## 核心规则（必须严格遵守）

### 1. 保留所有事实细节
原文中的人名、地名、数字、金额、日期、事件经过必须原封保留。绝不编造、改写、或添加原文没有的信息。

### 2. 添加开头钩子
文章第一句必须是强钩子。根据素材选择合适的钩子类型：
- 争议型：「花5万装光伏，真的能回本吗？」
- 数据冲击型：「屋顶闲着也是闲着，一年却可能亏掉2万。」
- 反常识型：「签了这份合同，屋顶就不是你的了。」
- 提问型：「你知道租赁合同里最大的坑是什么吗？」
- 圈内人视角：「做了3年光伏，有些话我终于敢说了。」

### 3. 口语化改写
- 每句 15-25 字，适合一口气读完，长句必须拆短
- 用"你"代替"大家/观众朋友们"
- 删掉书面语废话："值得一提的是""众所周知""在某种程度上""与此同时"
- 适当加入口语词："说实话""其实""你知道吗""但关键是"

### 4. 结构要求
钩子 → 问题展开 → 核心信息 → 行动号召
每段 2-3 句话，段落之间空一行

### 5. 字数控制
{min_chars}-{max_chars} 个中文字符（约 60-90 秒朗读时长）。宁短勿长。

### 6. 结尾行动号召
最后一段必须有一个明确的行动引导。不要用空洞的"关注我"。

### 7. 输出格式
只输出润色后的脚稿正文。不要标题、不要"大家好"开场、不要"关注点赞"结尾、不要任何说明文字。
每段之间空一行。

## 风格设定
- 你的身份：{role}
- 目标受众：{audience}
- 钩子倾向：{hook_style}
- 语气要求：{tone}
- 行动号召：{cta}
- 专业术语（适度使用并解释）：{domain_terms}

## 用户提供的原始文稿
{raw_text}

请直接输出润色后的脚稿："""

TITLE_PROMPT = """根据以下口播脚稿，生成一个短视频标题（15字以内，吸引眼球但不标题党）。
只输出标题，不要其他内容。

脚稿：
{script}"""


def _get_api_config(provider: str, api_key: str = None, base_url: str = None, model: str = None) -> dict:
    """解析 API 配置"""
    p = PROVIDERS.get(provider, PROVIDERS['deepseek'])
    key = api_key or os.environ.get(p['env_key']) or os.environ.get('OPENAI_API_KEY')
    url = base_url or p['base_url']
    m = model or p['model']
    return {'api_key': key, 'base_url': url, 'model': m}


def _count_chars(text: str) -> int:
    """统计中文字符数（不含标点和空格）"""
    return len(re.findall(r'[一-鿿]', text))


def _generate_title(script: str, api_config: dict) -> str:
    """根据口播稿生成标题"""
    try:
        resp = requests.post(
            f"{api_config['base_url']}/chat/completions",
            headers={
                'Authorization': f"Bearer {api_config['api_key']}",
                'Content-Type': 'application/json',
            },
            json={
                'model': api_config['model'],
                'messages': [{'role': 'user', 'content': TITLE_PROMPT.format(script=script)}],
                'temperature': 0.7,
                'max_tokens': 50,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip().strip('"').strip("'")
    except Exception:
        pass
    return datetime.now().strftime('%Y%m%d 口播视频')


def polish(raw_text: str, style: str = 'general', voice: str = None,
           api_key: str = None, base_url: str = None, model: str = None,
           provider: str = 'deepseek', min_chars: int = 200, max_chars: int = 400) -> dict:
    """
    润色原始文稿为口播脚本。

    返回 dict: {'title': str, 'script': str, 'voice': str, 'char_count': int}
    """
    preset = get_preset(style)

    # 解析 API 配置
    api_config = _get_api_config(provider, api_key, base_url, model)
    if not api_config['api_key']:
        return {'error': f'未配置 API Key。请设置环境变量 {PROVIDERS[provider]["env_key"]} 或通过 --api-key 传入'}

    # 解析音色
    resolved_voice = voice or preset.get('voice', 'zh-CN-XiaoxiaoNeural')
    resolved_voice = resolve_voice(resolved_voice)

    # 构建 prompt
    prompt = SYSTEM_PROMPT.format(
        role=preset.get('role', '自媒体创作者'),
        audience=preset.get('audience', '泛兴趣用户'),
        hook_style=preset.get('hook_style', '通用吸引'),
        tone=preset.get('tone', '自然口语化'),
        cta=preset.get('cta', '引导互动'),
        domain_terms=preset.get('domain_terms', ''),
        min_chars=min_chars,
        max_chars=max_chars,
        raw_text=raw_text,
    )

    # 调用 LLM
    try:
        resp = requests.post(
            f"{api_config['base_url']}/chat/completions",
            headers={
                'Authorization': f"Bearer {api_config['api_key']}",
                'Content-Type': 'application/json',
            },
            json={
                'model': api_config['model'],
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 2000,
            },
            timeout=120,
        )

        if resp.status_code != 200:
            return {'error': f'LLM API 返回错误 ({resp.status_code}): {resp.text[:200]}'}

        polished = resp.json()['choices'][0]['message']['content'].strip()

        # 生成标题
        title = _generate_title(polished, api_config)

        # 添加 @全局 标记
        voice_name = '男声' if 'Yunyang' in resolved_voice else (
            '女声' if 'Xiao' in resolved_voice else '男声')
        full_script = f"# {title}\n\n@全局:{voice_name}\n\n{polished}\n"

        return {
            'title': title,
            'script': full_script,
            'voice': resolved_voice,
            'char_count': _count_chars(polished),
        }

    except requests.exceptions.ConnectionError:
        return {'error': f'无法连接到 {api_config["base_url"]}，请检查网络'}
    except requests.exceptions.Timeout:
        return {'error': 'LLM API 请求超时（120秒），请稍后重试'}
    except Exception as e:
        return {'error': f'润色失败: {str(e)}'}


def save_script(script: str, output_dir: Path) -> Path:
    """保存口播稿到项目目录"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = output_dir / 'script.md'
    # 备份旧稿
    if path.exists():
        backup = output_dir / f'script_backup_{timestamp}.md'
        path.rename(backup)
    path.write_text(script, encoding='utf-8')
    return path
