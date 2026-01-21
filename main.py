# main.py

import asyncio
import aiohttp
import nest_asyncio
import random
import os
import json
import re
from playwright.async_api import async_playwright
from datetime import datetime
from urllib.parse import urlparse
from collections import deque

# Apply nest_asyncio if needed (optional in non-Colab, but kept for compatibility)
nest_asyncio.apply()

# Hapus pembuatan folder screenshot, hanya results
os.makedirs('results', exist_ok=True)

# ==========================================
# 2. CONFIGURATION
# ==========================================
# Jumlah browser yang jalan bersamaan (Hati-hati RAM penuh jika terlalu banyak)
CONCURRENT_THREADS = 10 
TIMEOUT_PER_LINK = 40000  # 40 detik timeout

class OuoBypasser:
    def __init__(self):
        self.results = []
        # Sumber proxy public
        self.proxy_sources = [
            "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt"
            # "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
            # "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            # "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            # "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            # "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt"
        ]

    async def fetch_all_proxies(self):
        """Mengambil proxy mentah tanpa validasi awal (langsung tes di link)"""
        all_proxies = set()
        print(f"📡 Mengambil proxy dari {len(self.proxy_sources)} sumber...")

        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_single_source(session, url) for url in self.proxy_sources]
            results = await asyncio.gather(*tasks)
            for proxy_list in results:
                all_proxies.update(proxy_list)

        proxy_list = list(all_proxies)
        random.shuffle(proxy_list) # Acak di awal
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
        """Format proxy agar diterima Playwright"""
        proxy = proxy.strip()
        # Jika sudah ada protocol
        if proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            return proxy
        # Jika IP:PORT biasa, anggap HTTP
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
        """Menjalankan satu sesi browser dengan 1 proxy"""
        
        proxy_config = self.parse_proxy_config(proxy)
        if not proxy_config:
            return None

        result = {
            'worker': worker_id,
            'url': url, 
            'proxy': proxy, 
            'success': False,
            'timestamp': datetime.now().isoformat()
        }

        # Print info (dipendekkan agar tidak spamming console)
        print(f"   [W{worker_id}] 🚀 Start: {proxy[:25]}...")

        async with async_playwright() as p:
            browser = None
            try:
                # Launch Browser dengan Proxy
                browser = await p.chromium.launch(
                    headless=True,
                    proxy=proxy_config,
                    args=[
                        '--no-sandbox', 
                        '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )

                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    ignore_https_errors=True
                )
                
                # Anti-detect script
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                page = await context.new_page()
                page.set_default_timeout(TIMEOUT_PER_LINK)

                # 1. LANGSUNG CEK KE LINK (Validasi Proxy di sini)
                try:
                    await page.goto(url, wait_until='domcontentloaded')
                except Exception as e:
                    # Jika gagal load awal, berarti proxy mati/lambat -> Langsung return
                    print(f"   [W{worker_id}] ❌ Proxy Dead/Timeout")
                    await browser.close()
                    return result # Success False

                # 2. Logika Bypass
                try:
                    # Klik tombol 'I am a human' atau sejenisnya
                    try:
                        await page.click('#btn-main', timeout=5000)
                    except:
                        # Cari tombol submit apapun
                        btns = await page.query_selector_all('button, input[type="submit"]')
                        for btn in btns:
                            if await btn.is_visible():
                                await btn.click()
                                break
                    
                    # Tunggu sebentar untuk countdown
                    await asyncio.sleep(3)

                    # Klik Get Link
                    try:
                        await page.click('#btn-main', timeout=5000)
                    except:
                        try:
                            await page.click('button:has-text("Get Link")', timeout=3000)
                        except:
                            pass
                    
                    # Tunggu redirect selesai
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # Cek Final URL
                    curr_url = page.url
                    if 'ouo.io' not in curr_url and 'ouo.press' not in curr_url and not curr_url.startswith('chrome-error'):
                        result['success'] = True
                        result['final_url'] = curr_url
                        print(f"   [W{worker_id}] 🎉 SUKSES! -> {curr_url}")
                    else:
                        print(f"   [W{worker_id}] ⚠️ Gagal Bypass")

                except Exception as e:
                    print(f"   [W{worker_id}] ⚠️ Error saat interaksi: {str(e)[:50]}")

                await browser.close()

            except Exception as e:
                # Error saat launch browser atau koneksi proxy fatal
                print(f"   [W{worker_id}] ❌ Connect Error")
                if browser: await browser.close()
        
        return result

    def load_links(self):
        filename = "ouo.io.txt"
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                f.write("https://ouo.io/MEhvxv\nhttps://ouo.io/NAcnTB\n")
            print(f"📝 Membuat file dummy {filename}")
            return ["https://ouo.io/MEhvxv", "https://ouo.io/NAcnTB"]
        
        with open(filename, 'r') as f:
            lines = [line.strip() for line in f if line.strip().startswith('http')]
        return lines if lines else []

    def save_results(self):
        with open('results/results.json', 'w') as f:
            json.dump(self.results, f, indent=2)

# ==========================================
# 3. WORKER SYSTEM (Multi-Thread Logic)
# ==========================================
async def worker(id, bypasser, proxy_queue, link_list, stats):
    """Worker yang terus berjalan sampai proxy habis"""
    print(f"🔧 Worker {id} siap.")
    
    while not proxy_queue.empty():
        # Ambil proxy (Pop & Delete otomatis karena Queue)
        proxy = await proxy_queue.get()
        
        # Ambil link acak
        target_link = random.choice(link_list)
        
        # Jalankan proses
        result = await bypasser.run_bypass_task(id, proxy, target_link)
        
        # Update Stats
        stats['processed'] += 1
        if result and result['success']:
            stats['success'] += 1
            bypasser.results.append(result)
            bypasser.save_results() # Simpan jika sukses
        
        proxy_queue.task_done()
        
        # Tampilkan stats di console setiap 10 proses
        if stats['processed'] % 10 == 0:
            print(f"\n📊 TOTAL STATS: {stats['success']}/{stats['processed']} Sukses | Sisa Proxy: {proxy_queue.qsize()}\n")

async def main():
    print("\n" + "="*60)
    print(f"🚀 OUO BYPASSER MULTI-THREAD ({CONCURRENT_THREADS} Threads)")
    print("="*60)

    bypasser = OuoBypasser()
    
    # 1. Load Links
    links = bypasser.load_links()
    if not links:
        print("❌ Tidak ada link di ouo.io.txt")
        return

    # 2. Ambil Proxy (Tanpa cek httpbin)
    raw_proxies = await bypasser.fetch_all_proxies()
    if not raw_proxies:
        print("❌ Gagal mengambil proxy.")
        return

    # 3. Masukkan ke Queue (Antrian)
    # Ini memastikan proxy hanya diambil sekali lalu hilang dari antrian
    proxy_queue = asyncio.Queue()
    for p in raw_proxies:
        await proxy_queue.put(p)  # Use await for async queue

    stats = {'processed': 0, 'success': 0}

    # 4. Jalankan Worker (Multi-thread)
    print(f"\n🎬 Memulai {CONCURRENT_THREADS} worker serentak...")
    workers = []
    for i in range(CONCURRENT_THREADS):
        task = asyncio.create_task(worker(i+1, bypasser, proxy_queue, links, stats))
        workers.append(task)

    # Tunggu semua queue habis
    await proxy_queue.join()
    
    # Cancel worker jika queue sudah kosong (untuk membersihkan task)
    for task in workers:
        task.cancel()

    print("\n" + "="*60)
    print("🏁 SELESAI. Semua proxy telah dicoba.")
    print(f"✅ Total Sukses: {stats['success']}")
    print(f"📊 Total Dicoba: {stats['processed']}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
