#!/usr/bin/env python3
"""
Web scraper for Youngsville.us livestream page
Extracts text content from HTML Packet and HTML Agenda links
Combines into a single file for NotebookLM
"""

import os
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin
import time

# Configuration
# This is the municode iframe URL that contains the meeting list
BASE_URL = "https://meetings.municode.com/PublishPage/index?cid=YOUNGSVILA&ppid=5d44059a-1e19-4452-a226-babc4b369c18&p={}"
TOTAL_PAGES = 4  # The municode page has 4 pages of meetings
SCRAPED_DIR = Path("./scraped_content")
OUTPUT_FILE = "notebooklm_source.txt"
TARGET_LINK_TEXTS = ["HTML Packet", "HTML Agenda"]

# Headers to mimic a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
}


def setup_directory():
    """Create and clean the scraped content directory"""
    print(f"Setting up directory: {SCRAPED_DIR}")
    SCRAPED_DIR.mkdir(exist_ok=True)

    # Clean existing .txt files
    for txt_file in SCRAPED_DIR.glob("*.txt"):
        txt_file.unlink()
        print(f"  Removed existing file: {txt_file.name}")


def fetch_page(url):
    """Fetch a webpage with error handling"""
    try:
        print(f"Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def extract_text_content(html_content):
    """Extract clean text content from HTML"""
    soup = BeautifulSoup(html_content, 'html.parser')

    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    # Get text from body or whole document
    body = soup.find('body')
    if body:
        text = body.get_text(separator='\n', strip=True)
    else:
        text = soup.get_text(separator='\n', strip=True)

    # Clean up multiple newlines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return '\n'.join(lines)


def parse_alt_text(alt_text):
    """
    Parse the alt text to extract date, meeting type, and document type.
    Example: "HTML Agenda for November 13, 2025 City Council Regular Meeting at 6:00 PM"
    Returns: (doc_type, meeting_info) where meeting_info includes date and meeting description
    """
    # Determine document type based on TARGET_LINK_TEXTS
    doc_type = None
    for target in TARGET_LINK_TEXTS:
        if alt_text.startswith(target):
            doc_type = target
            break
    
    if not doc_type:
        return None, None
    
    # Extract meeting info (everything after "for ")
    # Use dynamic regex based on the detected doc_type
    pattern = rf'{re.escape(doc_type)} for (.+)'
    match = re.match(pattern, alt_text)
    if match:
        meeting_info = match.group(1).strip()
    else:
        meeting_info = alt_text.replace(doc_type, '').strip()
        if meeting_info.startswith('for '):
            meeting_info = meeting_info[4:]
    
    return doc_type, meeting_info


def find_target_links(html_content):
    """Find all HTML Packet and HTML Agenda links with full meeting information"""
    soup = BeautifulSoup(html_content, 'html.parser')
    target_links = []

    # Find all links to adaHtmlDocument
    for link in soup.find_all('a', href=True):
        if 'adaHtmlDocument' not in link['href']:
            continue

        # Check if the link contains an image with alt text matching our targets
        img = link.find('img')
        if img and img.get('alt'):
            alt_text = img.get('alt', '')
            # Check if alt text starts with "HTML Agenda" or "HTML Packet"
            for target in TARGET_LINK_TEXTS:
                if alt_text.startswith(target):
                    absolute_url = link['href']
                    doc_type, meeting_info = parse_alt_text(alt_text)
                    target_links.append({
                        'url': absolute_url,
                        'text': target,
                        'full_alt_text': alt_text,
                        'meeting_info': meeting_info or 'Unknown Meeting'
                    })
                    print(f"  Found: {alt_text}")
                    break

    return target_links


def sanitize_filename(text, max_length=100):
    """
    Sanitize text for use as a filename.
    Removes/replaces characters that are not safe for filenames.
    """
    # Replace common problematic characters
    sanitized = text.replace(':', '').replace(',', '').replace('/', '-')
    sanitized = sanitized.replace('\\', '-').replace('?', '').replace('*', '')
    sanitized = sanitized.replace('"', '').replace('<', '').replace('>', '')
    sanitized = sanitized.replace('|', '-')
    # Replace spaces with underscores
    sanitized = sanitized.replace(' ', '_')
    # Remove any remaining non-alphanumeric characters except underscore, dash, and period
    sanitized = re.sub(r'[^\w\-.]', '', sanitized)
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


def process_links(links):
    """Process each link and save content to individual files"""
    for idx, link_info in enumerate(links, start=1):
        url = link_info['url']
        link_text = link_info['text']
        meeting_info = link_info.get('meeting_info', 'Unknown Meeting')
        full_alt_text = link_info.get('full_alt_text', link_text)

        print(f"\n[{idx}/{len(links)}] Processing: {full_alt_text}")

        # Fetch the page
        html_content = fetch_page(url)
        if not html_content:
            print(f"  Skipping due to fetch error")
            continue

        # Extract text
        text_content = extract_text_content(html_content)

        # Create descriptive filename with meeting info and document type
        doc_type_short = 'agenda' if 'Agenda' in link_text else 'packet'
        descriptive_name = sanitize_filename(f"{meeting_info}_{doc_type_short}")
        filename = f"{descriptive_name}.txt"
        filepath = SCRAPED_DIR / filename

        # Add enhanced header to content with full meeting information
        header_lines = [
            f"DOCUMENT TYPE: {link_text}",
            f"MEETING: {meeting_info}",
            f"URL: {url}",
            '=' * 80,
        ]
        content_with_header = '\n'.join(header_lines) + f"\n\n{text_content}\n\n"

        # Save to file
        filepath.write_text(content_with_header, encoding='utf-8')
        print(f"  Saved: {filename} ({len(text_content)} characters)")

        # Be respectful with rate limiting
        time.sleep(1)


def combine_files():
    """Combine all scraped files into a single output file"""
    print(f"\nCombining files into {OUTPUT_FILE}...")

    # Get all .txt files sorted by name
    txt_files = sorted(SCRAPED_DIR.glob("*.txt"))

    if not txt_files:
        print("  WARNING: No files found to combine!")
        return

    combined_content = []
    combined_content.append("=" * 80)
    combined_content.append("YOUNGSVILLE LIVESTREAM MEETING DOCUMENTS")
    combined_content.append(f"Scraped from: {BASE_URL}")
    combined_content.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    combined_content.append("=" * 80)
    combined_content.append("\n\n")

    for txt_file in txt_files:
        print(f"  Adding: {txt_file.name}")
        content = txt_file.read_text(encoding='utf-8')
        combined_content.append(content)
        combined_content.append("\n" + "=" * 80 + "\n\n")

    # Write combined file
    output_path = Path(OUTPUT_FILE)
    final_content = '\n'.join(combined_content)
    output_path.write_text(final_content, encoding='utf-8')

    print(f"\n✓ Successfully created {OUTPUT_FILE}")
    print(f"  Total size: {len(final_content):,} characters")
    print(f"  Files combined: {len(txt_files)}")


def main():
    """Main execution function"""
    print("=" * 80)
    print("YOUNGSVILLE LIVESTREAM SCRAPER")
    print("=" * 80)
    print()

    # Step 1: Setup directory
    setup_directory()
    print()

    # Step 2: Fetch all pages and collect links
    print(f"Fetching {TOTAL_PAGES} pages of meetings from municode...")
    all_target_links = []

    for page_num in range(1, TOTAL_PAGES + 1):
        page_url = BASE_URL.format(page_num)
        print(f"\n[Page {page_num}/{TOTAL_PAGES}]")

        page_content = fetch_page(page_url)
        if not page_content:
            print(f"  WARNING: Could not fetch page {page_num}. Skipping.")
            continue

        # Find links on this page
        page_links = find_target_links(page_content)
        all_target_links.extend(page_links)

    print(f"\n{'='*80}")
    print(f"Total links found across all pages: {len(all_target_links)}")
    print(f"{'='*80}")

    if not all_target_links:
        print("ERROR: No links found. Exiting.")
        return
    print()

    # Step 3: Process each link
    print("Processing links...")
    process_links(all_target_links)
    print()

    # Step 4: Combine all files
    combine_files()
    print()

    print("=" * 80)
    print("SCRAPING COMPLETE!")
    print(f"Your NotebookLM source file is ready: {OUTPUT_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    main()
