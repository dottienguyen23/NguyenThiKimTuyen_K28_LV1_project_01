"""
Step 9 – Second pass: retry the IDs that failed for a temporary reason.
Bậc 9 – Lượt hai: chạy lại các ID bị lỗi tạm thời.

Input  : retry_ids.csv (written by steps/step8_check_results.py: every error except HTTP 404)
Output : output_retry/products_XXXX.json + errors_retry/errors_XXXX.csv
         (separate folders, so the first pass's checkpoint files are not touched)
         (thư mục riêng, để không đụng vào checkpoint của lượt một)

Two improvements over scraper_simple.py, learned from the first run:
Hai cải tiến so với scraper_simple.py, rút ra từ lần chạy đầu:
  1. TIMEOUT = 5 instead of 10: a dead request costs 6 s instead of 11 s
     TIMEOUT = 5 thay vì 10: một request chết tốn 6 giây thay vì 11 giây
  2. Circuit breaker: after 20 network errors in a row, stop sending requests,
     wait until the API answers again, then retry the same ID.
     Cầu dao (circuit breaker): sau 20 lỗi mạng liên tiếp, ngừng gửi request,
     chờ đến khi API trả lời lại, rồi chạy lại đúng ID đó.
     -> batches 0062-0073 of the first run (~12,000 timeouts) would not happen again
     -> các batch 0062-0073 của lần chạy đầu (~12.000 timeout) sẽ không lặp lại

Run from the project folder / Chạy từ thư mục project:
    python steps/step8_check_results.py      # writes retry_ids.csv
    python -u steps/step9_retry_failed.py 2>&1 | tee -a logs/retry.log
"""

import csv
import html
import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

ID_FILE = "retry_ids.csv"
OUTPUT_DIR = "output_retry"
ERROR_DIR = "errors_retry"
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

BATCH_SIZE = 1000
DELAY = 1.0
TIMEOUT = 5                  # first run: 10 / lần đầu: 10
NETWORK_ERRORS = {"ReadTimeout", "ConnectTimeout", "Timeout", "ConnectionError"}
MAX_ERRORS_IN_A_ROW = 20     # circuit breaker threshold / ngưỡng ngắt cầu dao
WAIT_STEP = 120              # seconds between "is it back?" checks / giây giữa các lần kiểm tra
MAX_WAIT = 3600              # give up after 1 hour; rerun later to resume / quá 1 giờ thì dừng; chạy lại sau để tiếp tục


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
        r = session.get(API_URL.format(product_id), headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        return None, type(e).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    if "json" not in r.headers.get("Content-Type", ""):
        return None, "blocked"
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


def wait_until_api_answers(session, probe_id):
    """Return True when the API answers again, False after MAX_WAIT seconds.
    Trả về True khi API trả lời lại, False nếu quá MAX_WAIT giây."""
    waited = 0
    while waited < MAX_WAIT:
        print(f"   API not answering, waiting {WAIT_STEP}s (waited {waited // 60} min) / "
              f"API không trả lời, chờ {WAIT_STEP}s")
        time.sleep(WAIT_STEP)
        waited += WAIT_STEP
        _, error = get_product(session, probe_id)
        if error not in NETWORK_ERRORS and error != "blocked":
            print(f"   API is back after ~{waited // 60} min / API đã trả lời lại")
            return True
    return False


def save_batch(batch_no, products, errors):
    with open(f"{ERROR_DIR}/errors_{batch_no:04d}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "reason"])
        writer.writerows(errors)
    out = f"{OUTPUT_DIR}/products_{batch_no:04d}.json"
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    os.replace(out + ".tmp", out)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(ERROR_DIR, exist_ok=True)

    ids = read_ids(ID_FILE)
    total_batches = (len(ids) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"{len(ids)} IDs to retry, {total_batches} batches / {len(ids)} ID cần chạy lại")
    session = requests.Session()

    for start in range(0, len(ids), BATCH_SIZE):
        batch_no = start // BATCH_SIZE + 1
        batch = ids[start:start + BATCH_SIZE]
        if os.path.exists(f"{OUTPUT_DIR}/products_{batch_no:04d}.json"):
            print(f"Batch {batch_no}: done, skip / đã xong, bỏ qua")
            continue

        products, errors = [], []
        in_a_row = 0
        t0 = time.time()
        i = 0
        while i < len(batch):
            product_id = batch[i]
            product, error = get_product(session, product_id)
            time.sleep(DELAY)

            if error in NETWORK_ERRORS or error == "blocked":
                in_a_row += 1
                if in_a_row >= MAX_ERRORS_IN_A_ROW:
                    # Circuit breaker: the last 20 failures were the connection, not the products.
                    # Forget them and redo those IDs once the API answers again.
                    # Cầu dao: 20 lỗi vừa rồi là do kết nối, không phải do sản phẩm.
                    # Bỏ các lỗi đó và chạy lại các ID này khi API trả lời lại.
                    del errors[-(MAX_ERRORS_IN_A_ROW - 1):]
                    i -= MAX_ERRORS_IN_A_ROW - 1
                    in_a_row = 0
                    if not wait_until_api_answers(session, product_id):
                        print(f"Stopped: no answer for {MAX_WAIT // 60} min. Rerun later, "
                              f"batch {batch_no} will be redone / Dừng: chạy lại sau")
                        return
                    continue
            else:
                in_a_row = 0

            if product:
                products.append(product)
            else:
                errors.append([product_id, error])
            i += 1

        save_batch(batch_no, products, errors)
        print(f"Batch {batch_no}/{total_batches}: recovered={len(products)} still failing={len(errors)} "
              f"({(time.time() - t0) / 60:.0f} min)")

    print("Done / Xong! Next: python steps/step10_final_report.py")


if __name__ == "__main__":
    main()
