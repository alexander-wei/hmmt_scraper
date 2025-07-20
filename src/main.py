import aiohttp
import aiofiles
import asyncio
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm.asyncio import tqdm

BASE_URL = "https://www.hmmt.org/www/archive/problems"
OUTPUT_DIR = "downloaded_pdfs"
CONCURRENT_REQUESTS = 10  # adjust based on your bandwidth

sem = asyncio.Semaphore(CONCURRENT_REQUESTS)

async def fetch_html(session, url):
    async with sem:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.text()

async def download_file(session, url, out_dir):
    filename = os.path.basename(urlparse(url).path)
    filepath = os.path.join(out_dir, filename)
    if os.path.exists(filepath):
        return  # skip if already downloaded

    async with sem:
        async with session.get(url) as response:
            response.raise_for_status()
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(await response.read())

async def get_links_in_content(session, url):
    html = await fetch_html(session, url)
    soup = BeautifulSoup(html, 'html.parser')
    content_div = soup.find('div', id='content')
    if not content_div:
        return []
    return [urljoin(url, a['href']) for a in content_div.find_all('a', href=True)]

async def scrape():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        # Step 1: Get links pages
        links_pages = await get_links_in_content(session, BASE_URL)

        pdf_links = set()
        # Step 2: For each links page, get PDF links
        for link_page in tqdm(links_pages, desc="Fetching links pages"):
            sub_links = await get_links_in_content(session, link_page)
            pdf_links.update(url for url in sub_links if url.lower().endswith('.pdf'))

        # Step 3: Download all PDFs
        tasks = [
            asyncio.create_task(download_file(session, pdf_url, OUTPUT_DIR))
            for pdf_url in pdf_links
        ]
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading PDFs"):
            await f

if __name__ == "__main__":
    asyncio.run(scrape())
