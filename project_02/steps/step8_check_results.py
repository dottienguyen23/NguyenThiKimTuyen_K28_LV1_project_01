"""
Step 8 – Check the result: is anything missing or duplicated? Which errors are worth retrying?
Bậc 8 – Kiểm tra kết quả: có thiếu hay trùng không? Lỗi nào đáng chạy lại?

Run after the scraper finishes / Chạy sau khi scraper xong:
    python steps/step8_check_results.py
"""

import csv
import glob
import json
from collections import Counter

ID_FILE = "data/ids.csv"
OUTPUT_DIR = "output"
ERROR_DIR = "errors"
PERMANENT_ERRORS = {"HTTP 404"}   # product no longer exists -> never retry / sản phẩm không còn -> không chạy lại


def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip()
            if value.isdigit():
                ids.append(value)
    return list(dict.fromkeys(ids))


ids = read_ids(ID_FILE)

product_ids = []
for path in sorted(glob.glob(f"{OUTPUT_DIR}/products_*.json")):
    with open(path, encoding="utf-8") as f:
        product_ids += [str(p["id"]) for p in json.load(f)]

errors = []
for path in sorted(glob.glob(f"{ERROR_DIR}/errors_*.csv")):
    with open(path, encoding="utf-8") as f:
        errors += list(csv.DictReader(f))   # works for both 2-column and 3-column files

ok, err = len(product_ids), len(errors)
print(f"Products OK : {ok}")
print(f"Errors      : {err}")
print(f"OK + errors : {ok + err} / IDs: {len(ids)} -> "
      f"{'MATCH ✅' if ok + err == len(ids) else 'MISMATCH ❌ (unfinished or missing batches)'}")
print(f"Duplicate ids in output: {ok - len(set(product_ids))}")

print("\nErrors by reason / Lỗi theo loại:")
for reason, count in Counter(e["reason"] for e in errors).most_common():
    print(f"  {reason:<20} {count}")

retry = [e["id"] for e in errors if e["reason"] not in PERMANENT_ERRORS]
with open("retry_ids.csv", "w", encoding="utf-8") as f:
    f.write("id\n" + "\n".join(retry) + "\n")
print(f"\n{len(retry)} IDs worth retrying -> retry_ids.csv")
