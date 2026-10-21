"""
Step 2 – Clean the HTML description into plain text.
Bậc 2 – Làm sạch description từ HTML thành text.

Run / Chạy:  python steps/step2_clean_description.py
"""

import html
import re

import requests
from bs4 import BeautifulSoup

API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
PRODUCT_ID = 1391347


def clean_description(raw_html):
    if not raw_html:
        return ""
    # 1. Remove tags. The " " separator stops words from sticking together
    #    Bỏ tag. Dấu " " tránh các chữ bị dính vào nhau
    text = BeautifulSoup(raw_html, "html.parser").get_text(" ")
    # 2. Decode entities: &amp; -> &, &nbsp; -> space
    #    Giải mã ký tự đặc biệt: &amp; -> &, &nbsp; -> khoảng trắng
    text = html.unescape(text)
    # 3. Collapse spaces, tabs, newlines into a single space
    #    Gộp khoảng trắng, tab, xuống dòng thành 1 khoảng trắng
    return re.sub(r"\s+", " ", text).strip()


r = requests.get(API_URL.format(PRODUCT_ID), headers=HEADERS, timeout=10)
raw = r.json().get("description")

print("BEFORE / TRƯỚC:\n", (raw or "")[:400], "\n")
print("AFTER / SAU:\n", clean_description(raw)[:400])
