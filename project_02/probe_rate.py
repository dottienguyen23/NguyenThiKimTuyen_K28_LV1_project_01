"""
Đo tốc độ request mà Tiki chấp nhận được, trước khi chạy scraper.py.

Gửi request TUẦN TỰ với khoảng nghỉ cố định, dừng ngay khi bị chặn
(HTTP 200 nhưng không phải JSON), rồi báo đã gửi được bao nhiêu request trong bao lâu.

Cách chạy:  python probe_rate.py <giây nghỉ> <số request>
Ví dụ:      python probe_rate.py 1 150      # 1 request/giây, tối đa 150 request (~2,5 phút)
            python probe_rate.py 0.5 300    # 2 request/giây
"""
import sys
import time

import requests

from scraper import API_URL, ID_FILE, USER_AGENT, load_ids

delay = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
n = int(sys.argv[2]) if len(sys.argv) > 2 else 150

# Dùng một đoạn ID khác với các lần chạy trước để kết quả không bị ảnh hưởng bởi cache
ids = load_ids(ID_FILE)[10_000:10_000 + n]

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

target = f"~{1 / delay:.1f} req/s" if delay > 0 else "không nghỉ, nhanh nhất có thể"
print(f"Thử {n} request, nghỉ {delay}s giữa mỗi request ({target})")
ok = not_found = 0
start = time.time()
for i, pid in enumerate(ids, start=1):
    try:
        r = session.get(API_URL.format(pid), timeout=10)
    except requests.RequestException as e:
        print(f"{i:4d}  lỗi mạng: {type(e).__name__}")
        time.sleep(delay)
        continue

    content_type = r.headers.get("Content-Type", "")
    if r.status_code == 200 and "json" not in content_type:
        elapsed = time.time() - start
        print(f"\n❌ BỊ CHẶN ở request thứ {i}, sau {elapsed:.0f}s "
              f"(~{i / elapsed:.1f} req/s). ok={ok}, 404={not_found}")
        sys.exit(1)

    if r.status_code == 200:
        ok += 1
    elif r.status_code == 404:
        not_found += 1
    else:
        print(f"{i:4d}  HTTP {r.status_code}")

    if i % 25 == 0:
        print(f"{i:4d} request | {time.time() - start:5.0f}s | ok={ok} 404={not_found}")
    time.sleep(delay)

elapsed = time.time() - start
print(f"\n✅ KHÔNG bị chặn: {n} request trong {elapsed:.0f}s (~{n / elapsed:.1f} req/s). "
      f"ok={ok}, 404={not_found}")