"""
Probe: how many parallel workers does Tiki tolerate before it blocks?
Thử: Tiki chịu được bao nhiêu worker song song trước khi chặn?

Tests 1, 2, 3, 5 workers in that order, on fresh IDs each time, and STOPS at the
first level that shows a block, 429 or a burst of timeouts.
Thử lần lượt 1, 2, 3, 5 worker, mỗi mức dùng ID khác nhau, và DỪNG ngay ở mức
đầu tiên có dấu hiệu bị chặn, 429 hoặc nhiều timeout.

⚠️ Run only when no other scraper is running (step 9 finished).
⚠️ Chỉ chạy khi không có scraper nào khác đang chạy (step 9 đã xong).

Run from the project folder / Chạy từ thư mục project:
    python -u steps/probe_workers.py 2>&1 | tee -a logs/probe_workers.log
"""

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

ID_FILE = "data/ids.csv"
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {"User-Agent": "Mozilla/5.0"}

LEVELS = [1, 2, 3, 5]      # worker counts to try, slowest first / số worker cần thử, chậm nhất trước
REQUESTS_PER_LEVEL = 100   # small sample: enough to see a block, not enough to anger the API
DELAY = 1.0                # per worker, same as scraper.py / mỗi worker, giống scraper.py
TIMEOUT = 10
COOLDOWN = 120             # seconds of rest between levels / giây nghỉ giữa các mức
START_AT = 150_000         # take IDs from the end of the list, away from the first 150 used by probe_rate.py


def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip()
            if value.isdigit():
                ids.append(value)
    return list(dict.fromkeys(ids))


def fetch(product_id):
    time.sleep(DELAY)
    try:
        r = requests.get(API_URL.format(product_id), headers=HEADERS, timeout=TIMEOUT)
    except requests.RequestException as e:
        return type(e).__name__
    if r.status_code != 200:
        return f"HTTP {r.status_code}"
    if "json" not in r.headers.get("Content-Type", ""):
        return "blocked"
    return "ok"


def looks_blocked(counts):
    """A level fails if Tiki pushed back in any way.
    Một mức thất bại nếu Tiki phản ứng theo bất kỳ cách nào."""
    timeouts = sum(n for k, n in counts.items() if "Timeout" in k or k == "ConnectionError")
    return counts["blocked"] > 0 or counts["HTTP 429"] > 0 or counts["HTTP 403"] > 0 or timeouts >= 5


def main():
    ids = read_ids(ID_FILE)[START_AT:]
    results = []
    print(f"Testing workers {LEVELS}, {REQUESTS_PER_LEVEL} requests each, {COOLDOWN}s rest between levels")

    for n, workers in enumerate(LEVELS):
        sample = ids[n * REQUESTS_PER_LEVEL:(n + 1) * REQUESTS_PER_LEVEL]   # fresh IDs per level
        t0 = time.time()
        with ThreadPoolExecutor(workers) as ex:
            counts = Counter(ex.map(fetch, sample))
        seconds = time.time() - t0
        rate = len(sample) / seconds
        blocked = looks_blocked(counts)
        results.append((workers, seconds, rate, counts, blocked))

        detail = ", ".join(f"{k}={v}" for k, v in counts.most_common())
        print(f"{workers} worker(s): {seconds:5.0f}s | {rate:.2f} req/s | {detail} "
              f"-> {'❌ PUSHED BACK' if blocked else '✅ ok'}")

        if blocked:
            print("Stopping here: going faster would only make the block longer.")
            print("Dừng tại đây: chạy nhanh hơn chỉ làm thời gian bị chặn kéo dài.")
            break
        if n < len(LEVELS) - 1:
            time.sleep(COOLDOWN)

    safe = [w for w, _, _, _, b in results if not b]
    print("\n" + "=" * 60)
    if safe:
        best = max(safe)
        rate = next(r for w, _, r, _, _ in results if w == best)
        print(f"Highest safe level tested: {best} worker(s), {rate:.2f} req/s")
        print(f"-> 200,000 IDs ≈ {200_000 / rate / 3600:.0f} h (without blocks)")
    else:
        print("Even 1 worker was pushed back: wait and try again later.")
    if len(safe) == len(LEVELS):
        print(f"No block up to {LEVELS[-1]} workers: the real limit is higher than tested.")


if __name__ == "__main__":
    main()
