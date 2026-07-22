#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动截图脚本 — 使用 Playwright + 系统已安装的 Chrome 浏览器
遍历 urls.txt 中所有网站，截取首页截图
"""

import asyncio
import os
import re
import sys
from urllib.parse import urlparse

# 使用 Playwright 的异步 API
from playwright.async_api import async_playwright

URLS_FILE = 'urls.txt'
OUTPUT_DIR = 'images/screenshots'
MAX_CONCURRENT = 3  # 并发数（降低避免被封）
TIMEOUT_MS = 25000  # 页面加载超时
VIEWPORT = {'width': 1280, 'height': 800}

# 系统已安装的 Chrome 路径
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def sanitize_filename(url):
    """将 URL 转为安全的文件名"""
    parsed = urlparse(url)
    name = (parsed.netloc + parsed.path).replace('/', '_').replace('.', '_')
    name = re.sub(r'[^a-zA-Z0-9_\-\u4e00-\u9fff]', '', name)
    name = name[:80]
    if not name:
        name = 'unknown'
    return name + '.png'


async def screenshot_one(context, url, semaphore, progress, total):
    """截取单个网站的截图"""
    async with semaphore:
        filename = sanitize_filename(url)
        filepath = os.path.join(OUTPUT_DIR, filename)

        # 跳过已存在的截图
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            progress[0] += 1
            print(f"  [{progress[0]}/{total}] ⏭️ 跳过: {url}")
            return filename, url

        page = None
        try:
            page = await context.new_page()
            await page.set_viewport_size(VIEWPORT)

            # 设置超时并加载页面
            await page.goto(url, timeout=TIMEOUT_MS, wait_until='domcontentloaded')
            await asyncio.sleep(1.5)

            # 截图
            await page.screenshot(path=filepath, full_page=False)

            progress[0] += 1
            print(f"  [{progress[0]}/{total}] ✅ {url}")
            return filename, url

        except Exception as e:
            progress[0] += 1
            err = str(e)[:60]
            print(f"  [{progress[0]}/{total}] ❌ {url} — {err}")
            return None, url

        finally:
            if page:
                await page.close()


async def main():
    # 读取 URL 列表
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip()]

    urls = [u for u in urls if u.startswith('http')]
    print(f"📋 共 {len(urls)} 个 URL 待截图")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    print(f"🔗 并发数: {MAX_CONCURRENT}")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("🚀 启动浏览器（使用系统已安装的 Chrome）...")
    sys.stdout.flush()

    async with async_playwright() as p:
        # 使用系统 Chrome 启动
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROME_PATH,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--ignore-certificate-errors',
            ],
        )

        # 创建共享上下文（复用 cookie/缓存，加速加载）
        context = await browser.new_context(
            viewport=VIEWPORT,
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            ignore_https_errors=True,
        )

        print("✅ 浏览器启动成功\n")
        sys.stdout.flush()

        # 并发截图
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        progress = [0]
        tasks = [screenshot_one(context, url, semaphore, progress, len(urls)) for url in urls]
        results = await asyncio.gather(*tasks)

        await context.close()
        await browser.close()

    # 统计
    success = sum(1 for r in results if r[0] is not None)
    failed = sum(1 for r in results if r[0] is None)

    print(f"\n📊 截图完成: ✅ {success} 成功, ❌ {failed} 失败, 📁 共 {len(urls)} 个")

    # 生成截图映射文件
    mapping_lines = []
    for filename, url in results:
        if filename:
            mapping_lines.append(f"{url}|{filename}")

    mapping_path = os.path.join(OUTPUT_DIR, '_mapping.txt')
    with open(mapping_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(mapping_lines))
    print(f"📝 截图映射已保存: {mapping_path}")


if __name__ == '__main__':
    asyncio.run(main())