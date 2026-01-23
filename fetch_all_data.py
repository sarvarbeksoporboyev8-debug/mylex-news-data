#!/usr/bin/env python3
"""
Fetch latest documents from lex.uz and MERGE with existing data.
Only adds new documents, preserves existing ones.
Runs daily via GitHub Actions.
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

DOC_TYPES = {
    'codes': 21,
    'laws': 22,
    'president': 3,
    'government': 4,
    'ministries': 5,
    'international': 6,
}

LANG_SUFFIXES = {
    'uz-Cyrl': 'uz_Cyrl',
    'uz': 'uz',
    'ru': 'ru',
    'en': 'en',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

DATA_DIR = 'data'


def fetch_url(url, retries=3):
    """Fetch URL with retries."""
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


def merge_documents(existing, new_docs):
    """Merge new documents with existing, avoiding duplicates."""
    existing_ids = {doc['id'] for doc in existing}
    added = []
    
    for doc in new_docs:
        if doc['id'] not in existing_ids:
            added.append(doc)
            existing_ids.add(doc['id'])
    
    # New docs go at the beginning (most recent first)
    return added + existing, len(added)


def save_json(data, filepath):
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_and_merge(doc_type, act_type):
    """Fetch latest docs and merge with existing."""
    print(f"\nProcessing {doc_type}...")
    total_added = 0
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        url = f'{base_url}/search/all?act_type={act_type}&lang={lang_param}'
        
        lang_suffix = LANG_SUFFIXES[lang]
        filepath = f'{DATA_DIR}/{doc_type}_{lang_suffix}.json'
        
        print(f"  {lang}: fetching from {url}")
        html = fetch_url(url)
        new_docs = parse_html(html)
        print(f"    Fetched {len(new_docs)} from lex.uz")
        
        existing = load_existing_data(filepath)
        print(f"    Existing: {len(existing)} documents")
        
        merged, added = merge_documents(existing, new_docs)
        print(f"    Added {added} new documents")
        
        if added > 0:
            save_json(merged, filepath)
            print(f"    Saved {len(merged)} total to {filepath}")
        
        total_added += added
        time.sleep(2)
    
    return total_added


def fetch_news():
    """Fetch latest news and merge."""
    print(f"\nProcessing news...")
    total_added = 0
    today = datetime.now().strftime('%d.%m.%Y')
    
    for lang, lang_param in LANGUAGES.items():
        base_url = BASE_URLS[lang]
        url = f'{base_url}/search/all?from=01.01.2020&to={today}&lang={lang_param}'
        
        lang_suffix = LANG_SUFFIXES[lang]
        filepath = f'{DATA_DIR}/news_{lang_suffix}.json'
        
        print(f"  {lang}: fetching from {url}")
        html = fetch_url(url)
        new_docs = parse_html(html)
        print(f"    Fetched {len(new_docs)} from lex.uz")
        
        existing = load_existing_data(filepath)
        print(f"    Existing: {len(existing)} documents")
        
        merged, added = merge_documents(existing, new_docs)
        print(f"    Added {added} new documents")
        
        if added > 0:
            save_json(merged, filepath)
            print(f"    Saved {len(merged)} total to {filepath}")
        
        total_added += added
        time.sleep(2)
    
    return total_added


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
    print("Lex.uz Data Updater (Merge Mode)")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 50)
    
    total_added = 0
    
    # Fetch and merge all document types
    for doc_type, act_type in DOC_TYPES.items():
        total_added += fetch_and_merge(doc_type, act_type)
    
    # Fetch and merge news
    total_added += fetch_news()
    
    # Update metadata
    update_metadata()
    
    print("\n" + "=" * 50)
    print(f"Complete! Added {total_added} new documents total.")
    print(f"Finished at: {datetime.now().isoformat()}")
    print("=" * 50)


if __name__ == '__main__':
    main()
