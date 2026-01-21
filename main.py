import asyncio
import aiohttp
import random
import os
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime
from urllib.parse import urlparse

CONCURRENT_THREADS = 10
TIMEOUT_PER_LINK = 40000

os.makedirs("results", exist_ok=True)

class OuoBypasser:
    def __init__(self):
        self.results = []
        self.proxy_sources = [
            "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt"
        ]

    async def fetch_all_proxies(self):
        proxies = set()
        async with aiohttp.ClientSession() as session:
            for url in self.proxy_sources:
                try:
                    async with session.get(url, timeout=15) as r:
                        if r.status == 200:
                            data = await r.text()
                            for line in data.splitlines():
                                if ":" in line:
                                    proxies.add(line.strip())
                except:
                    pass
        lst = list(proxies)
        random.shuffle(lst)
        print(f"📡 Proxy loaded: {len(lst)}")
        return lst

    def normalize_proxy(self, proxy):
        if proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            return proxy
        if re.match(r"\d+\.\d+\.\d+\.\d+:\d+", proxy):
            return "http://" + proxy
        return None

    def proxy_config(self, proxy):
        p = self.normalize_proxy(proxy)
        if not p:
            return None
        u = urlparse(p)
        cfg = {"server": p}
        if u.username:
            cfg["username"] = u.username
        if u.password:
            cfg["password"] = u.password
        return cfg

    async def run(self, wid, proxy, url):
        cfg = self.proxy_config(proxy)
        if not cfg:
            return None

        result = {
            "worker": wid,
            "url": url,
            "proxy": proxy,
            "success": False,
            "time": datetime.utcnow().isoformat()
        }

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=cfg,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )

                page = await (await browser.new_context()).new_page()
                page.set_default_timeout(TIMEOUT_PER_LINK)

                await page.goto(url, wait_until="domcontentloaded")

                try:
                    await page.click("#btn-main", timeout=5000)
                except:
                    pass

                await asyncio.sleep(3)

                await page.wait_for_load_state("networkidle", timeout=10000)

                final = page.url
                if "ouo" not in final:
                    result["success"] = True
                    result["final_url"] = final
                    print(f"[W{wid}] ✅ {final}")

                await browser.close()
            except Exception:
                print(f"[W{wid}] ❌ Proxy failed")

        return result

    def load_links(self):
        with open("ouo.io.txt") as f:
            return [x.strip() for x in f if x.startswith("http")]

async def worker(wid, bypasser, queue, links, stats):
    while not queue.empty():
        proxy = await queue.get()
        url = random.choice(links)
        res = await bypasser.run(wid, proxy, url)
        stats["total"] += 1
        if res and res["success"]:
            stats["success"] += 1
            bypasser.results.append(res)
            with open("results/results.json", "w") as f:
                json.dump(bypasser.results, f, indent=2)
        queue.task_done()

async def main():
    bypasser = OuoBypasser()
    links = bypasser.load_links()
    proxies = await bypasser.fetch_all_proxies()

    q = asyncio.Queue()
    for p in proxies:
        q.put_nowait(p)

    stats = {"total": 0, "success": 0}

    tasks = [
        asyncio.create_task(worker(i+1, bypasser, q, links, stats))
        for i in range(CONCURRENT_THREADS)
    ]

    await q.join()
    for t in tasks:
        t.cancel()

    print("🏁 DONE")
    print(stats)

if __name__ == "__main__":
    asyncio.run(main())
