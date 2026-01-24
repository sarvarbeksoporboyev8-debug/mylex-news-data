#!/usr/bin/env python3
"""
Fetch latest documents from lex.uz and MERGE with existing data.
Only adds new documents, preserves existing ones.
Runs daily via GitHub Actions.
Supports pagination to fetch more than 20 documents.
"""

import json
import re
import os
from datetime import datetime
import requests
import time

# Configuration
LANGUAGES = {
    'uz-Cyrl': 3,
    'uz': 4,
    'ru': 1,
    'en': 2,
}

BASE_URLS = {
    'uz-Cyrl': 'https://lex.uz',
    'uz': 'https://lex.uz/uz',
    'ru': 'https://lex.uz/ru',
    'en': 'https://lex.uz/en',
}

DOC_TYPES = {
    'codes': 21,
    'laws': 22,
}

LANG_SUFFIXES = {
    'uz-Cyrl': 'uz_Cyrl',
    'uz': 'uz',
    'ru': 'ru',
    'en': 'en',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Content-Type': 'application/x-www-form-urlencoded',
}

DATA_DIR = 'data'
MAX_PAGES = 9999  # No practical limit - fetch all pages


def extract_viewstate(html):
    """Extract ASP.NET ViewState and other hidden fields."""
    fields = {}
    patterns = [
        (r'id="__VIEWSTATE" value="([^"]*)"', '__VIEWSTATE'),
        (r'id="__VIEWSTATEGENERATOR" value="([^"]*)"', '__VIEWSTATEGENERATOR'),
        (r'id="__EVENTVALIDATION" value="([^"]*)"', '__EVENTVALIDATION'),
    ]
    for pattern, name in patterns:
        match = re.search(pattern, html)
        if match:
            fields[name] = match.group(1)
    return fields


def has_next_page(html):
    """Check if there's a next page button."""
    return 'ucFoundActsControl$LinkButton1' in html or 'ucFoundActsControl_LinkButton1' in html


def fetch_with_pagination(url, session, max_pages=MAX_PAGES):
    """Fetch all pages using ASP.NET postback pagination."""
    all_docs = []
    seen_ids = set()
    
    # First request
    try:
        response = session.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        html = response.text
    except Exception as e:
        print(f"    Initial request failed: {e}")
        return []
    
    # Parse first page
    docs = parse_html(html)
    for doc in docs:
        if doc['id'] not in seen_ids:
            seen_ids.add(doc['id'])
            all_docs.append(doc)
    
    print(f"    Page 1: {len(docs)} docs")
    
    # Check for more pages
    page = 2
    while has_next_page(html) and page <= max_pages:
        viewstate = extract_viewstate(html)
        if not viewstate.get('__VIEWSTATE'):
            break
        
        # Prepare postback data
        post_data = {
            '__EVENTTARGET': 'ucFoundActsControl$LinkButton1',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': viewstate.get('__VIEWSTATE', ''),
            '__VIEWSTATEGENERATOR': viewstate.get('__VIEWSTATEGENERATOR', ''),
            '__EVENTVALIDATION': viewstate.get('__EVENTVALIDATION', ''),
        }
        
        time.sleep(1)  # Be nice to server
        
        try:
            response = session.post(url, data=post_data, headers=HEADERS, timeout=60)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            print(f"    Page {page} request failed: {e}")
            break
        
        docs = parse_html(html)
        new_count = 0
        for doc in docs:
            if doc['id'] not in seen_ids:
                seen_ids.add(doc['id'])
                all_docs.append(doc)
                new_count += 1
        
        print(f"    Page {page}: {len(docs)} docs ({new_count} new)")
        
        if new_count == 0:
            break  # No new docs, stop
        
        page += 1
    
    return all_docs


def fetch_url(url, retries=3):
    """Fetch URL with retries (simple, no pagination)."""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(5)
    return None


def parse_html(html):
    """Parse HTML and extract document links."""
    if not html:
        return []
    
    docs = []
    seen = set()
    
    pattern = re.compile(
        r'href="(/(?:uz/|ru/|en/)?docs/(-?\d+))"[^>]*>([^<]+)',
        re.IGNORECASE
    )
    
    for match in pattern.finditer(html):
        path = match.group(1)
        doc_id = match.group(2)
        title = match.group(3).strip()
        
        if doc_id in seen or not title:
            continue
        seen.add(doc_id)
        
        docs.append({
            'id': doc_id,
            'title': title.replace('$', 'USD '),
            'url': f'https://lex.uz{path}',
        })
    
    return docs


