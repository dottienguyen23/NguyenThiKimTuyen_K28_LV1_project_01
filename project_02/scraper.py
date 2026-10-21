"""
Tiki Product Scraper – Project 02 (Data Engineer course)

Lấy thông tin ~200k sản phẩm Tiki qua API, lưu thành các file .json (~1000 sản phẩm/file),
chuẩn hóa "description", ghi lại sản phẩm lỗi kèm lý do, và dùng ThreadPoolExecutor để rút ngắn thời gian.

Cách chạy trong VS Code:
  1. Mở thư mục tiki-scraper (File > Open Folder)
  2. Chọn interpreter .venv (Ctrl+Shift+P > "Python: Select Interpreter")
  3. Đặt file ID vào data/ và sửa ID_FILE nếu tên khác
  4. Chỉnh LIMIT ở phần CẤU HÌNH (test nhỏ trước), rồi bấm ▶ Run Python File

Script tự làm theo thứ tự:
  [1] Kiểm tra file ID   [2] Gọi thử API 1 sản phẩm   [3] (tùy chọn) Đo tốc độ
  [4] Lấy dữ liệu theo batch   [5] Kiểm tra kết quả
"""

import csv
import html
import json
import logging
import os
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from urllib3.util.retry import Retry

# ============================================================
# CẤU HÌNH – chỉ cần sửa ở đây
# ============================================================
VERSION = "v4-auto-resume"                   # in ra lúc chạy, để biết chắc đang chạy bản nào

BASE_DIR = Path(__file__).resolve().parent   # luôn tính đường dẫn theo vị trí file này,
                                             # dù VS Code chạy từ thư mục nào
ID_FILE = BASE_DIR / "data" / "ids.csv"      # đổi tên cho đúng file bạn tải về
OUTPUT_DIR = BASE_DIR / "output"
ERROR_DIR = BASE_DIR / "errors"
LOG_DIR = BASE_DIR / "logs"

API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
USER_AGENT = "Mozilla/5.0"

BATCH_SIZE = 1000      # số sản phẩm mỗi file. KHÔNG đổi giữa các lần chạy (checkpoint dựa vào số batch)
MAX_WORKERS = 1        # số request song song. probe_rate.py: 1 thread + nghỉ 1s = an toàn
TIMEOUT = 10           # giây chờ tối đa cho mỗi request
REQUEST_DELAY = 1.0    # giây nghỉ trước mỗi request (mỗi thread)
                       # tốc độ tối đa ≈ MAX_WORKERS / REQUEST_DELAY request/giây

BLOCK_CHECK_EVERY = 120  # khi bị chặn: cứ 120 giây gửi 1 request thử xem đã hết chặn chưa
BLOCK_MAX_WAIT = 3600    # chờ tối đa 1 giờ cho mỗi lần bị chặn, quá thì dừng hẳn

LIMIT = 3000           # None = chạy toàn bộ. Khi test phải là bội số của BATCH_SIZE
RUN_BENCHMARK = False  # True = đo tốc độ tuần tự vs song song trước khi chạy chính

logger = logging.getLogger("tiki")


# ============================================================
# Logging: ghi ra cả màn hình và logs/run.log
# ============================================================
def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    for handler in (logging.FileHandler(LOG_DIR / "run.log", encoding="utf-8"),
                    logging.StreamHandler()):
        handler.setFormatter(fmt)
        logger.addHandler(handler)


# ============================================================
# [1] Đọc và kiểm tra file ID
# ============================================================
def load_ids(path):
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy {path}. Hãy đặt file ID vào thư mục data/")

    raw, invalid = [], []
    # utf-8-sig: tự bỏ ký tự BOM nếu file được lưu từ Excel/Windows
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            value = line.strip().split(",")[0].strip()   # strip() cũng bỏ \r của file Windows
            if value.isdigit():
                raw.append(value)
            elif value:
                invalid.append(value)

    ids = list(dict.fromkeys(raw))                       # bỏ trùng, giữ nguyên thứ tự
    logger.info("[1] File ID: %d dòng hợp lệ | %d trùng | %d không hợp lệ %s",
                len(raw), len(raw) - len(ids), len(invalid), invalid[:3])
    logger.info("[1] => %d ID duy nhất", len(ids))
    return ids


