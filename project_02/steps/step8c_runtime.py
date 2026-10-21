"""
Step 8c – Runtime analysis: how long did each batch take, where was time lost, when will it finish?
Bậc 8c – Phân tích thời gian chạy: mỗi batch mất bao lâu, mất thời gian ở đâu, khi nào xong?

Two sources / Hai nguồn dữ liệu:
  1. The time each output file was written (works for both scraper versions)
     Thời điểm ghi mỗi file output (dùng được cho cả hai phiên bản scraper)
  2. logs/run.log, if it exists: exact seconds per batch and "blocked" messages
     logs/run.log nếu có: số giây chính xác mỗi batch và các thông báo bị chặn

Run from the project folder / Chạy từ thư mục project:
    python steps/step8c_runtime.py
"""

import glob
import os
import re
import statistics
from datetime import datetime

ID_FILE = "data/ids.csv"
OUTPUT_DIR = "output"
LOG_FILE = "logs/run.log"
BATCH_SIZE = 1000
DELAY = 1.0
PAUSE_FACTOR = 3   # a gap > 3x the median batch = a pause (restart, sleep, block)
                   # khoảng cách > 3 lần trung vị = có gián đoạn (restart, sleep, bị chặn)


def fmt(seconds):
    h, rest = divmod(int(seconds), 3600)
    return f"{h}h{rest // 60:02d}m"


# ---------- 1. Batch durations from file timestamps ----------
# ---------- 1. Thời gian mỗi batch, tính từ thời điểm ghi file ----------
files = sorted(glob.glob(f"{OUTPUT_DIR}/products_*.json"), key=os.path.getmtime)
if len(files) < 2:
    raise SystemExit("Need at least 2 finished batches / Cần ít nhất 2 batch đã xong")

times = [(int(re.search(r"(\d+)\.json$", f).group(1)), os.path.getmtime(f)) for f in files]
gaps = [(b, t - prev_t) for (_, prev_t), (b, t) in zip(times, times[1:])]
median_gap = statistics.median(g for _, g in gaps)
normal = [g for _, g in gaps if g <= median_gap * PAUSE_FACTOR]
pauses = [(b, g) for b, g in gaps if g > median_gap * PAUSE_FACTOR]

first, last = times[0][1], times[-1][1]
wall = last - first
print("=" * 60)
print(f"Finished batches : {len(files)}")
print(f"First batch saved: {datetime.fromtimestamp(first):%Y-%m-%d %H:%M}")
print(f"Last batch saved : {datetime.fromtimestamp(last):%Y-%m-%d %H:%M}")
print(f"Wall-clock time between them: {fmt(wall)}")

print("\nTime per batch (gap between saved files) / Thời gian mỗi batch:")
print(f"  median {median_gap / 60:.1f} min | fastest {min(normal) / 60:.1f} min | "
      f"slowest normal {max(normal) / 60:.1f} min")
print(f"  ≈ {median_gap / BATCH_SIZE:.2f} s per ID "
      f"(of which {DELAY:.1f} s is the deliberate delay / trong đó {DELAY:.1f} s là thời gian nghỉ cố ý)")

lost = sum(g - median_gap for _, g in pauses)
print(f"\nPauses (gap > {PAUSE_FACTOR}x median) / Các lần gián đoạn: {len(pauses)}")
for b, g in pauses:
    end = dict(times)[b]
    print(f"  before batch {b:04d}: {fmt(g)} (saved {datetime.fromtimestamp(end):%m-%d %H:%M})")
print(f"  time lost in pauses ≈ {fmt(lost)} ({lost / wall * 100:.0f}% of wall-clock time)")

# ---------- 2. The log: exact batch seconds (scraper.py) and blocks ----------
# ---------- 2. Log: số giây chính xác (scraper.py) và số lần bị chặn ----------
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        log = f.read()
    exact = [float(s) for s in re.findall(r"batch \d+: ok=\d+ lỗi=\d+ \(([\d.]+)s\)", log)]
    blocks = len(re.findall(r"bị chặn", log, flags=re.IGNORECASE))
    # start banners of both versions / dòng khởi động của cả hai phiên bản
    restarts = len(re.findall(r"scraper\.py v|Có \d+ ID, chia thành", log))
    print(f"\nFrom {LOG_FILE}:")
    if exact:
        print(f"  exact batch times (scraper.py): median {statistics.median(exact) / 60:.1f} min, "
              f"max {max(exact) / 60:.1f} min")
    print(f"  'blocked' messages / thông báo bị chặn: {blocks}")
    print(f"  script starts / số lần khởi động: {restarts}")
else:
    print(f"\n{LOG_FILE} not found: run the scraper with `| tee -a {LOG_FILE}` next time")

# ---------- 3. Forecast ----------
# ---------- 3. Dự báo ----------
if os.path.exists(ID_FILE):
    with open(ID_FILE, encoding="utf-8-sig") as f:
        n_ids = len({line.strip() for line in f if line.strip().isdigit()})
    total_batches = (n_ids + BATCH_SIZE - 1) // BATCH_SIZE
    done = len(glob.glob(f"{OUTPUT_DIR}/products_*.json"))
    left = total_batches - done
    print("\n" + "=" * 60)
    print(f"Progress: {done}/{total_batches} batches ({done / total_batches * 100:.1f}%)")
    print(f"Remaining {left} batches:")
    print(f"  no pauses            : {fmt(left * median_gap)}")
    print(f"  with same pause rate : {fmt(left * wall / (len(files) - 1))}")
    ideal = n_ids * DELAY
    print(f"Lower bound for the full run at {DELAY:.1f} s/ID: {fmt(ideal)} "
          f"(only more workers or a shorter delay can beat this / chỉ tăng worker hoặc giảm delay mới nhanh hơn)")
