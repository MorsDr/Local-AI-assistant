# ai_helper

A lightweight, asynchronous web scraping and automation assistant built with Python. 

Currently in active development, focusing on high-efficiency data extraction and robust session logging.

## Core Stack
* Language: Python (Asyncio, aiohttp)
* Scraper: DuckDuckGo API + BeautifulSoup4 (with custom link ranking and HTML parsing)
* Logging: Standard automated text logging (Pathlib integrated)

## Current Features
* Advanced Web Search & Parsing: Fully asynchronous module that queries the web, extracts clean content, ranks links on the fly, and bypasses heavy overhead.
* Automated Logger: Generates structured log files inside the project directory upon session startup and tracks execution errors in real time.

## Quick Start

### 1. Installation
Clone the repository and install the required dependencies:
```bash
pip install -r requirements.txt