# ============================================================
# Làm sạch dữ liệu
# ============================================================
def clean_description(raw):
    """HTML -> text: bỏ tag, giải mã &nbsp; &amp;..., gộp khoảng trắng."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()   # \s gồm cả \xa0 (&nbsp;) và xuống dòng


def extract(p):
    """Chỉ giữ các trường DoD yêu cầu. Kiểm tra lại tên trường ở bước [2]."""
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    }


# ============================================================
# Gọi API
# ============================================================
_local = threading.local()


def get_session():
    """Mỗi thread một Session riêng: tái sử dụng kết nối và tự retry khi lỗi tạm thời."""
    if not hasattr(_local, "session"):
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        retry = Retry(
            total=3,
            backoff_factor=1,                         # chờ tăng dần giữa các lần thử lại
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,                    # hết lượt retry thì trả về response để ghi mã lỗi
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        _local.session = session
    return _local.session


BLOCKED = threading.Event()   # cờ dùng chung cho mọi thread: "API đang chặn mình"


def fetch_product(pid):
    """Trả về (pid, dữ liệu, None, "") nếu thành công,
    hoặc (pid, None, lý do lỗi, chi tiết) nếu lỗi."""
    if BLOCKED.is_set():
        # Đã bị chặn: KHÔNG gửi thêm request (gửi tiếp chỉ làm thời gian bị chặn kéo dài)
        return pid, None, "blocked", "skipped"
    time.sleep(REQUEST_DELAY)
    try:
        r = get_session().get(API_URL.format(pid), timeout=TIMEOUT)
    except requests.RequestException as e:
        return pid, None, type(e).__name__, str(e)[:100]       # Timeout, ConnectionError, ...
    if r.status_code != 200:
        return pid, None, f"HTTP {r.status_code}", ""
    try:
        return pid, extract(r.json()), None, ""
    except ValueError:
        # HTTP 200 nhưng body không phải JSON = trang chặn bot. Bật cờ để các thread khác dừng gửi.
        BLOCKED.set()
        return pid, None, "blocked", f"{r.headers.get('Content-Type', '?')} | {r.text[:80]!r}"


def api_available(probe_id):
    """Gửi 1 request thử: True nếu API trả về JSON bình thường."""
    try:
        r = get_session().get(API_URL.format(probe_id), timeout=TIMEOUT)
    except requests.RequestException:
        return False
    return r.status_code == 200 and "json" in r.headers.get("Content-Type", "")


def wait_until_unblocked(probe_id):
    """Chờ đến khi hết bị chặn. Trả về False nếu quá BLOCK_MAX_WAIT."""
    waited = 0
    while waited < BLOCK_MAX_WAIT:
        logger.warning("[4] Đang bị chặn, chờ %ds rồi thử lại (đã chờ %d phút)...",
                       BLOCK_CHECK_EVERY, waited // 60)
        time.sleep(BLOCK_CHECK_EVERY)
        waited += BLOCK_CHECK_EVERY
        if api_available(probe_id):
            logger.info("[4] Hết bị chặn sau ~%d phút, chạy tiếp.", waited // 60)
            return True
    return False


# ============================================================
# [2] Gọi thử 1 sản phẩm để xem cấu trúc
# ============================================================
def explore_one(pid):
    """Gọi thử 1 sản phẩm. Trả về False nếu API không dùng được (bị chặn / lỗi)."""
    r = get_session().get(API_URL.format(pid), timeout=TIMEOUT)
    content_type = r.headers.get("Content-Type", "?")
    logger.info("[2] Gọi thử ID %s -> HTTP %s | %s", pid, r.status_code, content_type)
    if r.status_code != 200:
        logger.error("[2] Sản phẩm đầu tiên lỗi HTTP %s, kiểm tra mạng rồi chạy lại", r.status_code)
        return False
    try:
        p = r.json()
    except ValueError:
        logger.error("[2] API trả về %s thay vì JSON -> đang bị chặn (anti-bot). "
                     "Chờ đến khi curl trả về application/json rồi chạy lại.", content_type)
        logger.error("[2] Đầu body: %r", r.text[:120])
        return False
    logger.info("[2] Các trường API trả về: %s", sorted(p.keys()))
    sample = extract(p)
    logger.info("[2] Sau khi extract:\n%s",
                json.dumps({**sample, "description": sample["description"][:200] + "..."},
                           ensure_ascii=False, indent=2))
    return True


# ============================================================
# [3] Đo tốc độ: tuần tự vs ThreadPoolExecutor
# ============================================================
def benchmark(ids, n=100):
    sample = ids[:n]
    start = time.time()
    for pid in sample:
        fetch_product(pid)
    seq = time.time() - start
    logger.info("[3] Tuần tự: %d ID trong %.1fs -> ước tính 200k: %.1f giờ",
                n, seq, seq / n * 200_000 / 3600)

    for workers in (10, 20, 50):
        sample = ids[n:2 * n]                         # dùng cùng nhóm ID để so sánh công bằng
        start = time.time()
        with ThreadPoolExecutor(workers) as ex:
            results = list(ex.map(fetch_product, sample))
        t = time.time() - start
        errors = sum(1 for _, _, err, _ in results if err)
        logger.info("[3] %2d workers: %.1fs | lỗi %d -> ước tính 200k: %.1f giờ",
                    workers, t, errors, t / n * 200_000 / 3600)


# ============================================================
# [4] Lấy dữ liệu theo batch, có checkpoint
# ============================================================
def save_batch(batch_no, products, errors):
    # File lỗi riêng cho mỗi batch -> chạy lại batch không bị ghi trùng
    with open(ERROR_DIR / f"errors_{batch_no:04d}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "reason", "detail"])
        writer.writerows(errors)

    # Ghi ra file tạm rồi mới đổi tên: không bao giờ còn file JSON dở dang
    out = OUTPUT_DIR / f"products_{batch_no:04d}.json"
    tmp = out.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)


def run_batches(ids, probe_id):
    batches = [ids[i:i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
    total_ok = total_err = skipped = blocks = 0

    # loggers=[logger]: chỉ chuyển logger "tiki" qua tqdm, tránh in mỗi dòng 2 lần
    with ThreadPoolExecutor(MAX_WORKERS) as ex, logging_redirect_tqdm(loggers=[logger]):
        for batch_no, batch in enumerate(tqdm(batches, desc="Batches", unit="batch"), start=1):
            if (OUTPUT_DIR / f"products_{batch_no:04d}.json").exists():
                skipped += 1                          # checkpoint: batch đã xong ở lần chạy trước
                continue

            start = time.time()
            while True:
                BLOCKED.clear()
                results = list(ex.map(fetch_product, batch))
                if not BLOCKED.is_set():
                    break                             # batch chạy trọn vẹn, không bị chặn
                # Bị chặn giữa batch: KHÔNG lưu (kết quả không đầy đủ), chờ hết chặn rồi làm lại cả batch
                blocks += 1
                done = sum(1 for _, data, _, _ in results if data)
                logger.warning("[4] batch %04d bị chặn sau ~%d sản phẩm", batch_no, done)
                if not wait_until_unblocked(probe_id):
                    logger.error("[4] Bị chặn quá %d phút. DỪNG. Chạy lại sau: script sẽ "
                                 "tiếp tục từ batch %04d.", BLOCK_MAX_WAIT // 60, batch_no)
                    logger.info("[4] Lần chạy này: ok=%d lỗi=%d | bỏ qua %d batch | bị chặn %d lần",
                                total_ok, total_err, skipped, blocks)
                    return

            products = [data for _, data, err, _ in results if data]
            errors = [(pid, err, detail) for pid, _, err, detail in results if err]
            save_batch(batch_no, products, errors)

            total_ok += len(products)
            total_err += len(errors)
            logger.info("[4] batch %04d: ok=%d lỗi=%d (%.1fs)",
                        batch_no, len(products), len(errors), time.time() - start)

    logger.info("[4] Lần chạy này: ok=%d lỗi=%d | bỏ qua %d batch đã có | bị chặn %d lần",
                total_ok, total_err, skipped, blocks)


# ============================================================
# [5] Kiểm tra kết quả
# ============================================================
def validate(ids):
    product_ids = []
    for path in sorted(OUTPUT_DIR.glob("products_*.json")):
        with open(path, encoding="utf-8") as f:
            product_ids += [str(p["id"]) for p in json.load(f)]

    errors = []
    for path in sorted(ERROR_DIR.glob("errors_*.csv")):
        with open(path, encoding="utf-8") as f:
            errors += list(csv.DictReader(f))

    ok, err = len(product_ids), len(errors)
    dup = ok - len(set(product_ids))
    logger.info("[5] File output: %d | sản phẩm ok: %d | lỗi: %d",
                len(list(OUTPUT_DIR.glob("products_*.json"))), ok, err)
    logger.info("[5] ok + lỗi = %d | số ID cần lấy = %d -> %s",
                ok + err, len(ids), "KHỚP ✅" if ok + err == len(ids) else "KHÔNG KHỚP ❌")
    logger.info("[5] id trùng trong output: %d", dup)
    for reason, count in Counter(e["reason"] for e in errors).most_common():
        logger.info("[5]   %-20s %d", reason, count)


# ============================================================
def main():
    setup_logging()
    logger.info("scraper.py %s | MAX_WORKERS=%d REQUEST_DELAY=%.1fs (~%.1f req/s tối đa) | LIMIT=%s",
                VERSION, MAX_WORKERS, REQUEST_DELAY, MAX_WORKERS / max(REQUEST_DELAY, 0.1), LIMIT)
    OUTPUT_DIR.mkdir(exist_ok=True)
    ERROR_DIR.mkdir(exist_ok=True)

    ids = load_ids(ID_FILE)
    if LIMIT:
        if LIMIT % BATCH_SIZE:
            raise ValueError("LIMIT phải là bội số của BATCH_SIZE, nếu không batch cuối "
                             "sẽ bị thiếu sản phẩm khi chạy toàn bộ (checkpoint sẽ bỏ qua nó)")
        ids = ids[:LIMIT]
        logger.info("Chế độ test: chỉ lấy %d ID đầu", len(ids))

    if not explore_one(ids[0]):
        logger.error("Dừng trước khi lấy dữ liệu, để không ghi hàng loạt lỗi vào errors/.")
        return
    if RUN_BENCHMARK:
        benchmark(ids)

    start = time.time()
    run_batches(ids, probe_id=ids[0])          # ids[0] vừa trả về JSON ở bước [2]
    logger.info("Tổng thời gian: %.1f phút", (time.time() - start) / 60)

    validate(ids)


if __name__ == "__main__":
    main()