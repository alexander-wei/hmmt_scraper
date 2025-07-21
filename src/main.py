"""
Asynchronous PDF Scraper for HMMT Archive

This module provides an asynchronous web scraper that downloads all PDF files
linked from the Harvard-MIT Mathematics Tournament (HMMT) archive problems page.

Features
--------
- Crawls the HMMT archive problems page and its subpages to discover all PDF links.
- Downloads PDFs concurrently with robust retry logic and timeout handling.
- Saves each PDF with a unique filename to avoid collisions.
- Logs all downloads to a JSON file for traceability.

Usage
-----
Run this script directly to start scraping and downloading PDFs:

    python main.py

The downloaded PDFs will be saved in the ``downloaded_pdfs/`` directory, and
a log of all downloads will be written to ``download_log.json``.

Dependencies
------------
- aiohttp
- aiofiles
- async_timeout
- beautifulsoup4
- tenacity
- tqdm

"""

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
    """
    Returns a tenacity retry decorator configured for asynchronous operations.

    The decorator retries a function up to 5 times with exponential backoff,
    raising the last exception if all attempts fail.

    :return: Configured tenacity.retry decorator for async functions.
    :rtype: tenacity.retry
    """
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )


def random_string(length=12):
    """
    Generate a random alphanumeric string.

    :param int length: Length of the generated string. Default is 12.
    :return: Random string of specified length.
    :rtype: str
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@retry_async()
async def fetch_html(session, url):
    """
    Asynchronously fetch the HTML content of a given URL.

    :param aiohttp.ClientSession session: The aiohttp session to use for the request.
    :param str url: The URL to fetch.
    :return: HTML content as a string.
    :rtype: str
    :raises aiohttp.ClientError: If the request fails after retries.
    """
    await asyncio.sleep(random.uniform(0, 1))
    async with sem:
        with async_timeout.timeout(REQUEST_TIMEOUT):
            async with session.get(url, headers=HEADERS) as response:
                response.raise_for_status()
                return await response.text()


@retry_async()
async def download_file(session, url, out_dir):
    """
    Asynchronously download a file from a URL and save it with a unique filename.

    :param aiohttp.ClientSession session: The aiohttp session to use for the request.
    :param str url: The URL of the file to download.
    :param str out_dir: Directory to save the downloaded file.
    :return: None
    :rtype: None
    :raises aiohttp.ClientError: If the download fails after retries.

    The function appends a mapping of the original URL and the unique filename
    to the global download_log.
    """
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
    """
    Asynchronously extract all links from the 'content' div of a web page.

    :param aiohttp.ClientSession session: The aiohttp session to use for the request.
    :param str url: The URL of the page to parse.
    :return: List of absolute URLs found in the 'content' div.
    :rtype: list[str]
    :raises aiohttp.ClientError: If the page cannot be fetched after retries.
    """
    html = await fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", id="content")
    if not content_div:
        return []
    return [urljoin(url, a["href"]) for a in content_div.find_all("a", href=True)]


async def scrape():
    """
    Main coroutine to orchestrate scraping and downloading of PDFs from the HMMT archive.

    - Discovers all subpages from the archive index.
    - Extracts all PDF links from subpages.
    - Downloads all PDFs concurrently with retry and timeout handling.
    - Writes a log of all downloads to a JSON file.

    :return: None
    :rtype: None
    """
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
