import asyncio
import aiohttp
import random
import os
import json
import re
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright

# ============================================================
# CONFIG
# ============================================================
CONCURRENT_THREADS = 10
TIMEOUT_PER_LINK = 40000

TELEGRAM_BOT_TOKEN = "1854314410:AAErBoDlQEeK13RJ7v_0YbQjsW2V_TrIcEI"
TELEGRAM_CHAT_ID = "822150591"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

os.makedirs("results", exist_ok=True)

# ============================================================
# TELEGRAM
# ============================================================
async def send_telegram_result(result):
    text = (
        "🎉 *OUO BYPASS BERHASIL*\n\n"
        f"🔗 *Link Asal:*\n{result['url']}\n\n"
        f"✅ *Final URL:*\n{result['final_url']}\n\n"
        f"🌐 *Proxy:*\n`{result['proxy']}`\n\n"
        f"👷 *Worker:* W{result['worker']}\n"
        f"🕒 *Waktu:* {result['time']}"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(TELEGRAM_API, data=payload):
            pass


# ============================================================
# BYPASSER
# ============================================================
class OuoBypasser:
    def __init__(self):
        self.results = []
        self.proxy_sources = [
            "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/all.txt"
        ]

    async def fetch_all_proxies(self):
        print(f"📡 Mengambil proxy dari {len(self.proxy_sources)} sumber...")
        proxies = set()

        async with aiohttp.ClientSession() as session:
            for src in self.proxy_sources:
                try:
                    async with session.get(src, timeout=15) as r:
                        if r.status == 200:
                            for line in (await r.text()).splitlines():
                                if ":" in line:
                                    proxies.add(line.strip())
                except:
                    pass

        proxies = list(proxies)
        random.shuffle(proxies)
        print(f"✅ Total proxy mentah didapatkan: {len(proxies)}")
        return proxies

    def normalize_proxy(self, proxy):
        proxy = proxy.strip()
        if proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            return proxy
        if re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", proxy):
            return "http://" + proxy
        return None

    def parse_proxy_config(self, proxy):
        p = self.normalize_proxy(proxy)
        if not p:
            return None
        u = urlparse(p)
        cfg = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
        if u.username:
            cfg["username"] = u.username
        if u.password:
            cfg["password"] = u.password
        return cfg

    async def run(self, wid, proxy, url):
        print(f"   [W{wid}] 🚀 Start: {proxy[:30]}...")
        proxy_cfg = self.parse_proxy_config(proxy)
        if not proxy_cfg:
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
                    proxy=proxy_cfg,
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )

                context = await browser.new_context(ignore_https_errors=True)
                page = await context.new_page()
                page.set_default_timeout(TIMEOUT_PER_LINK)

                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except:
                    print(f"   [W{wid}] ❌ Proxy Dead/Timeout")
                    await browser.close()
                    return result

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
                    print(f"   [W{wid}] 🎉 SUKSES! -> {final}")
                    await send_telegram_result(result)
                else:
                    print(f"   [W{wid}] ⚠️ Gagal Bypass")

                await browser.close()

            except Exception as e:
                print(f"   [W{wid}] ⚠️ Error saat interaksi: {str(e)[:50]}")

        return result

    def load_links(self):
        with open("ouo.io.txt") as f:
            return [x.strip() for x in f if x.startswith("http")]


# ============================================================
# WORKER
# ============================================================
async def worker(wid, bypasser, queue, links, stats):
    print(f"🔧 Worker {wid} siap.")
    while not queue.empty():
        proxy = await queue.get()
        link = random.choice(links)

        res = await bypasser.run(wid, proxy, link)
        stats["total"] += 1

        if res and res.get("success"):
            stats["success"] += 1
            bypasser.results.append(res)
            with open("results/results.json", "w") as f:
                json.dump(bypasser.results, f, indent=2)

        if stats["total"] % 10 == 0:
            print(
                f"\n📊 TOTAL STATS: {stats['success']}/{stats['total']} "
                f"Sukses | Sisa Proxy: {queue.qsize()}\n"
            )

        queue.task_done()


# ============================================================
# MAIN
# ============================================================
async def main():
    print("\n" + "=" * 60)
    print(f"🚀 OUO BYPASSER MULTI-THREAD ({CONCURRENT_THREADS} Threads)")
    print("=" * 60)

    bypasser = OuoBypasser()
    links = bypasser.load_links()
    proxies = await bypasser.fetch_all_proxies()

    queue = asyncio.Queue()
    for p in proxies:
        queue.put_nowait(p)

    print(f"\n🎬 Memulai {CONCURRENT_THREADS} worker serentak...")
    stats = {"total": 0, "success": 0}

    tasks = [
        asyncio.create_task(worker(i + 1, bypasser, queue, links, stats))
        for i in range(CONCURRENT_THREADS)
    ]

    await queue.join()
    for t in tasks:
        t.cancel()

    print("\n" + "=" * 60)
    print("🏁 SELESAI. Semua proxy telah dicoba.")
    print(f"✅ Total Sukses: {stats['success']}")
    print(f"📊 Total Dicoba: {stats['total']}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