def load_existing_data(filepath):
    """Load existing JSON data."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []





def save_json(data, filepath):
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_docs(doc_type, act_type):
    """Fetch docs and overwrite existing files."""
    print(f"\nProcessing {doc_type}...")
    total = 0
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        url = f'{base_url}/search/all?act_type={act_type}&lang={lang_param}'
        
        lang_suffix = LANG_SUFFIXES[lang]
        filepath = f'{DATA_DIR}/{doc_type}_{lang_suffix}.json'
        
        print(f"  {lang}: fetching from {url}")
        
        # Fetch with pagination
        session = requests.Session()
        docs = fetch_with_pagination(url, session, max_pages=MAX_PAGES)
        print(f"    Fetched {len(docs)} documents")
        
        # Overwrite
        if docs:
            save_json(docs, filepath)
            print(f"    Saved to {filepath}")
            total += len(docs)
        
        time.sleep(2)
    
    return total


def fetch_homepage_news(html, base_url):
    """Parse news from homepage 'Қонунчиликдаги янгиликлар' section (~10 items)."""
    docs = []
    seen = set()
    
    # Pattern for lx_link items (excludes passport links)
    # Matches: <a class="lx_link" href="/uz/docs/-8012407" target="_blank">Title</a>
    pattern = re.compile(
        r'<a\s+class="lx_link"\s+href="(/(?:uz/|ru/|en/)?docs/(-?\d+))"[^>]*>([^<]+)</a>',
        re.IGNORECASE
    )
    
    for match in pattern.finditer(html):
        path = match.group(1)
        doc_id = match.group(2)
        title = match.group(3).strip()
        
        if doc_id in seen or not title:
            continue
        seen.add(doc_id)
        
        docs.append({
            'id': doc_id,
            'title': title.replace('$', 'USD '),
            'url': f'https://lex.uz{path}',
        })
        
        # Limit to 10 items (homepage news section)
        if len(docs) >= 10:
            break
    
    return docs


def fetch_news():
    """Fetch latest news from homepage (overwrites, not merges)."""
    print(f"\nProcessing news (homepage)...")
    total_fetched = 0
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        
        lang_suffix = LANG_SUFFIXES[lang]
        filepath = f'{DATA_DIR}/news_{lang_suffix}.json'
        
        print(f"  {lang}: fetching homepage {base_url}")
        
        try:
            response = requests.get(base_url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            
            news = fetch_homepage_news(response.text, base_url)
            print(f"    Found {len(news)} news items")
            
            if news:
                save_json(news, filepath)
                print(f"    Saved to {filepath}")
                total_fetched += len(news)
            
        except Exception as e:
            print(f"    Failed: {e}")
        
        time.sleep(2)
    
    return total_fetched


def update_metadata():
    """Update metadata.json with current counts."""
    metadata = {
        'last_updated': datetime.now().isoformat(),
        'document_types': {}
    }
    
    for filename in os.listdir(DATA_DIR):
        if not filename.endswith('.json'):
            continue
        
        filepath = f'{DATA_DIR}/{filename}'
        data = load_existing_data(filepath)
        
        # Parse filename: type_lang.json
        parts = filename.replace('.json', '').rsplit('_', 1)
        if len(parts) != 2:
            continue
        
        doc_type, lang_suffix = parts
        
        # Convert lang_suffix back to lang code
        lang_code = lang_suffix.replace('_', '-')
        
        if doc_type not in metadata['document_types']:
            metadata['document_types'][doc_type] = {}
        
        metadata['document_types'][doc_type][lang_code] = {
            'file': f'data/{filename}',
            'count': len(data)
        }
    
    save_json(metadata, 'metadata.json')
    print("\nUpdated metadata.json")


def main():
    print("=" * 50)
    print("Lex.uz Data Updater")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 50)
    
    total = 0
    
    # Fetch codes and laws (overwrite)
    for doc_type, act_type in DOC_TYPES.items():
        total += fetch_docs(doc_type, act_type)
    
    # Fetch news (10 items from homepage, overwrites daily)
    fetch_news()
    
    # Update metadata
    update_metadata()
    
    print("\n" + "=" * 50)
    print(f"Complete! Fetched {total} documents total.")
    print(f"Finished at: {datetime.now().isoformat()}")
    print("=" * 50)


if __name__ == '__main__':
    main()
