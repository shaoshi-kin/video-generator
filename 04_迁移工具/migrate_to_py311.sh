#!/bin/bash
# Python 3.11 无痛迁移脚本
# 保留3.9环境，创建3.11并行环境

set -e  # 遇到错误停止

echo "=========================================="
echo "🚀 Python 3.11 无痛迁移工具"
echo "=========================================="
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 当前目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📍 工作目录: $SCRIPT_DIR"
echo ""

# ============ 第1步: 检查现有环境 ============
echo "🔍 步骤1: 检查现有Python环境..."
echo "------------------------------------------"

echo "Python 3.9 版本:"
if command -v python3.9 &> /dev/null; then
    python3.9 --version
    echo -e "${GREEN}✓ Python 3.9 已安装${NC}"
else
    echo -e "${YELLOW}⚠ Python 3.9 未找到${NC}"
fi

echo ""
echo "Python 3.11 版本:"
if command -v python3.11 &> /dev/null; then
    python3.11 --version
    echo -e "${GREEN}✓ Python 3.11 已安装${NC}"
else
    echo -e "${YELLOW}⚠ Python 3.11 未安装，需要安装${NC}"
fi

echo ""

# ============ 第2步: 安装Python 3.11 ============
echo "📦 步骤2: 安装 Python 3.11..."
echo "------------------------------------------"

if ! command -v python3.11 &> /dev/null; then
    echo "正在通过 Homebrew 安装 Python 3.11..."
    if command -v brew &> /dev/null; then
        brew install python@3.11
        echo -e "${GREEN}✓ Python 3.11 安装完成${NC}"
    else
        echo -e "${RED}✗ 未找到 Homebrew，请先安装: https://brew.sh${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Python 3.11 已存在，跳过安装${NC}"
fi

echo ""

# ============ 第3步: 创建虚拟环境 ============
echo "🌟 步骤3: 创建 Python 3.11 虚拟环境..."
echo "------------------------------------------"

VENV_DIR="$SCRIPT_DIR/venv311"

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠ 虚拟环境已存在: $VENV_DIR${NC}"
    read -p "是否删除并重新创建? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        echo "已删除旧环境"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    python3.11 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
fi

echo ""

# ============ 第4步: 安装依赖 ============
echo "📦 步骤4: 安装依赖包..."
echo "------------------------------------------"

source "$VENV_DIR/bin/activate"

echo "升级 pip..."
pip install --upgrade pip -q

echo ""
echo "安装核心依赖..."

pip install openai -q
pip install requests -q
pip install edge-tts -q
pip install replicate -q

echo -e "${GREEN}✓ 依赖安装完成${NC}"

echo ""

# ============ 第5步: 验证安装 ============
echo "✅ 步骤5: 验证安装..."
echo "------------------------------------------"

echo "测试导入核心库..."
python -c "
import openai
import requests
import edge_tts
print('✓ openai: OK')
print('✓ requests: OK')
print('✓ edge_tts: OK')
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 所有依赖工作正常${NC}"
else
    echo -e "${RED}✗ 依赖测试失败${NC}"
    exit 1
fi

echo ""

# ============ 第6步: 创建快捷脚本 ============
echo "📝 步骤6: 创建快捷运行脚本..."
echo "------------------------------------------"

# 创建run_py311.sh
cat > "$SCRIPT_DIR/run_py311.sh" << 'EOF'
#!/bin/bash
# 使用 Python 3.11 运行脚本

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 激活虚拟环境
source "$SCRIPT_DIR/venv311/bin/activate"

# 运行传入的命令
python "$@"
EOF

chmod +x "$SCRIPT_DIR/run_py311.sh"

# 创建使用说明
cat > "$SCRIPT_DIR/PYTHON311_README.md" << EOF
# Python 3.11 环境使用指南

## 🎯 快速开始

### 方式1: 激活虚拟环境后使用

