"""
Step 8b – Profile the scraped data: is the content good, not just complete?
Bậc 8b – Kiểm tra chất lượng dữ liệu: nội dung có tốt không, không chỉ là đủ hay thiếu?

Run from the project folder / Chạy từ thư mục project:
    python steps/step8b_profile_products.py
"""

import csv
import glob
import json
import statistics
from collections import Counter

OUTPUT_DIR = "output"
ERROR_DIR = "errors"
FIELDS = ["id", "name", "url_key", "price", "description", "images"]

# ---------- 1. Products: read one file at a time (200k products do not fit nicely in memory) ----------
# ---------- 1. Sản phẩm: đọc từng file một (200k sản phẩm chiếm nhiều bộ nhớ) ----------
files = sorted(glob.glob(f"{OUTPUT_DIR}/products_*.json"))
total = 0
ids = Counter()
missing = Counter()          # field is None or empty / trường bị None hoặc rỗng
prices = []
zero_price = 0
desc_lengths = []
image_counts = Counter()
double_space_names = 0
per_batch_ok = {}

for path in files:
    batch_no = int(path.split("_")[-1].split(".")[0])
    with open(path, encoding="utf-8") as f:
        products = json.load(f)
    per_batch_ok[batch_no] = len(products)

    for p in products:
        total += 1
        ids[p.get("id")] += 1
        for field in FIELDS:
            if p.get(field) in (None, "", []):
                missing[field] += 1

        price = p.get("price")
        if isinstance(price, (int, float)):
            prices.append(price)
            if price == 0:
                zero_price += 1

        desc_lengths.append(len(p.get("description") or ""))
        image_counts[len(p.get("images") or [])] += 1
        if "  " in (p.get("name") or ""):
            double_space_names += 1

print("=" * 60)
print(f"Output files : {len(files)}")
print(f"Products     : {total:,}")
print(f"Duplicate ids: {sum(c - 1 for c in ids.values() if c > 1)}")

print("\nMissing or empty fields / Trường bị thiếu hoặc rỗng:")
for field in FIELDS:
    pct = missing[field] / total * 100 if total else 0
    print(f"  {field:<12} {missing[field]:>8,}  ({pct:.1f}%)")

if prices:
    q = statistics.quantiles(prices, n=4)
    print("\nPrice (VND) / Giá:")
    print(f"  min {min(prices):,.0f} | Q1 {q[0]:,.0f} | median {q[1]:,.0f} | "
          f"Q3 {q[2]:,.0f} | max {max(prices):,.0f}")
    print(f"  price = 0: {zero_price:,}")

if desc_lengths:
    print("\nDescription length (characters) / Độ dài description:")
    print(f"  median {statistics.median(desc_lengths):,.0f} | max {max(desc_lengths):,} | "
          f"under 50 chars: {sum(1 for n in desc_lengths if n < 50):,}")

print("\nImages per product / Số ảnh mỗi sản phẩm:")
for n, count in sorted(image_counts.items())[:10]:
    print(f"  {n:>3} images: {count:,}")

print(f"\nNames with double spaces / Tên có 2 khoảng trắng liền nhau: {double_space_names:,}")

# ---------- 2. Errors: by reason, and by batch (a spike = a bad period, e.g. a block or Wi-Fi drop) ----------
# ---------- 2. Lỗi: theo loại, và theo batch (tăng đột biến = một giai đoạn có vấn đề) ----------
reasons = Counter()
per_batch_err = {}
for path in sorted(glob.glob(f"{ERROR_DIR}/errors_*.csv")):
    batch_no = int(path.split("_")[-1].split(".")[0])
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    per_batch_err[batch_no] = len(rows)
    reasons.update(r["reason"] for r in rows)

print("\n" + "=" * 60)
print(f"Errors: {sum(reasons.values()):,}")
for reason, count in reasons.most_common():
    print(f"  {reason:<20} {count:>8,}")

print("\nBatches with an unusual error count / Batch có số lỗi bất thường:")
if per_batch_err:
    typical = statistics.median(per_batch_err.values())
    unusual = {b: n for b, n in per_batch_err.items() if n > typical * 1.5 or n < typical * 0.5}
    print(f"  typical errors per batch: {typical:.0f}")
    for b, n in sorted(unusual.items()):
        print(f"  batch {b:04d}: {n} errors, {per_batch_ok.get(b, 0)} ok")
    if not unusual:
        print("  none")
