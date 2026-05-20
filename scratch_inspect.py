import os
import json
from bs4 import BeautifulSoup

cache_dir = "/Users/michael/RecursiveRAO/data/cache"
files = [f for f in os.listdir(cache_dir) if f.endswith(".html")]

print(f"Total HTML cached files: {len(files)}")
for f_name in sorted(files):
    path = os.path.join(cache_dir, f_name)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"File: {f_name} | Size: {size_mb:.2f} MB")
