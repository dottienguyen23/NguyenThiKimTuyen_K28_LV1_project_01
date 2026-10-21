"""
Step 3 – Loop over many IDs and save everything to ONE JSON file.
Bậc 3 – Lặp qua nhiều ID và lưu tất cả vào MỘT file JSON.

Weakness on purpose: one bad response crashes the whole run, and nothing is saved.
Điểm yếu cố ý: một response lỗi làm crash cả chương trình, và không có gì được lưu.

Run / Chạy:  python steps/step3_loop.py
"""

import html
import json
import re
import time

import requests
from bs4 import BeautifulSoup

ID_FILE = "data/ids.csv"
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DELAY = 1.0   # seconds between requests / giây nghỉ giữa 2 request
LIMIT = 20    # small test / test nhỏ


def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:   # utf-8-sig drops the BOM / bỏ ký tự BOM
        for line in f:
            value = line.strip()
            if value.isdigit():                   # skips the header "id" / bỏ dòng tiêu đề "id"
                ids.append(value)
    return list(dict.fromkeys(ids))               # remove duplicates, keep order / bỏ trùng, giữ thứ tự


def clean_description(raw_html):
    if not raw_html:
        return ""
    text = BeautifulSoup(raw_html, "html.parser").get_text(" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


ids = read_ids(ID_FILE)[:LIMIT]
print(f"{len(ids)} IDs")

products = []
start = time.time()
for product_id in ids:
    r = requests.get(API_URL.format(product_id), headers=HEADERS, timeout=10)
    p = r.json()   # crashes on a blocked/broken response / crash nếu response bị chặn/hỏng
    products.append({
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    })
    time.sleep(DELAY)

with open("products_test.json", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)   # ensure_ascii=False keeps Vietnamese readable

seconds_per_id = (time.time() - start) / len(ids)
print(f"{seconds_per_id:.2f} s/ID -> 200,000 IDs ≈ {seconds_per_id * 200_000 / 3600:.0f} hours")
