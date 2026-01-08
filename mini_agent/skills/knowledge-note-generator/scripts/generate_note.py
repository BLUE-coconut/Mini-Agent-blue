#!/usr/bin/env python3
"""知识笔记图生成脚本 - 使用 Banana API 生成知识笔记可视化图"""

import sys
import os
import asyncio
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# 加载环境变量
def load_env_manually(env_file_path):
    """手动读取 .env 文件并设置环境变量"""
    try:
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and value:
                        os.environ[key] = value
        return True
    except Exception:
        return False

# 尝试加载环境变量
possible_env_paths = [
    Path.cwd() / ".env",
    SCRIPT_DIR.parent.parent.parent.parent / ".env",
    SCRIPT_DIR / ".env",
]

try:
    from dotenv import load_dotenv
    for env_file in possible_env_paths:
        if env_file.exists() and env_file.is_file():
            try:
                load_dotenv(env_file)
                break
            except Exception:
                load_env_manually(env_file)
                break
except ImportError:
    for env_file in possible_env_paths:
        if env_file.exists() and env_file.is_file():
            load_env_manually(env_file)
            break

from banana_image_gen_tool import BananaImageGenTool

# 预设的知识笔记图样式模板
STYLE_TEMPLATES = {
    "mindmap": """知识点以思维导图形式呈现，中心主题突出，分支清晰，使用不同颜色区分层级，
连接线优雅流畅，整体布局平衡美观。使用微软雅黑字体，背景为浅色渐变。""",

    "card": """知识点以卡片形式排列，每个卡片包含标题和要点，
卡片之间有清晰的视觉层次，使用柔和的阴影效果，整体风格现代简洁。
使用微软雅黑字体，背景纯白或浅灰。""",

    "timeline": """知识点以时间线/流程图形式展示，从左到右或从上到下排列，
节点清晰标注，连接箭头指示顺序，适合展示步骤或发展过程。
使用微软雅黑字体，配色专业稳重。""",

    "hierarchy": """知识点以层级结构展示，金字塔或树状图形式，
层级关系一目了然，使用不同颜色和大小区分重要性。
使用微软雅黑字体，设计简洁大方。""",

    "infographic": """知识点以信息图形式呈现，融合图标、数据和文字，
视觉效果丰富但不杂乱，信息传达直观高效。
使用微软雅黑字体，配色鲜明有活力。"""
}

def build_prompt(topic: str, content: str, style: str, custom_style: str = None) -> str:
    """构建生成知识笔记图的prompt"""
    style_desc = custom_style if custom_style else STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["card"])

    prompt = f"""请生成一张专业的知识笔记图，要求如下：

【主题】{topic}

【内容要点】
{content}

【设计风格】
{style_desc}

【通用要求】
1. 所有文字使用微软雅黑字体（Microsoft YaHei），确保中英文清晰可读
2. 采用扁平化设计风格，现代简洁
3. 配色和谐专业，避免过于花哨
4. 布局合理，信息层次分明
5. 适合用于学习笔记、知识总结、PPT配图等场景

请确保图片质量高，文字清晰，整体美观专业。"""

    return prompt


async def main():
    parser = argparse.ArgumentParser(description="生成知识笔记图")
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help="笔记主题"
    )
    parser.add_argument(
        "--content",
        type=str,
        required=True,
        help="知识要点内容（多个要点用换行或分号分隔）"
    )
    parser.add_argument(
        "--style",
        type=str,
        default="card",
        choices=["mindmap", "card", "timeline", "hierarchy", "infographic"],
        help="图表样式: mindmap(思维导图), card(卡片), timeline(时间线), hierarchy(层级), infographic(信息图)"
    )
    parser.add_argument(
        "--custom-style",
        type=str,
        help="自定义样式描述（覆盖预设样式）"
    )
    parser.add_argument(
        "--aspect-ratio",
        type=str,
        default="16:9",
        choices=["1:1", "4:3", "16:9", "3:4", "9:16"],
        help="图像宽高比，默认 16:9"
    )
    parser.add_argument(
        "--image-size",
        type=str,
        default="2K",
        choices=["256", "512", "1K", "2K"],
        help="图像尺寸，默认 2K"
    )
    parser.add_argument(
        "--output-filename",
        type=str,
        help="输出文件名（不含扩展名）"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="knowledge_notes",
        help="输出目录，默认 knowledge_notes"
    )
    parser.add_argument(
        "--workspace-dir",
        type=str,
        help="工作目录，默认当前目录"
    )

    args = parser.parse_args()

    # 检查 API Key
    if not os.getenv("BANANA_API_KEY"):
        print("❌ 错误: 未找到 BANANA_API_KEY")
        print("\n请设置环境变量或在 .env 文件中配置")
        sys.exit(1)

    # 构建 prompt
    prompt = build_prompt(args.topic, args.content, args.style, args.custom_style)

    # 初始化工具
    workspace_dir = args.workspace_dir if args.workspace_dir else Path.cwd()
    tool = BananaImageGenTool(
        workspace_dir=str(workspace_dir),
        output_dir=args.output_dir
    )

    print(f"📝 主题: {args.topic}")
    print(f"🎨 样式: {args.style}")
    print(f"📐 尺寸: {args.image_size} ({args.aspect_ratio})")
    print("🔄 正在生成知识笔记图...")

    # 生成图片
    result = await tool.execute(
        prompt=prompt,
        aspect_ratio=args.aspect_ratio,
        image_size=args.image_size,
        output_filename=args.output_filename
    )

    if result["success"]:
        print(f"\n✅ 生成成功！")
        print(f"📁 保存位置: {result.get('path', result['content'])}")
    else:
        print(f"\n❌ 生成失败: {result.get('error', '未知错误')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