\`\`\`bash
cd $SCRIPT_DIR
source venv311/bin/activate

# 现在可以使用 python 命令
python smart_hybrid.py 1.md
python tts_simple.py --script "测试" --output test.mp3

deactivate  # 退出虚拟环境
\`\`\`

### 方式2: 使用快捷脚本

\`\`\`bash
cd $SCRIPT_DIR

# 运行任意Python脚本
./run_py311.sh smart_hybrid.py 1.md
./run_py311.sh tts_simple.py --script "文案" --output voice.mp3
\`\`\`

### 方式3: 直接使用Python 3.11路径

\`\`\`bash
$SCRIPT_DIR/venv311/bin/python smart_hybrid.py 1.md
\`\`\`

## 📊 环境对比

| 命令 | Python版本 | 用途 |
|------|-----------|------|
| \`python3.9\` | 3.9 | 原有工作流 |
| \`python3.11\` | 3.11 | 系统全局 |
| \`source venv311/bin/activate\` | 3.11 | 项目专用(推荐) |
| \`./run_py311.sh\` | 3.11 | 快捷方式 |

## 🔧 安装更多包

\`\`\`bash
source venv311/bin/activate
pip install <包名>
\`\`\`

## ❓ 常见问题

### 如何确认使用的是3.11?
\`\`\`bash
source venv311/bin/activate
python --version  # 应显示 Python 3.11.x
\`\`\`

### 想回到3.9怎么办?
\`\`\`bash
deactivate  # 退出虚拟环境
python3.9 script.py  # 使用3.9
\`\`\`

EOF

echo -e "${GREEN}✓ 快捷脚本创建完成${NC}"
echo ""

# ============ 第7步: 测试运行 ============
echo "🧪 步骤7: 测试运行..."
echo "------------------------------------------"

echo "测试 smart_hybrid.py --help..."
python smart_hybrid.py --help > /dev/null 2>&1 && echo -e "${GREEN}✓ smart_hybrid.py 正常${NC}" || echo -e "${YELLOW}⚠ smart_hybrid.py 有警告${NC}"

echo ""
echo "测试 tts_simple.py --help..."
python tts_simple.py --help > /dev/null 2>&1 && echo -e "${GREEN}✓ tts_simple.py 正常${NC}" || echo -e "${YELLOW}⚠ tts_simple.py 有警告${NC}"

echo ""

# ============ 完成 ============
echo "=========================================="
echo -e "${GREEN}✅ Python 3.11 迁移完成！${NC}"
echo "=========================================="
echo ""
echo "📁 环境位置: $VENV_DIR"
echo ""
echo "🚀 使用方法:"
echo ""
echo "1️⃣  激活环境后使用（推荐）:"
echo "   cd $SCRIPT_DIR"
echo "   source venv311/bin/activate"
echo "   python smart_hybrid.py 1.md"
echo "   python tts_simple.py --script '测试' --output test.mp3"
echo ""
echo "2️⃣  使用快捷脚本:"
echo "   ./run_py311.sh smart_hybrid.py 1.md"
echo ""
echo "3️⃣  查看详细说明:"
echo "   cat PYTHON311_README.md"
echo ""
echo "📌 重要提示:"
echo "   • 原有Python 3.9环境完全保留"
echo "   • 两个环境互不干扰"
echo "   • 可以在3.9和3.11之间自由切换"
echo ""
echo "🎉 现在可以开始使用Python 3.11了！"
echo ""

# 提示用户是否需要立即测试
echo -n "是否立即测试配音功能? (y/n): "
read -n 1 -r
echo
if [[ \$REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🎙️ 测试配音生成..."
    python tts_simple.py --script "测试Python 3.11环境，配音功能正常" --output test_py311.mp3
    if [ -f "test_py311.mp3" ]; then
        echo -e "${GREEN}✅ 测试成功! 文件已生成: test_py311.mp3${NC}"
        ls -lh test_py311.mp3
    fi
fi

echo ""
echo "完毕！"
