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
# KONFIGURASI
# ==========================================
CONCURRENT_THREADS = 5  # Sesuaikan dengan CPU GitHub Runner (biasanya 2-core)
TIMEOUT_PER_LINK = 30000 # 30 detik

class OuoBypasser:
    def __init__(self):
        self.results = []
        self.proxy_sources = [
            "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/all.txt",
            "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"
        ]

    async def fetch_all_proxies(self):
        all_proxies = set()
        print(f"📡 Mengambil proxy dari {len(self.proxy_sources)} sumber...")

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_source(session, url) for url in self.proxy_sources]
            results = await asyncio.gather(*tasks)
            for proxy_list in results:
                all_proxies.update(proxy_list)

        proxy_list = list(all_proxies)
        random.shuffle(proxy_list)
        print(f"✅ Total proxy mentah didapatkan: {len(proxy_list)}")
        return proxy_list

    async def _fetch_single_source(self, session, url):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    return [line.strip() for line in content.split('\n') if line.strip() and ':' in line]
        except:
            pass
        return []

    def normalize_proxy_url(self, proxy):
        proxy = proxy.strip()
        if proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            return proxy
        if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', proxy):
            return f"http://{proxy}"
        return None

    def parse_proxy_config(self, proxy_url):
        if not proxy_url: return None
        normalized = self.normalize_proxy_url(proxy_url)
        if not normalized: return None
        
        parsed = urlparse(normalized)
        proxy_config = {'server': normalized}
        if parsed.username: proxy_config['username'] = parsed.username
        if parsed.password: proxy_config['password'] = parsed.password
        return proxy_config

    async def run_bypass_task(self, worker_id, proxy, url):
        proxy_config = self.parse_proxy_config(proxy)
        if not proxy_config: return None

        result = {
            'worker': worker_id,
            'url': url, 
            'proxy': proxy, 
            'success': False,
            'timestamp': datetime.now().isoformat()
        }

        print(f"   [W{worker_id}] 🚀 Start: {proxy[:25]}...")

        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy_config,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-blink-features=AutomationControlled']
                )

                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )
                
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                page = await context.new_page()
                page.set_default_timeout(TIMEOUT_PER_LINK)

                try:
                    await page.goto(url, wait_until='domcontentloaded')
                except Exception:
                    print(f"   [W{worker_id}] ❌ Proxy Dead/Timeout")
                    await browser.close()
                    return result

                # Logika Bypass
                try:
                    # Klik I am Human
                    try:
                        await page.click('#btn-main', timeout=5000)
                    except:
                        btns = await page.query_selector_all('button, input[type="submit"]')
                        for btn in btns:
                            if await btn.is_visible():
                                await btn.click()
                                break
                    
                    await asyncio.sleep(3)

                    # Klik Get Link
                    try:
                        await page.click('#btn-main', timeout=5000)
                    except:
                        try:
                            await page.click('button:has-text("Get Link")', timeout=3000)
                        except:
                            pass
                    
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    curr_url = page.url
                    if 'ouo.io' not in curr_url and 'ouo.press' not in curr_url and not curr_url.startswith('chrome-error'):
                        result['success'] = True
                        result['final_url'] = curr_url
                        print(f"   [W{worker_id}] 🎉 SUKSES! -> {curr_url}")
                    else:
                        print(f"   [W{worker_id}] ⚠️ Gagal Bypass")

                except Exception as e:
                    print(f"   [W{worker_id}] ⚠️ Error interaksi: {str(e)[:50]}")

                await browser.close()

            except Exception:
                print(f"   [W{worker_id}] ❌ Connect Error")
                if browser: await browser.close()
        
        return result

    def load_links(self):
        filename = "ouo.io.txt"
        if not os.path.exists(filename):
            print(f"❌ File {filename} tidak ditemukan.")
            return []
        
        with open(filename, 'r') as f:
            lines = [line.strip() for line in f if line.strip().startswith('http')]
        return lines

    def save_results(self):
        os.makedirs('results', exist_ok=True)
        with open('results/results.json', 'w') as f:
            json.dump(self.results, f, indent=2)

async def worker(id, bypasser, proxy_queue, link_list, stats):
    print(f"🔧 Worker {id} siap.")
    while not proxy_queue.empty():
        proxy = await proxy_queue.get()
        target_link = random.choice(link_list)
        
        result = await bypasser.run_bypass_task(id, proxy, target_link)
        
        stats['processed'] += 1
        if result and result['success']:
            stats['success'] += 1
            bypasser.results.append(result)
            bypasser.save_results()
        
        proxy_queue.task_done()
        
        if stats['processed'] % 10 == 0:
            print(f"\n📊 TOTAL: {stats['success']}/{stats['processed']} Sukses | Sisa Proxy: {proxy_queue.qsize()}\n")

async def main():
    print("="*60 + "\n🚀 OUO BYPASSER (GITHUB ACTIONS VERSION)\n" + "="*60)

    bypasser = OuoBypasser()
    links = bypasser.load_links()
    if not links: return

    raw_proxies = await bypasser.fetch_all_proxies()
    if not raw_proxies: return

    proxy_queue = asyncio.Queue()
    # Batasi jumlah proxy agar tidak timeout di GitHub Actions (Maks 6 jam)
    # Kita ambil 500 proxy acak saja untuk satu kali run
    for p in raw_proxies[:500]: 
        proxy_queue.put_nowait(p)

    stats = {'processed': 0, 'success': 0}
    
    tasks = []
    for i in range(CONCURRENT_THREADS):
        task = asyncio.create_task(worker(i+1, bypasser, proxy_queue, links, stats))
        tasks.append(task)

    await proxy_queue.join()
    
    for task in tasks: task.cancel()

    print(f"\n🏁 SELESAI. Sukses: {stats['success']} / {stats['processed']}")

if __name__ == "__main__":
    asyncio.run(main())
