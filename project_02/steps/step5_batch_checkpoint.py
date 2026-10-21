"""
Step 5 – Batches of 1000 + checkpoint: after a restart, finished batches are skipped.
Bậc 5 – Chia batch 1000 + checkpoint: chạy lại thì bỏ qua các batch đã xong.

Run / Chạy:  python steps/step5_batch_checkpoint.py
Test it / Thử: stop with Ctrl-c in the middle, run again -> finished batches are skipped.
               dừng bằng Ctrl-c giữa chừng, chạy lại -> các batch đã xong được bỏ qua.
"""

import csv
import html
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

ID_FILE = "data/ids.csv"
OUTPUT_DIR = "output"
ERROR_DIR = "errors"
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

BATCH_SIZE = 1000   # never change between runs: the checkpoint depends on batch numbers
                    # không đổi giữa các lần chạy: checkpoint dựa vào số thứ tự batch
DELAY = 1.0
LIMIT = 3000        # must be a multiple of BATCH_SIZE / phải là bội số của BATCH_SIZE


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
    try:
        r = session.get(API_URL.format(product_id), headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        return None, type(e).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        p = r.json()
    except ValueError:
        return None, "bad_json"
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    }, None


def save_batch(batch_no, products, errors):
    with open(f"{ERROR_DIR}/errors_{batch_no:04d}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "reason"])
        writer.writerows(errors)

    # Atomic write: write a temp file, then rename. A crash never leaves a half-written JSON
    # Ghi nguyên tử: ghi file tạm rồi đổi tên. Crash giữa chừng không để lại file JSON dở dang
    out = f"{OUTPUT_DIR}/products_{batch_no:04d}.json"
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    os.replace(out + ".tmp", out)


def main():
    if LIMIT and LIMIT % BATCH_SIZE:
        raise ValueError("LIMIT must be a multiple of BATCH_SIZE / LIMIT phải là bội số của BATCH_SIZE")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ERROR_DIR, exist_ok=True)

    ids = read_ids(ID_FILE)
    if LIMIT:
        ids = ids[:LIMIT]
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE   # ceiling division / chia làm tròn lên
    session = requests.Session()

    for start in range(0, len(ids), BATCH_SIZE):
        batch_no = start // BATCH_SIZE + 1
        batch = ids[start:start + BATCH_SIZE]

        # Checkpoint: the output file itself is the proof that the batch is done
        # Checkpoint: chính file output là bằng chứng batch đã xong
        if os.path.exists(f"{OUTPUT_DIR}/products_{batch_no:04d}.json"):
            print(f"Batch {batch_no}: done, skip / đã xong, bỏ qua")
            continue

        products, errors = [], []
        t0 = time.time()
        for product_id in batch:
            product, error = get_product(session, product_id)
            if product:
                products.append(product)
            else:
                errors.append([product_id, error])
            time.sleep(DELAY)

        save_batch(batch_no, products, errors)
        print(f"Batch {batch_no}/{total_batches}: ok={len(products)} errors={len(errors)} "
              f"({(time.time() - t0) / 60:.0f} min)")


if __name__ == "__main__":
    main()
