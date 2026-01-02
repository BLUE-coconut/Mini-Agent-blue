"""浏览器管理器 - 基于playwright的反检测浏览器管理"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class BrowserManager:
    """浏览器管理器 - 使用上下文管理器确保资源正确释放"""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._initialized = False

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self) -> None:
        """初始化浏览器"""
        if self._initialized:
            return

        try:
            self.playwright = await async_playwright().start()

            launch_args = {
                'headless': False,
                'args': [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-infobars',
                    '--start-maximized',
                    '--ignore-certificate-errors',
                    '--ignore-ssl-errors'
                ]
            }

            self.browser = await self.playwright.chromium.launch(**launch_args)
            self.context = await self.browser.new_context(permissions=['geolocation'])
            self.page = await self.context.new_page()

            await self._inject_stealth_script()
            self._initialized = True

        except Exception as e:
            await self.close()
            raise RuntimeError(f"浏览器初始化失败: {e}")

    async def _inject_stealth_script(self) -> None:
        """注入反检测脚本"""
        stealth_js = """
        (function(){
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh'] });
            window.chrome = { runtime: {} };
            delete navigator.__proto__.webdriver;

            if ('serviceWorker' in navigator) {
                Object.defineProperty(navigator, 'serviceWorker', { get: () => undefined });
            }

            window.addEventListener('error', function(e) {
                if (e.message && e.message.includes('serviceWorker')) {
                    e.preventDefault();
                    return false;
                }
            });
        })();
        """
        await self.page.add_init_script(stealth_js)

    async def close(self) -> None:
        """关闭浏览器资源"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        finally:
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None
            self._initialized = False

    async def ensure_initialized(self) -> None:
        """确保浏览器已初始化"""
        if not self._initialized:
            await self.initialize()


@asynccontextmanager
async def browser_session():
    """浏览器会话上下文管理器"""
    manager = BrowserManager()
    try:
        await manager.initialize()
        yield manager
    finally:
        await manager.close()
