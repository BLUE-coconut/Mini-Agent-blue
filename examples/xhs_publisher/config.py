"""配置管理"""

from pathlib import Path


# 获取项目根目录（当前文件所在目录的父目录的父目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Config:
    """配置类"""

    # 工作目录 - 使用项目目录下的 workspace
    WORKSPACE_DIR = PROJECT_ROOT / "examples" / "xhs_publisher" / "workspace"

    # 图片临时目录
    IMAGES_DIR = WORKSPACE_DIR / "images"

    # 文案目录
    CONTENT_DIR =  WORKSPACE_DIR / "content"

    # Agent配置
    MAX_STEPS = 50
    TOKEN_LIMIT = 80000

    # MCP 配置
    # 设置为 True 则加载 MCP 工具（需要配置 mcp.json）
    # 设置为 False 则不加载任何 MCP 工具
    ENABLE_MCP = True
    
    # 图像生成工具配置
    # 可选值: 'banana'
    # - 'banana': 使用内置的 BananaImageGenTool（无需额外配置）
    IMAGE_GEN_TOOL = 'banana'  # 默认使用 banana
    
    # 飞书配置
    # 启用飞书文档读取功能（需要配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET）
    ENABLE_FEISHU = False

    @classmethod
    def ensure_dirs(cls):
        """确保目录存在"""
        cls.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        cls.CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_image_gen_tool_name(cls) -> str:
        """获取图像生成工具名称"""
        return "text_to_image" if cls.IMAGE_GEN_TOOL == 'mcp' else "banana_image_gen"
