"""
Tiki scraper – bản đơn giản (Project 02)

Ý tưởng:
  1. Đọc danh sách ID
  2. Chia thành từng nhóm 1000 ID (batch)
  3. Với mỗi ID: gọi API -> lấy 6 trường -> làm sạch description
  4. Mỗi batch lưu thành 1 file JSON, sản phẩm lỗi lưu vào 1 file CSV
  5. Batch nào đã có file thì bỏ qua (chạy lại không phải làm lại từ đầu)

Chạy:  cd vào thư mục project, rồi  python scraper_simple.py
"""

import csv
import html
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

# ---------- CẤU HÌNH ----------
ID_FILE = "data/ids.csv"
OUTPUT_DIR = "output"
ERROR_DIR = "errors"

API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

BATCH_SIZE = 1000     # số sản phẩm mỗi file
DELAY = 1.0           # giây nghỉ giữa 2 request (nhanh hơn thì Tiki chặn)
WAIT_IF_BLOCKED = 120 # bị chặn thì chờ bao nhiêu giây rồi thử lại
LIMIT = None          # None = chạy hết 200k ID


# ---------- 1. ĐỌC DANH SÁCH ID ----------
def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip()
            if value.isdigit():          # bỏ dòng tiêu đề "id" và dòng trống
                ids.append(value)
    return list(dict.fromkeys(ids))      # bỏ ID trùng, giữ nguyên thứ tự


# ---------- 2. LÀM SẠCH DESCRIPTION ----------
def clean_description(raw_html):
    if not raw_html:
        return ""
    text = BeautifulSoup(raw_html, "html.parser").get_text(" ")  # bỏ tag HTML
    text = html.unescape(text)                                   # &amp; -> &
    return re.sub(r"\s+", " ", text).strip()                     # gộp khoảng trắng thừa


# ---------- 3. LẤY 1 SẢN PHẨM ----------
def get_product(session, product_id):
    """Trả về (sản phẩm, None) nếu thành công, hoặc (None, lý do lỗi)."""
    try:
        r = session.get(API_URL.format(product_id), headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        return None, type(e).__name__                # Timeout, ConnectionError...

    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"         # ví dụ HTTP 404 = sản phẩm không còn

    if "json" not in r.headers.get("Content-Type", ""):
        return None, "blocked"                       # Tiki trả về trang HTML chặn bot

    p = r.json()
    product = {
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    }
    return product, None


def get_product_wait_if_blocked(session, product_id):
    """Như get_product, nhưng nếu bị chặn thì chờ rồi thử lại cùng sản phẩm đó."""
    while True:
        product, error = get_product(session, product_id)
        if error != "blocked":
            return product, error
        print(f"   Bị chặn ở ID {product_id}, chờ {WAIT_IF_BLOCKED}s rồi thử lại...")
        time.sleep(WAIT_IF_BLOCKED)


# ---------- 4. LƯU KẾT QUẢ ----------
def save_batch(batch_no, products, errors):
    with open(f"{ERROR_DIR}/errors_{batch_no:04d}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "reason"])
        writer.writerows(errors)

    # Ghi ra file tạm rồi mới đổi tên: nếu bị tắt giữa chừng sẽ không có file JSON dở dang
    out = f"{OUTPUT_DIR}/products_{batch_no:04d}.json"
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    os.replace(out + ".tmp", out)


# ---------- 5. CHƯƠNG TRÌNH CHÍNH ----------
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ERROR_DIR, exist_ok=True)

    ids = read_ids(ID_FILE)
    if LIMIT:
        ids = ids[:LIMIT]
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Có {len(ids)} ID, chia thành {total_batches} batch")

    session = requests.Session()   # dùng lại kết nối cho mọi request -> nhanh hơn

    for start in range(0, len(ids), BATCH_SIZE):
        batch_no = start // BATCH_SIZE + 1
        batch = ids[start:start + BATCH_SIZE]

        if os.path.exists(f"{OUTPUT_DIR}/products_{batch_no:04d}.json"):
            print(f"Batch {batch_no}: đã có, bỏ qua")
            continue

        products, errors = [], []
        batch_start = time.time()

        for product_id in batch:
            product, error = get_product_wait_if_blocked(session, product_id)
            if product:
                products.append(product)
            else:
                errors.append([product_id, error])
            time.sleep(DELAY)

        save_batch(batch_no, products, errors)

        # Ước tính thời gian còn lại = thời gian batch này × số batch còn lại
        seconds = time.time() - batch_start
        remaining_hours = seconds * (total_batches - batch_no) / 3600
        print(f"Batch {batch_no}/{total_batches}: ok={len(products)} lỗi={len(errors)} "
              f"({seconds / 60:.0f} phút) | còn khoảng {remaining_hours:.1f} giờ")

    print("Xong!")


if __name__ == "__main__":
    main()