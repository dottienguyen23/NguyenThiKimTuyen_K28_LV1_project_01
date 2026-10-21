"""
Đo tốc độ request mà Tiki chấp nhận được, trước khi chạy scraper.
Measure the request rate Tiki accepts, before running the scraper.

Gửi request TUẦN TỰ với KHOẢNG CÁCH CỐ ĐỊNH giữa hai lần bắt đầu request,
dừng ngay khi bị chặn, rồi báo đã gửi được bao nhiêu request trong bao lâu.

Cải tiến so với bản đầu / Improvements over the first version:
  1. Tham số là KHOẢNG CÁCH giữa hai lần bắt đầu request, không phải thời gian nghỉ sau request.
     Bản đầu nghỉ sau khi nhận phản hồi, nên "1 giây" thực tế là ~1,33 giây (~0,75 req/s).
     Giờ 1.0 nghĩa là đúng 1 req/s (nếu Tiki trả lời nhanh hơn 1 giây).
  2. Tham số thứ ba chọn đoạn ID, để mỗi lần đo dùng sản phẩm khác nhau.
  3. Trước khi đo, kiểm tra API đang trả JSON (không đo nhầm lệnh chặn cũ).
  4. 429 / 403 / nhiều lỗi mạng liên tiếp cũng được coi là bị chặn, không chỉ trang HTML.

Cách chạy:  python probe_rate.py <khoảng cách giây> <số request> [ID bắt đầu]
Ví dụ:      python probe_rate.py 1 300            # 1,0 req/s
            python probe_rate.py 0.85 300 20000   # ~1,18 req/s, dùng ID từ vị trí 20.000
"""
import sys
import time
from collections import Counter

import requests

from scraper import API_URL, ID_FILE, USER_AGENT, load_ids

interval = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
n = int(sys.argv[2]) if len(sys.argv) > 2 else 150
offset = int(sys.argv[3]) if len(sys.argv) > 3 else 10_000

PROBE_ID = "1391347"        # sản phẩm chắc chắn tồn tại / a product known to exist
TIMEOUT = 10
MAX_NETWORK_ERRORS = 5      # số lỗi mạng liên tiếp coi như bị chặn / mất mạng

ids = load_ids(ID_FILE)[offset:offset + n]

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

# --- 0. Kiểm tra API sẵn sàng / Check the API is ready ---
r = session.get(API_URL.format(PROBE_ID), timeout=TIMEOUT)
if r.status_code != 200 or "json" not in r.headers.get("Content-Type", ""):
    print(f"⚠️ API chưa sẵn sàng (HTTP {r.status_code}, {r.headers.get('Content-Type', '?')}). "
          f"Có thể lệnh chặn cũ vẫn còn: chờ rồi chạy lại.")
    sys.exit(2)

target = f"{1 / interval:.2f} req/s" if interval > 0 else "nhanh nhất có thể"
print(f"Thử {n} request, ID từ vị trí {offset}, cứ {interval}s bắt đầu một request (mục tiêu {target})")

counts = Counter()
network_in_a_row = 0
response_times = []
start = time.monotonic()

for i, pid in enumerate(ids, start=1):
    t0 = time.monotonic()
    try:
        r = session.get(API_URL.format(pid), timeout=TIMEOUT)
        response_times.append(time.monotonic() - t0)
        ctype = r.headers.get("Content-Type", "")
        if r.status_code == 200 and "json" not in ctype:
            result = "blocked"
        elif r.status_code in (403, 429):
            result = f"HTTP {r.status_code}"
        elif r.status_code == 200:
            result = "ok"
        else:
            result = f"HTTP {r.status_code}"
        network_in_a_row = 0
    except requests.RequestException as e:
        result = type(e).__name__
        network_in_a_row += 1
    counts[result] += 1

    elapsed = time.monotonic() - start
    if result in ("blocked", "HTTP 403", "HTTP 429") or network_in_a_row >= MAX_NETWORK_ERRORS:
        print(f"\n❌ BỊ CHẶN ({result}) ở request thứ {i}, sau {elapsed:.0f}s "
              f"(thực tế ~{i / elapsed:.2f} req/s). {dict(counts)}")
        sys.exit(1)

    if i % 25 == 0:
        print(f"{i:4d} request | {elapsed:5.0f}s | {i / elapsed:.2f} req/s | "
              f"ok={counts['ok']} 404={counts['HTTP 404']}")

    # Chỉ nghỉ phần còn thiếu của khoảng cách / sleep only what is left of the interval
    time.sleep(max(0.0, interval - (time.monotonic() - t0)))

elapsed = time.monotonic() - start
avg = sum(response_times) / len(response_times) if response_times else 0
print(f"\n✅ KHÔNG bị chặn: {n} request trong {elapsed:.0f}s (thực tế ~{n / elapsed:.2f} req/s). "
      f"{dict(counts)}")
print(f"   Tiki trả lời trung bình {avg:.2f}s/request. "
      f"Ở tốc độ này, 200.000 ID ≈ {200_000 / (n / elapsed) / 3600:.0f} giờ")
