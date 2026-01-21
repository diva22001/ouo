import asyncio
import aiohttp
import random
import os
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime
from urllib.parse import urlparse

# ==========================================
# CONFIGURATION
# ==========================================
CONCURRENT_THREADS = 5 
TIMEOUT_PER_LINK = 40000 

class OuoBypasser:
    def __init__(self):
        self.results = []
        # Menggunakan sumber proxy US sesuai permintaan
        self.proxy_sources = [
            "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt"
        ]

    async def fetch_all_proxies(self):
        all_proxies = set()
        print(f"📡 Mengambil proxy dari {self.proxy_sources[0]}...")

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_source(session, url) for url in self.proxy_sources]
            results = await asyncio.gather(*tasks)
            for proxy_list in results:
                all_proxies.update(proxy_list)

        proxy_list = list(all_proxies)
        random.shuffle(proxy_list) [cite: 7]
        print(f"✅ Total proxy didapatkan: {len(proxy_list)}")
        return proxy_list

    async def _fetch_single_source(self, session, url):
        try:
            async with session.get(url, timeout=15) as response:
                if response.status == 200:
                    content = await response.text() [cite: 8]
                    return [line.strip() for line in content.split('\n') if line.strip() and ':' in line] [cite: 8]
        except:
            pass
        return []

    def parse_proxy_config(self, proxy):
        proxy = proxy.strip() [cite: 9]
        if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            proxy = f"http://{proxy}" [cite: 9]
        
        parsed = urlparse(proxy)
        return {'server': proxy}

    async def run_bypass_task(self, worker_id, proxy, url):
        proxy_config = self.parse_proxy_config(proxy)
        result = {'worker': worker_id, 'url': url, 'proxy': proxy, 'success': False, 'timestamp': datetime.now().isoformat()} [cite: 12]

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(headless=True, proxy=proxy_config, args=['--no-sandbox', '--disable-dev-shm-usage']) [cite: 13, 14]
                context = await browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36') [cite: 15, 16]
                page = await context.new_page() [cite: 17]
                page.set_default_timeout(TIMEOUT_PER_LINK) [cite: 17]

                try:
                    await page.goto(url, wait_until='domcontentloaded') [cite: 17]
                except:
                    await browser.close() [cite: 18]
                    return result

                # Logika Klik
                try:
                    await page.click('#btn-main', timeout=7000) [cite: 20]
                    await asyncio.sleep(3) [cite: 22]
                    await page.click('#btn-main', timeout=7000) [cite: 23]
                    await page.wait_for_load_state('networkidle', timeout=10000) [cite: 25]
                    
                    if 'ouo.io' not in page.url and 'ouo.press' not in page.url: [cite: 26]
                        result['success'] = True
                        result['final_url'] = page.url
                        print(f"   [W{worker_id}] 🎉 SUKSES: {page.url}") [cite: 27, 28]
                except:
                    pass

                await browser.close() [cite: 29]
            except:
                if browser: await browser.close() [cite: 29]
        return result

async def worker(id, bypasser, proxy_queue, link_list, stats):
    while not proxy_queue.empty():
        proxy = await proxy_queue.get() [cite: 32]
        target_link = random.choice(link_list) [cite: 32]
        result = await bypasser.run_bypass_task(id, proxy, target_link) [cite: 33]
        
        stats['processed'] += 1
        if result and result['success']:
            stats['success'] += 1
            bypasser.results.append(result)
            bypasser.save_results()
        
        proxy_queue.task_done() [cite: 34]

async def main():
    bypasser = OuoBypasser()
    links = ["https://ouo.io/MEhvxv", "https://ouo.io/NAcnTB"] # Atau load dari file 
    raw_proxies = await bypasser.fetch_all_proxies()

    proxy_queue = asyncio.Queue()
    for p in raw_proxies: # TIDAK DIBATASI [cite: 36]
        proxy_queue.put_nowait(p)

    stats = {'processed': 0, 'success': 0}
    tasks = [asyncio.create_task(worker(i, bypasser, proxy_queue, links, stats)) for i in range(CONCURRENT_THREADS)] [cite: 37]
    
    await proxy_queue.join()
    print(f"\n🏁 SELESAI. Total Sukses: {stats['success']}") [cite: 38]

if __name__ == "__main__":
    asyncio.run(main())
