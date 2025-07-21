import asyncio
import json
import os
import random
import string
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
import async_timeout
from bs4 import BeautifulSoup
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential
from tqdm.asyncio import tqdm

BASE_URL = "https://www.hmmt.org/www/archive/problems"
OUTPUT_DIR = "downloaded_pdfs"
LOG_FILE = "download_log.json"
CONCURRENT_REQUESTS = 10
REQUEST_TIMEOUT = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

sem = asyncio.Semaphore(CONCURRENT_REQUESTS)
download_log = []


def retry_async():
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )


def random_string(length=12):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@retry_async()
async def fetch_html(session, url):
    await asyncio.sleep(random.uniform(0, 1))
    async with sem:
        with async_timeout.timeout(REQUEST_TIMEOUT):
            async with session.get(url, headers=HEADERS) as response:
                response.raise_for_status()
                return await response.text()


@retry_async()
async def download_file(session, url, out_dir):
    await asyncio.sleep(random.uniform(0, 1))
    filename = os.path.basename(urlparse(url).path)
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{random_string(12)}{ext}"
    filepath = os.path.join(out_dir, unique_filename)

    async with sem:
        with async_timeout.timeout(REQUEST_TIMEOUT):
            async with session.get(url, headers=HEADERS) as response:
                response.raise_for_status()
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(await response.read())

    # Record mapping
    download_log.append({"url": url, "filename": unique_filename})


async def get_links_in_content(session, url):
    html = await fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", id="content")
    if not content_div:
        return []
    return [urljoin(url, a["href"]) for a in content_div.find_all("a", href=True)]


async def scrape():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        print("📥 Fetching links pages...")
        links_pages = await get_links_in_content(session, BASE_URL)

        pdf_links = set()
        for link_page in tqdm(links_pages, desc="🔗 Discovering PDFs"):
            try:
                sub_links = await get_links_in_content(session, link_page)
                pdf_links.update(
                    url for url in sub_links if url.lower().endswith(".pdf")
                )
            except RetryError as e:
                print(f"⚠️ Failed to fetch {link_page}: {e}")

        print(f"📄 Found {len(pdf_links)} PDFs. Starting downloads...")
        tasks = [
            asyncio.create_task(download_file(session, pdf_url, OUTPUT_DIR))
            for pdf_url in pdf_links
        ]

        for f in tqdm(
            asyncio.as_completed(tasks), total=len(tasks), desc="💾 Downloading PDFs"
        ):
            try:
                await f
            except RetryError as e:
                print(f"⚠️ Failed to download: {e}")

    # Write log file
    async with aiofiles.open(LOG_FILE, "w") as f:
        await f.write(json.dumps(download_log, indent=2))
    print(f"✅ Download log written to {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(scrape())
