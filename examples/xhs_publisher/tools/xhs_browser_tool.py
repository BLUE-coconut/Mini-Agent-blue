"""小红书浏览器工具 - 封装浏览器操作为Agent工具"""

from typing import Any, Optional
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mini_agent.tools.base import Tool, ToolResult
from browser import BrowserManager, XiaohongshuPublisher


# 全局浏览器实例
_browser_manager: Optional[BrowserManager] = None
_publisher: Optional[XiaohongshuPublisher] = None


class XHSBrowserTool(Tool):
    """小红书浏览器操作工具"""

    @property
    def name(self) -> str:
        return "xhs_browser"

    @property
    def description(self) -> str:
        return """小红书浏览器操作工具，支持以下操作:
- connect: 启动浏览器并连接小红书
- login: 尝试自动登录，失败则等待手动登录
- publish: 发布图文内容到小红书
- close: 关闭浏览器"""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["connect", "login", "publish", "close"],
                    "description": "要执行的操作"
                },
                "title": {
                    "type": "string",
                    "description": "发布内容的标题（仅publish操作需要）"
                },
                "content": {
                    "type": "string",
                    "description": "发布内容的正文（仅publish操作需要）"
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "图片文件的绝对路径列表（仅publish操作需要）"
                }
            },
            "required": ["action"]
        }

    async def execute(self, action: str, title: str = "", content: str = "", images: list = None) -> ToolResult:
        """执行浏览器操作"""
        global _browser_manager, _publisher

        try:
            if action == "connect":
                if _browser_manager and _browser_manager._initialized:
                    return ToolResult(success=True, content="浏览器已连接")

                _browser_manager = BrowserManager()
                await _browser_manager.initialize()
                _publisher = XiaohongshuPublisher(_browser_manager)
                return ToolResult(success=True, content="浏览器启动成功，已连接到小红书")

            elif action == "login":
                if not _publisher:
                    return ToolResult(success=False, error="请先执行connect操作")

                # 尝试cookies登录
                if await _publisher.login_with_cookies():
                    return ToolResult(success=True, content="登录成功（通过cookies）")

                # 等待手动登录
                return ToolResult(
                    success=True,
                    content="需要手动登录。请在浏览器中完成登录操作，登录成功后系统会自动检测。"
                )

            elif action == "publish":
                if not _publisher:
                    return ToolResult(success=False, error="请先执行connect和login操作")

                if not title or not content:
                    return ToolResult(success=False, error="发布需要提供title和content")

                result = await _publisher.post_article(title, content, images)
                return ToolResult(success=result["success"], content=result["message"])

            elif action == "close":
                if _browser_manager:
                    await _browser_manager.close()
                    _browser_manager = None
                    _publisher = None
                return ToolResult(success=True, content="浏览器已关闭")

            else:
                return ToolResult(success=False, error=f"未知操作: {action}")

        except Exception as e:
            return ToolResult(success=False, error=str(e))
