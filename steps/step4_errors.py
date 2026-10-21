"""
Step 4 – Handle errors: a bad ID is recorded with a reason, the loop continues.
Bậc 4 – Xử lý lỗi: ID lỗi được ghi lại kèm lý do, vòng lặp vẫn chạy tiếp.

Run / Chạy:  python steps/step4_errors.py
"""

import csv
import html
import json
import re
import time

import requests
from bs4 import BeautifulSoup

ID_FILE = "data/ids.csv"
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DELAY = 1.0
LIMIT = 50


def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip()
            if value.isdigit():
                ids.append(value)
    return list(dict.fromkeys(ids))


def clean_description(raw_html):
    if not raw_html:
        return ""
    text = BeautifulSoup(raw_html, "html.parser").get_text(" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def get_product(session, product_id):
    """Return (product, None) on success, or (None, reason) on failure.
    Trả về (sản phẩm, None) nếu thành công, hoặc (None, lý do) nếu lỗi."""
    try:
        # timeout=10: without it, a dead connection can hang forever
        # timeout=10: không có nó, một kết nối chết có thể treo mãi mãi
        r = session.get(API_URL.format(product_id), headers=HEADERS, timeout=10)
    except requests.RequestException as e:      # base class: Timeout, ConnectionError, ...
        return None, type(e).__name__

    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"    # 404 = product gone / sản phẩm không còn, 429 = too fast / quá nhanh

    try:
        p = r.json()
    except ValueError:                          # body is not valid JSON / body không phải JSON
        return None, "bad_json"

    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    }, None


ids = read_ids(ID_FILE)[:LIMIT]
session = requests.Session()   # reuses the connection -> faster / dùng lại kết nối -> nhanh hơn

products, errors = [], []
for product_id in ids:
    product, error = get_product(session, product_id)
    if product:
        products.append(product)
    else:
        errors.append([product_id, error])
    time.sleep(DELAY)

with open("products_test.json", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)

with open("errors_test.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "reason"])
    writer.writerows(errors)

print(f"ok={len(products)} errors={len(errors)}")
