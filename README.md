# HMMT PDF Scraper

This project provides an asynchronous Python tool for downloading all PDF problems from the Harvard-MIT Mathematics Tournament (HMMT) archive. It was created to streamline the process of collecting problem sets for AI/LLM data annotation, particularly for annotating HMMT problems in a project I worked on as a data labeling contractor.

## Purpose

Manually gathering large sets of math problems for annotation is tedious and error-prone. This tool automates the process, making it easy to build high-quality datasets for machine learning, natural language processing, or educational research. It is especially useful for anyone working on AI/LLM data annotation projects involving mathematical content, or Olympiad-style math problems.

## Features

- **Automated Discovery:** Crawls the HMMT archive and subpages to find all available PDF problem sets.
- **Concurrent Downloads:** Downloads PDFs in parallel for speed and efficiency.
- **Robustness:** Handles network errors and timeouts with retries and exponential backoff.
- **Unique Filenames:** Saves each PDF with a unique name to prevent overwriting.
- **Download Logging:** Records all downloads in a JSON log for traceability.

## Usage

1. **Install dependencies:**
   ```bash
   pip install aiohttp aiofiles async_timeout beautifulsoup4 tenacity tqdm
   ```

2. **Run the scraper:**
   ```bash
   python src/main.py
   ```

3. **Results:**
   - All PDFs will be saved in the `downloaded_pdfs/` directory.
   - A log of all downloads will be written to `download_log.json`.

## How It Fits Annotation Workflows

This tool was developed to make life easier for AI/LLM data annotators. By automating the collection of HMMT problems, it enables rapid dataset creation and reduces manual effort, allowing annotators to focus on labeling and analysis rather than data gathering.

## Project Structure

```
src/
  main.py           # Main scraper script
  downloaded_pdfs/  # Output directory for PDFs
  bk_downloads/     # (Optional) Backup or alternate downloads
download_log.json   # Log of all downloaded files
README.md           # Project documentation
```

## License

This project is provided as-is for research and annotation purposes.
