import os
import pandas as pd

html_path = "/Users/michael/RecursiveRAO/data/cache/10-K_2025-01-26_0001045810-25-000023.html"

with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

print("Parsing tables...")
try:
    tables = pd.read_html(html_content, flavor="lxml")
    print(f"Total tables: {len(tables)}")
    for idx, df in enumerate(tables):
        # Convert all column names to string to avoid comparison issues
        df.columns = [str(c) for c in df.columns]
        df_str = df.to_string()
        has_segments = "Graphics" in df_str and "Compute" in df_str
        has_markets = "Data Center" in df_str and "Gaming" in df_str
        if has_segments or has_markets:
            print(f"Index {idx}: Shape={df.shape} | Segments={has_segments} | Markets={has_markets}")
except Exception as e:
    import traceback
    traceback.print_exc()
