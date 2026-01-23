#!/usr/bin/env python3
"""
Fetch all legal documents from lex.uz and save as JSON files.
Runs daily via GitHub Actions to keep data fresh.
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
    'ru': 2,
    'en': 1,
}

BASE_URLS = {
    'uz-Cyrl': 'https://lex.uz',
    'uz': 'https://lex.uz/uz',
    'ru': 'https://lex.uz/ru',
    'en': 'https://lex.uz/en',
}

# Document types with their act_type values
DOC_TYPES = {
    'constitution': 1,
    'codes': 21,
    'laws': 22,
    'president': 3,
    'government': 4,
    'ministries': 5,
    'international': 6,
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def fetch_url(url, retries=3):
    """Fetch URL with retries and delay."""
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed for {url}: {e}")
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

def fetch_documents(doc_type, act_type):
    """Fetch documents of a specific type for all languages."""
    print(f"\nFetching {doc_type}...")
    results = {}
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        url = f'{base_url}/search/all?act_type={act_type}&lang={lang_param}'
        
        print(f"  {lang}: {url}")
        html = fetch_url(url)
        docs = parse_html(html)
        results[lang] = docs
        print(f"    Found {len(docs)} documents")
        
        # Be nice to the server
        time.sleep(2)
    
    return results

def fetch_news():
    """Fetch news/recent documents for all languages."""
    print(f"\nFetching news...")
    results = {}
    today = datetime.now().strftime('%d.%m.%Y')
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        url = f'{base_url}/search/all?from=01.01.2020&to={today}&lang={lang_param}'
        
        print(f"  {lang}: {url}")
        html = fetch_url(url)
        docs = parse_html(html)
        results[lang] = docs
        print(f"    Found {len(docs)} documents")
        
        time.sleep(2)
    
    return results

def save_json(data, filename):
    """Save data to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {filename}")

def main():
    print("=" * 50)
    print("Lex.uz Data Fetcher")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 50)
    
    all_data = {}
    
    # Fetch all document types
    for doc_type, act_type in DOC_TYPES.items():
        all_data[doc_type] = fetch_documents(doc_type, act_type)
    
    # Fetch news separately (uses date range)
    all_data['news'] = fetch_news()
    
    # Create data directory if needed
    os.makedirs('data', exist_ok=True)
    
    # Save each document type as separate files per language
    metadata = {
        'last_updated': datetime.now().isoformat(),
        'document_types': {},
    }
    
    for doc_type, lang_data in all_data.items():
        metadata['document_types'][doc_type] = {}
        
        for lang, docs in lang_data.items():
            # Sanitize language code for filename
            lang_safe = lang.replace('-', '_')
            filename = f'data/{doc_type}_{lang_safe}.json'
            save_json(docs, filename)
            
            metadata['document_types'][doc_type][lang] = {
                'file': filename,
                'count': len(docs),
            }
    
    # Save metadata
    save_json(metadata, 'metadata.json')
    
    print("\n" + "=" * 50)
    print("Fetch complete!")
    print(f"Finished at: {datetime.now().isoformat()}")
    print("=" * 50)

if __name__ == '__main__':
    main()
