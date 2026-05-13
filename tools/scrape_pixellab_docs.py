#!/usr/bin/env python3
"""Scrape Pixellab API docs (Scalar + Redoc) to local files via Playwright."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUT_DIR = Path("docs/reference/pixellab-api")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("scalar-docs", "https://api.pixellab.ai/v2/docs"),
    ("redoc",       "https://api.pixellab.ai/v2/redoc"),
]

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 1000})
        for label, url in PAGES:
            print(f"\n=== {label} ← {url} ===")
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)
            # Give JS one extra second to render
            await page.wait_for_timeout(2500)

            html = await page.content()
            html_path = OUT_DIR / f"{label}.html"
            html_path.write_text(html, encoding="utf-8")
            print(f"  saved HTML: {html_path} ({len(html):,} bytes)")

            # Extract visible text (the rendered API doc body)
            text = await page.evaluate("() => document.body.innerText")
            text_path = OUT_DIR / f"{label}.txt"
            text_path.write_text(text, encoding="utf-8")
            lines = text.splitlines()
            print(f"  saved TEXT: {text_path} ({len(text):,} chars, {len(lines)} lines)")

            await page.close()
        await browser.close()

asyncio.run(scrape())
print("\nDone.")
