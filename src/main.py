import aiohttp
import aiofiles
import asyncio
import os
import async_timeout
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm.asyncio import tqdm
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

BASE_URL = "https://www.hmmt.org/www/archive/problems"
OUTPUT_DIR = "downloaded_pdfs"
CONCURRENT_REQUESTS = 10  # adjust as needed
REQUEST_TIMEOUT = 10  # seconds

sem = asyncio.Semaphore(CONCURRENT_REQUESTS)


# Retry decorator: max 5 attempts, exponential backoff 1s → 2s → 4s...
def retry_async():
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )


@retry_async()
async def fetch_html(session, url):
    async with sem:
        with async_timeout.timeout(REQUEST_TIMEOUT):
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.text()


@retry_async()
async def download_file(session, url, out_dir):
    filename = os.path.basename(urlparse(url).path)
    filepath = os.path.join(out_dir, filename)
    if os.path.exists(filepath):
        return  # Skip if already exists

    async with sem:
        with async_timeout.timeout(REQUEST_TIMEOUT):
            async with session.get(url) as response:
                response.raise_for_status()
                async with aiofiles.open(filepath, "wb") as f:
                    await f.write(await response.read())


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
        # Step 1: Get links pages
        print("📥 Fetching links pages...")
        links_pages = await get_links_in_content(session, BASE_URL)

        pdf_links = set()
        # Step 2: For each links page, get PDF links (with progress bar)
        for link_page in tqdm(links_pages, desc="🔗 Discovering PDFs"):
            try:
                sub_links = await get_links_in_content(session, link_page)
                pdf_links.update(
                    url for url in sub_links if url.lower().endswith(".pdf")
                )
            except RetryError as e:
                print(f"⚠️ Failed to fetch {link_page}: {e}")

        # Step 3: Download PDFs (with progress bar)
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


if __name__ == "__main__":
    asyncio.run(scrape())
