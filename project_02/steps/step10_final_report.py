"""
Step 10 – Final report: combine the first pass and the retry pass.
Bậc 10 – Báo cáo cuối: gộp lượt một và lượt chạy lại.

Every input ID ends up in exactly one place:
Mỗi ID đầu vào nằm ở đúng một nơi:
  - a product in output/ or output_retry/
  - one line in final_errors.csv with its FINAL reason
    (the retry reason replaces the first-pass reason / lý do ở lượt hai thay cho lý do lượt một)

Run from the project folder / Chạy từ thư mục project:
    python steps/step10_final_report.py
"""

import csv
import glob
import json
from collections import Counter

ID_FILE = "data/ids.csv"
PASSES = [("output", "errors"), ("output_retry", "errors_retry")]   # later pass wins / lượt sau được ưu tiên


def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip()
            if value.isdigit():
                ids.append(value)
    return list(dict.fromkeys(ids))


ids = read_ids(ID_FILE)
products = set()
product_rows = 0
reason = {}             # id -> latest error reason / lý do lỗi mới nhất
recovered_in_retry = 0

for out_dir, err_dir in PASSES:
    for path in sorted(glob.glob(f"{out_dir}/products_*.json")):
        with open(path, encoding="utf-8") as f:
            for p in json.load(f):
                pid = str(p["id"])
                product_rows += 1
                if out_dir == "output_retry" and pid in reason:
                    recovered_in_retry += 1
                products.add(pid)
                reason.pop(pid, None)       # fetched now, so no longer an error / đã lấy được, không còn là lỗi
    for path in sorted(glob.glob(f"{err_dir}/errors_*.csv")):
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["id"] not in products:
                    reason[row["id"]] = row["reason"]

missing = [i for i in ids if i not in products and i not in reason]

with open("final_errors.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "reason"])
    writer.writerows(sorted(reason.items(), key=lambda kv: int(kv[0])))

print("=" * 60)
print(f"Input IDs                : {len(ids):,}")
print(f"Products (unique)        : {len(products):,}  ({len(products) / len(ids) * 100:.1f}%)")
print(f"  recovered in retry pass: {recovered_in_retry:,}")
print(f"  duplicate product rows : {product_rows - len(products):,}")
print(f"Final errors             : {len(reason):,}  ({len(reason) / len(ids) * 100:.1f}%)")
print(f"IDs in neither (missing) : {len(missing):,}")
print(f"Products + errors = IDs? : "
      f"{'MATCH ✅' if len(products) + len(reason) == len(ids) and not missing else 'MISMATCH ❌'}")

print("\nFinal errors by reason / Lỗi cuối cùng theo loại:")
for r, count in Counter(reason.values()).most_common():
    print(f"  {r:<20} {count:>8,}  ({count / len(ids) * 100:.1f}% of IDs)")
print("\n-> final_errors.csv (id, reason): the DoD list of failed products and why")
