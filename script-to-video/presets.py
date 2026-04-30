"""风格预设配置：pv（光伏）/ ai（AI科技）/ general（通用）"""

PRESETS = {
    'pv': {
        # --- 视频参数 ---
        'resolution': '1080x1920',       # 竖屏 9:16，抖音/视频号
        'fps': 30,
        'subtitle_font_size': 52,
        'subtitle_color': 'white',
        'subtitle_position': 'bottom',   # bottom / center
        'subtitle_box': True,            # 半透明黑底
        # --- 配音参数 ---
        'voice': 'zh-CN-YunyangNeural',  # 成熟稳重男声
        'rate': '+15%',
        # --- LLM 润色参数 ---
        'role': '光伏/新能源创业者',
        'audience': '农村/城郊有屋顶的居民和工厂主',
        'hook_style': '钱、合同陷阱、真实案例、反常识认知',
        'tone': '成熟沉稳、可信赖，行业老手分享踩坑经验',
        'cta': '引导私信发送合同审查 / 免费咨询避坑问题',
        'domain_terms': '发电收益、并网、自发自用余电上网、屋顶租赁、EMC合同',
        # --- 示例脚本 ---
        'sample_script': """# 光伏屋顶租赁避坑

@全局:男声

花5万装光伏真的能回本吗？但签错合同，亏的可不止5万。

很多人觉得屋顶闲着也是闲着，租出去装光伏还能赚租金。但你知道租赁合同里最大的坑是什么吗？

有个业主签了三年合同，厂房拆迁的时候才发现——合同里写着拆除费由业主承担。一句话，几万块没了。

识别合同陷阱，看这三点就够了：设备归属、拆除责任、发电收益分成比例。

当然也有把钱赚到的，关键是签之前让懂行的人帮你把把关。把你的合同发给我，我免费帮你看有没有雷。"""
    },

    'ai': {
        # --- 视频参数 ---
        'resolution': '1920x1080',       # 横屏 16:9，B站/YouTube
        'fps': 30,
        'subtitle_font_size': 44,
        'subtitle_color': 'yellow',
        'subtitle_position': 'bottom',
        'subtitle_box': False,
        # --- 配音参数 ---
        'voice': 'zh-CN-YunxiNeural',    # 年轻男声
        'rate': '+18%',
        # --- LLM 润色参数 ---
        'role': '程序员/AI工具创业者',
        'audience': '对效率工具感兴趣的互联网用户和开发者',
        'hook_style': '圈内人视角、效率对比、反常识认知',
        'tone': '年轻直接、干货感强，像一个懂行的朋友在跟你聊天',
        'cta': '引导试用工具 / 关注获取更多AI实战教程',
        'domain_terms': 'API、自动化、prompt、工作流、效率提升',
        # --- 示例脚本 ---
        'sample_script': """# AI工具怎么真正用起来

@全局:男声

很多程序员用AI写代码，大部分人只用了它10%的能力。

我做了9年iOS开发，试过市面上几乎所有AI编程工具。说实话，大部分教程教的都是表面功夫。

真正提效的关键，不是AI能帮你写多少代码，而是你怎么把你的思路准确地告诉它。

三个技巧，让你的AI从实习生变高级工程师。最后一个直接省掉每天2小时。

想学的话评论区扣1，我整理一份我自己的AI工作流发你。"""
    },

    'general': {
        'resolution': '1920x1080',
        'fps': 30,
        'subtitle_font_size': 42,
        'subtitle_color': 'white',
        'subtitle_position': 'bottom',
        'subtitle_box': True,
        'voice': 'zh-CN-XiaoxiaoNeural',  # 女声
        'rate': '+18%',
        'role': '自媒体创作者',
        'audience': '泛兴趣用户',
        'hook_style': '好奇心、争议、提问',
        'tone': '自然口语化，亲和力强',
        'cta': '引导评论互动 / 关注获取更多内容',
        'domain_terms': '',
        'sample_script': """# 短视频口播示例

@全局:女声

你知道吗？最近我发现了一个很有意思的现象。

很多人每天都在做同一件事，但从来没想过为什么。

今天想跟你聊聊这个话题，可能会改变你的一些固有想法。

先说结论：你花时间的方式，就是你人生的样子。

觉得有道理的，评论区聊聊你的看法。"""
    }
}

# 音色别名映射（用户友好名 → Edge TTS 标准名）
VOICE_ALIASES = {
    '女声': 'zh-CN-XiaoxiaoNeural',
    '男声': 'zh-CN-YunyangNeural',
    '新闻男': 'zh-CN-YunjianNeural',
    '年轻男': 'zh-CN-YunxiNeural',
    'Xiaoxiao': 'zh-CN-XiaoxiaoNeural',
    'Yunyang': 'zh-CN-YunyangNeural',
    'Yunjian': 'zh-CN-YunjianNeural',
    'Yunxi': 'zh-CN-YunxiNeural',
    'Xiaoyi': 'zh-CN-XiaoyiNeural',
}


def get_preset(name: str) -> dict:
    """获取风格预设，不存在则返回 general"""
    return PRESETS.get(name, PRESETS['general'])


def list_presets() -> list:
    return list(PRESETS.keys())


def resolve_voice(voice_name: str) -> str:
    """解析音色名称为 Edge TTS 标准名"""
    return VOICE_ALIASES.get(voice_name, voice_name)
