"""小红书发布器 - 处理登录和内容发布"""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, List

from .manager import BrowserManager
from config import Config


class XiaohongshuPublisher:
    """小红书内容发布器"""

    BASE_URL = "https://creator.xiaohongshu.com"

    def __init__(self, browser_manager: BrowserManager):
        self.browser = browser_manager
        self._setup_storage()

    def _setup_storage(self):
        """设置存储路径 - 使用统一的 workspace 目录"""
        app_dir = Config.WORKSPACE_DIR
        app_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_file = app_dir / "cookies.json"

    async def _load_cookies(self):
        """从文件加载cookies"""
        if not self.cookies_file.exists():
            return
        try:
            cookies = json.loads(self.cookies_file.read_text())
            for cookie in cookies:
                cookie.setdefault('domain', '.xiaohongshu.com')
                cookie.setdefault('path', '/')
            await self.browser.context.add_cookies(cookies)
        except Exception:
            pass

    async def _save_cookies(self):
        """保存cookies到文件"""
        if not self.browser.context:
            return
        try:
            cookies = await self.browser.context.cookies()
            self.cookies_file.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        except Exception:
            pass

    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            await self.browser.page.goto(self.BASE_URL, wait_until="networkidle")
            await asyncio.sleep(2)
            return "login" not in self.browser.page.url
        except Exception:
            return False

    async def login_with_cookies(self) -> bool:
        """尝试使用cookies登录"""
        await self._load_cookies()
        return await self.is_logged_in()

    async def wait_for_manual_login(self) -> bool:
        """等待用户手动登录"""
        await self.browser.page.goto(f"{self.BASE_URL}/login", wait_until="networkidle")

        # 等待用户完成登录，最多等待5分钟
        for _ in range(60):
            await asyncio.sleep(5)
            if "login" not in self.browser.page.url:
                await self._save_cookies()
                return True
        return False

    async def post_article(self, title: str, content: str, images: Optional[List[str]] = None) -> dict:
        """发布图文内容

        Args:
            title: 文章标题
            content: 文章内容
            images: 图片路径列表

        Returns:
            dict: 包含success和message的结果
        """
        try:
            # 导航到创作者中心
            await self.browser.page.goto(self.BASE_URL, wait_until="networkidle")
            await asyncio.sleep(3)

            if "login" in self.browser.page.url:
                return {"success": False, "message": "未登录，请先登录"}

            # 点击发布按钮
            publish_selectors = [".publish-video .btn", "button:has-text('发布笔记')"]
            for selector in publish_selectors:
                try:
                    await self.browser.page.wait_for_selector(selector, timeout=5000)
                    await self.browser.page.click(selector)
                    break
                except Exception:
                    continue

            await asyncio.sleep(3)

            # 切换到图文选项卡
            try:
                await self.browser.page.wait_for_selector(".creator-tab", timeout=10000)
                await self.browser.page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('.creator-tab');
                        if (tabs.length > 1) tabs[1].click();
                    }
                """)
                await asyncio.sleep(2)
            except Exception:
                pass

            # 上传图片
            if images:
                await self._upload_images(images)

            # 输入标题
            await self._fill_title(title)

            # 输入内容
            await self._fill_content(content)

            return {"success": True, "message": "内容已填充，请在浏览器中检查并手动点击发布"}

        except Exception as e:
            return {"success": False, "message": f"发布失败: {e}"}

    async def _upload_images(self, images: List[str]):
        """上传图片"""
        try:
            await self.browser.page.wait_for_selector(".upload-button", timeout=20000)
            await asyncio.sleep(1.5)

            # 尝试直接设置文件
            try:
                await self.browser.page.set_input_files(".upload-input", files=images, timeout=10000)
                await asyncio.sleep(5)
                return
            except Exception:
                pass

            # 备选：点击上传按钮触发文件选择
            try:
                async with self.browser.page.expect_file_chooser(timeout=15000) as fc_info:
                    await self.browser.page.click(".upload-button", timeout=7000)
                file_chooser = await fc_info.value
                await file_chooser.set_files(images)
                await asyncio.sleep(5)
            except Exception:
                pass

        except Exception:
            pass

    async def _fill_title(self, title: str):
        """填写标题"""
        title_selectors = [
            "input.d-text[placeholder='填写标题会有更多赞哦～']",
            "input.d-text",
            "input[placeholder*='标题']"
        ]
        for selector in title_selectors:
            try:
                await self.browser.page.wait_for_selector(selector, timeout=5000)
                await self.browser.page.fill(selector, title)
                return
            except Exception:
                continue

    async def _fill_content(self, content: str):
        """填写内容"""
        content_selectors = [
            "[contenteditable='true']",
            ".note-content",
            "[role='textbox']"
        ]
        for selector in content_selectors:
            try:
                await self.browser.page.wait_for_selector(selector, timeout=5000)
                await self.browser.page.fill(selector, content)
                return
            except Exception:
                continue
