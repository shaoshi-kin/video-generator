# Python 3.11 无痛迁移指南

## 🎯 目标
- 保留现有 Python 3.9 工作流（完全不动）
- 创建 Python 3.11 并行环境（用于新功能）
- 两个环境互不干扰，自由切换

---

## 🚀 一键迁移（只需3分钟）

```bash
cd /Users/kingshaoshi/Desktop/claudeCode
./migrate_to_py311.sh
```

脚本会自动完成：
1. ✅ 检查现有环境
2. ✅ 安装 Python 3.11（通过Homebrew）
3. ✅ 创建虚拟环境 `venv311/`
4. ✅ 安装所有依赖（openai, edge-tts, replicate等）
5. ✅ 验证安装
6. ✅ 创建快捷脚本

---

## 📖 迁移后使用方式

### 方式一：激活环境（推荐日常使用）

```bash
cd /Users/kingshaoshi/Desktop/claudeCode

# 激活 Python 3.11 环境
source venv311/bin/activate

# 现在 python 命令就是 3.11 了
python smart_hybrid.py 1.md
python tts_simple.py --script "测试" --output voice.mp3

# 用完退出
deactivate
```

### 方式二：快捷脚本（单次运行）

```bash
cd /Users/kingshaoshi/Desktop/claudeCode

# 运行任意脚本（自动使用3.11）
./run_py311.sh smart_hybrid.py 1.md
./run_py311.sh tts_simple.py --script "文案" --output voice.mp3
```

### 方式三：直接指定路径

```bash
# 使用3.11
./venv311/bin/python smart_hybrid.py 1.md

# 使用3.9（原有方式）
python3.9 smart_hybrid.py 1.md
```

---

## 🔄 环境切换对比

| 场景 | 使用命令 | Python版本 |
|------|---------|-----------|
| 日常工作流 | `python3.9 xxx.py` | 3.9 |
| 新功能/配音 | `source venv311/bin/activate && python xxx.py` | 3.11 |
| 快速测试 | `./run_py311.sh xxx.py` | 3.11 |
| 系统全局 | `python3.11 xxx.py` | 3.11 |

---

## 🎙️ 立即测试配音功能

迁移完成后，测试Edge-TTS：

```bash
# 激活3.11环境
source venv311/bin/activate

# 生成测试配音
python tts_simple.py \
  --script "普华永道血赔10亿，审计巨头为恒大买单" \
  --output test_voice.mp3

# 播放试听
open test_voice.mp3  # macOS
# 或
afplay test_voice.mp3  # macOS命令行
```

---

## 📁 文件结构变化

```
claudeCode/
├── venv311/                    ← 新增: Python 3.11 环境
│   ├── bin/python              ← 3.11解释器
│   └── lib/python3.11/...      ← 安装的包
├── run_py311.sh                ← 新增: 快捷运行脚本
├── migrate_to_py311.sh         ← 迁移脚本（只用一次）
├── PYTHON311_README.md         ← 详细说明文档
│
├── smart_hybrid.py             ← 原文件（不变）
├── tts_simple.py               ← 新增: 配音脚本
└── ...                         ← 其他原文件
```

---

## ❓ 常见问题

### Q1: 升级会影响现有的视频生成工作流吗？
**A**: 不会。原有脚本和Python 3.9环境完全保留，不受影响。

### Q2: 如何确认当前使用的是3.11？
```bash
source venv311/bin/activate
python --version  # 应显示 Python 3.11.x
deactivate
```

### Q3: 安装失败了怎么办？
```bash
# 查看错误日志
./migrate_to_py311.sh 2>&1 | tee install.log

# 手动安装
brew install python@3.11
python3.11 -m venv venv311
source venv311/bin/activate
pip install openai requests edge-tts replicate
```

### Q4: 如何删除3.11环境？
```bash
rm -rf venv311/
rm run_py311.sh
# Python 3.11本身可以不删，不影响
```

### Q5: 以后每次都要激活环境吗？
**A**: 是的。但你可以把激活命令加入别名：
```bash
# 添加到 ~/.zshrc
echo 'alias py311="source /Users/kingshaoshi/Desktop/claudeCode/venv311/bin/activate"' >> ~/.zshrc
source ~/.zshrc

# 以后使用
py311  # 自动激活
python smart_hybrid.py 1.md
deactivate  # 退出
```

---

## ✅ 迁移检查清单

- [ ] 运行 `./migrate_to_py311.sh` 完成安装
- [ ] 测试 `source venv311/bin/activate && python --version`
- [ ] 测试配音 `python tts_simple.py --script "测试" --output test.mp3`
- [ ] 确认原有 `python3.9` 工作流正常
- [ ] 熟悉环境切换方式

---

## 🎯 下一步

迁移完成后，你就可以：

```bash
# 1. 生成视频方案（可以用3.9或3.11）
python3.9 smart_hybrid.py article.md

# 2. 生成AI配音（必须用3.11）
cd projects/2026-04-24_article_hybrid
source ../../venv311/bin/activate
python ../../tts_simple.py --from-project plan.json

# 3. 获得完整配音文件
ls 03_audio/*.mp3
```

---

**准备好开始迁移了吗？**

在终端运行：
```bash
cd /Users/kingshaoshi/Desktop/claudeCode
./migrate_to_py311.sh
```

遇到问题随时问我！
