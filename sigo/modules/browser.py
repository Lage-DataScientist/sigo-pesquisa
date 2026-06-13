"""Gestão do browser via Playwright."""

from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from sigo.config import BROWSER_OPTIONS


@asynccontextmanager
async def browser_session():
    """Context manager que devolve (browser, context, page) e fecha tudo no final."""
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=BROWSER_OPTIONS["headless"],
            slow_mo=BROWSER_OPTIONS["slow_mo"],
        )
        context: BrowserContext = await browser.new_context()
        context.set_default_timeout(BROWSER_OPTIONS["timeout"])
        page: Page = await context.new_page()
        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()
