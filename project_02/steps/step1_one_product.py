"""
Step 1 – Fetch ONE product and keep only the fields we need.
Bậc 1 – Lấy MỘT sản phẩm và chỉ giữ các trường cần thiết.

Run / Chạy:  python steps/step1_one_product.py
"""

import json

import requests

API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PRODUCT_ID = 1391347

r = requests.get(API_URL.format(PRODUCT_ID), headers=HEADERS, timeout=10)
print("Status:", r.status_code, "|", r.headers.get("Content-Type"))

p = r.json()
print("Fields returned by the API:", len(p))
print(sorted(p.keys()))

# .get() returns None if a field is missing, instead of crashing with KeyError
# .get() trả về None nếu thiếu trường, thay vì crash với KeyError
product = {
    "id": p.get("id"),
    "name": p.get("name"),
    "url_key": p.get("url_key"),
    "price": p.get("price"),
    "description": p.get("description"),  # still raw HTML here / vẫn là HTML thô
    "images": [img.get("base_url") for img in (p.get("images") or [])],
}

print(json.dumps(product, ensure_ascii=False, indent=2)[:1500])
