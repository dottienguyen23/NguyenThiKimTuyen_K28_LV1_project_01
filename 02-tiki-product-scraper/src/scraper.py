"""
Tiki product scraper.

Downloads product details from the Tiki API for a list of product IDs and saves them
as JSON files of 1,000 products each, with the HTML description cleaned to plain text.
Every ID ends up in exactly one place: a product file (output/) or an error file (errors/).

Usage (run from the project root):
    python -u src/scraper.py                      # full run with defaults
    python -u src/scraper.py --limit 3000         # quick test on the first 3,000 IDs
    python -u src/scraper.py --help               # all options

Safe to stop and restart at any time: finished batches are skipped on the next run.

Exit codes:
    0    finished, and products + errors reconcile with the input IDs
    1    stopped early (pre-flight failed, or API blocked / network down for too long)
    2    finished, but the reconciliation check failed
    130  interrupted with Ctrl+C
"""

import argparse
import csv
import html
import json
import logging
import math
import os
import re
import sys
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

VERSION = "v5"

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # src/scraper.py -> project root
API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
USER_AGENT = "Mozilla/5.0"

# Checkpointing is based on batch numbers, so this must never change between runs.
BATCH_SIZE = 1000

logger = logging.getLogger("tiki")


# ============================================================
# Configuration
# ============================================================
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Download Tiki product details into batched JSON files.")
    p.add_argument("--ids", type=Path, default=PROJECT_ROOT / "data" / "ids.csv",
                   help="CSV file with one product ID per line (default: data/ids.csv)")
    p.add_argument("--root", type=Path, default=PROJECT_ROOT,
                   help="folder where output/, errors/ and logs/ are created (default: project root)")
    p.add_argument("--limit", type=int, default=None,
                   help=f"only process the first N IDs, for testing (must be a multiple of {BATCH_SIZE})")
    p.add_argument("--workers", type=int, default=1,
                   help="parallel requests (default: 1; Tiki blocked 2 workers at ~1.4 req/s)")
    p.add_argument("--interval", type=float, default=1.0,
                   help="seconds between request starts, across all workers (default: 1.0 = 1 req/s)")
    p.add_argument("--timeout", type=float, default=10,
                   help="seconds to wait for one response (default: 10)")
    p.add_argument("--max-network-errors", type=int, default=20,
                   help="consecutive network errors that mean 'connection is down' (default: 20)")
    p.add_argument("--check-every", type=int, default=120,
                   help="while blocked or offline: seconds between availability checks (default: 120)")
    p.add_argument("--max-wait", type=int, default=3600,
                   help="while blocked or offline: seconds to wait before giving up (default: 3600)")
    p.add_argument("--verbose", action="store_true", help="also log debug details")
    args = p.parse_args(argv)

    if args.limit is not None and (args.limit <= 0 or args.limit % BATCH_SIZE):
        p.error(f"--limit must be a positive multiple of {BATCH_SIZE}, otherwise the last test "
                "batch would be saved incomplete and skipped by the checkpoint on a full run")
    if args.workers < 1 or args.interval <= 0:
        p.error("--workers must be >= 1 and --interval must be > 0")
    return args


def setup_logging(log_dir, verbose):
    log_dir.mkdir(parents=True, exist_ok=True)
    # Full date in every line: a full run lasts several days.
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    for handler in (logging.FileHandler(log_dir / "run.log", encoding="utf-8"),
                    logging.StreamHandler()):
        handler.setFormatter(fmt)
        logger.addHandler(handler)


# ============================================================
# Input
# ============================================================
def load_ids(path):
    if not path.exists():
        raise FileNotFoundError(f"ID file not found: {path}")

    raw, invalid = [], []
    with open(path, encoding="utf-8-sig") as f:              # utf-8-sig drops an Excel BOM
        for line in f:
            value = line.strip().split(",")[0].strip()        # strip() also removes Windows \r
            if value.isdigit():
                raw.append(value)
            elif value:
                invalid.append(value)                         # e.g. a header row

    ids = list(dict.fromkeys(raw))                            # de-duplicate, keep order
    logger.info("IDs: %d valid lines | %d duplicates | %d invalid %s -> %d unique",
                len(raw), len(raw) - len(ids), len(invalid), invalid[:3], len(ids))
    return ids


# ============================================================
# Transform
# ============================================================
def clean_description(raw):
    """HTML -> plain text: drop tags, decode entities, collapse whitespace."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "html.parser").get_text(separator=" ")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()                  # \s also matches \xa0 (&nbsp;)


def extract(p):
    """Keep only the fields required by the project."""
    return {
        "id": p.get("id"),
        "name": p.get("name"),
        "url_key": p.get("url_key"),
        "price": p.get("price"),
        "description": clean_description(p.get("description")),
        "images": [img.get("base_url") for img in (p.get("images") or [])],
    }


# ============================================================
# Extract
# ============================================================
class RateLimiter:
    """Starts at most one request every `interval` seconds, shared by all threads.

    Pacing by start time (not 'sleep after each answer') keeps the rate exact
    without wasting the server's response time.
    """

    def __init__(self, interval):
        self.interval = interval
        self._lock = threading.Lock()
        self._next = time.monotonic()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self.interval
        time.sleep(start - now)


class Scraper:
    def __init__(self, args):
        self.args = args
        self.limiter = RateLimiter(args.interval)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._network_errors = 0
        # Shared stop flag: set when the API blocks us or the network is down,
        # so all threads stop sending requests for the rest of the batch.
        self.halt = threading.Event()
        self.halt_reason = ""

    # ---- HTTP ------------------------------------------------
    def _session(self):
        """One Session per thread: reuses connections and retries temporary errors."""
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
            retry = Retry(total=3, backoff_factor=1,
                          status_forcelist=[429, 500, 502, 503, 504],
                          raise_on_status=False)              # after retries, return the response
            session.mount("https://", HTTPAdapter(max_retries=retry))
            self._local.session = session
        return self._local.session

    def _stop(self, reason):
        with self._lock:
            if not self.halt.is_set():
                self.halt_reason = reason
                self.halt.set()

    def reset(self):
        with self._lock:
            self.halt.clear()
            self.halt_reason = ""
            self._network_errors = 0

    def fetch(self, pid):
        """Return (pid, product, None, "") on success or (pid, None, reason, detail) on error."""
        if self.halt.is_set():
            return pid, None, "skipped", self.halt_reason     # never saved: the batch is redone
        self.limiter.wait()
        try:
            r = self._session().get(API_URL.format(pid), timeout=self.args.timeout)
        except requests.RequestException as e:
            with self._lock:
                self._network_errors += 1
                down = self._network_errors >= self.args.max_network_errors
            if down:
                self._stop("network down")                   # circuit breaker
            return pid, None, type(e).__name__, str(e)[:100]

        with self._lock:
            self._network_errors = 0
        if r.status_code != 200:
            return pid, None, f"HTTP {r.status_code}", ""
        try:
            return pid, extract(r.json()), None, ""
        except ValueError:
            # HTTP 200 with a non-JSON body is Tiki's anti-bot page.
            self._stop("blocked")
            return pid, None, "blocked", f"{r.headers.get('Content-Type', '?')} | {r.text[:80]!r}"

    def api_available(self, probe_id):
        try:
            r = self._session().get(API_URL.format(probe_id), timeout=self.args.timeout)
        except requests.RequestException:
            return False
        return r.status_code == 200 and "json" in r.headers.get("Content-Type", "")

    def wait_until_available(self, probe_id):
        waited = 0
        while waited < self.args.max_wait:
            logger.warning("Waiting %ds before checking the API again (waited %d min so far)",
                           self.args.check_every, waited // 60)
            time.sleep(self.args.check_every)
            waited += self.args.check_every
            if self.api_available(probe_id):
                logger.info("API available again after ~%d min, resuming", waited // 60)
                return True
        return False

    # ---- Pipeline steps --------------------------------------
    def preflight(self, pid):
        """Fetch one product before the real run, so a blocked API or a dead
        connection does not flood errors/ with thousands of failures."""
        try:
            r = self._session().get(API_URL.format(pid), timeout=self.args.timeout)
        except requests.RequestException as e:
            logger.error("Pre-flight: no connection (%s). Check the network and run again.",
                         type(e).__name__)
            return False
        content_type = r.headers.get("Content-Type", "?")
        if r.status_code != 200:
            logger.error("Pre-flight: ID %s returned HTTP %s", pid, r.status_code)
            return False
        try:
            product = r.json()
        except ValueError:
            logger.error("Pre-flight: API returned %s instead of JSON, we are blocked. "
                         "Wait until it returns JSON again, then rerun.", content_type)
            return False
        logger.info("Pre-flight OK: ID %s returned JSON", pid)
        logger.debug("API fields: %s", sorted(product.keys()))
        return True

    def run_batches(self, ids, out_dir, err_dir):
        """Return True if every batch was saved, False if the run stopped early."""
        batches = [ids[i:i + BATCH_SIZE] for i in range(0, len(ids), BATCH_SIZE)]
        probe_id = ids[0]                                     # passed the pre-flight check
        total_ok = total_err = skipped = halts = 0

        with ThreadPoolExecutor(self.args.workers) as ex, logging_redirect_tqdm(loggers=[logger]):
            for batch_no, batch in enumerate(tqdm(batches, desc="Batches", unit="batch"), start=1):
                if batch_path(out_dir, batch_no).exists():
                    skipped += 1                              # checkpoint: done in an earlier run
                    continue

                start = time.time()
                while True:
                    self.reset()
                    try:
                        results = list(ex.map(self.fetch, batch))
                    except KeyboardInterrupt:
                        self._stop("interrupted")             # queued tasks return at once
                        raise
                    if not self.halt.is_set():
                        break
                    # Halted mid-batch: the results are incomplete, so nothing is saved.
                    # Wait for the API, then redo the whole batch.
                    halts += 1
                    done = sum(1 for _, data, _, _ in results if data)
                    logger.warning("Batch %04d halted (%s) after %d products",
                                   batch_no, self.halt_reason, done)
                    if not self.wait_until_available(probe_id):
                        logger.error("API unavailable for over %d min. Stopping. "
                                     "Run again later to resume from batch %04d.",
                                     self.args.max_wait // 60, batch_no)
                        logger.info("This run: ok=%d errors=%d | skipped %d batches | halted %d times",
                                    total_ok, total_err, skipped, halts)
                        return False

                products = [data for _, data, err, _ in results if data]
                errors = [(pid, err, detail) for pid, _, err, detail in results if err]
                save_batch(out_dir, err_dir, batch_no, products, errors)
                total_ok += len(products)
                total_err += len(errors)
                logger.info("Batch %04d: ok=%d errors=%d (%.0fs)",
                            batch_no, len(products), len(errors), time.time() - start)

        logger.info("This run: ok=%d errors=%d | skipped %d finished batches | halted %d times",
                    total_ok, total_err, skipped, halts)
        return True


# ============================================================
# Load
# ============================================================
def batch_path(out_dir, batch_no):
    return out_dir / f"products_{batch_no:04d}.json"


def save_batch(out_dir, err_dir, batch_no, products, errors):
    # One error file per batch, so redoing a batch never duplicates error rows.
    with open(err_dir / f"errors_{batch_no:04d}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "reason", "detail"])
        writer.writerows(errors)

    # Write to a temp file, then rename: a half-written JSON file can never exist.
    # The product file is written last because its existence marks the batch as done.
    out = batch_path(out_dir, batch_no)
    tmp = out.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out)


# ============================================================
# Validate
# ============================================================
def validate(ids, out_dir, err_dir):
    """Reconcile the batches of this ID list: products + errors must equal the IDs."""
    n_batches = math.ceil(len(ids) / BATCH_SIZE)
    product_ids, errors, missing = [], [], []
    for batch_no in range(1, n_batches + 1):
        p_path = batch_path(out_dir, batch_no)
        e_path = err_dir / f"errors_{batch_no:04d}.csv"
        if not (p_path.exists() and e_path.exists()):
            missing.append(batch_no)
            continue
        with open(p_path, encoding="utf-8") as f:
            product_ids += [str(p["id"]) for p in json.load(f)]
        with open(e_path, encoding="utf-8") as f:
            errors += list(csv.DictReader(f))

    ok, err = len(product_ids), len(errors)
    dup = ok - len(set(product_ids))
    reconciled = not missing and dup == 0 and ok + err == len(ids)

    logger.info("Validation: %d/%d batches | products=%d errors=%d | duplicates=%d",
                n_batches - len(missing), n_batches, ok, err, dup)
    logger.info("Validation: products + errors = %d | input IDs = %d -> %s",
                ok + err, len(ids), "OK" if reconciled else "MISMATCH")
    if missing:
        logger.warning("Missing batches: %s", missing[:10])
    for reason, count in Counter(e["reason"] for e in errors).most_common():
        logger.info("  %-20s %d", reason, count)
    return reconciled


# ============================================================
def main(argv=None):
    args = parse_args(argv)
    out_dir, err_dir = args.root / "output", args.root / "errors"
    setup_logging(args.root / "logs", args.verbose)
    out_dir.mkdir(parents=True, exist_ok=True)
    err_dir.mkdir(parents=True, exist_ok=True)

    logger.info("scraper.py %s | workers=%d interval=%.2fs (max %.2f req/s) | limit=%s",
                VERSION, args.workers, args.interval, 1 / args.interval, args.limit)

    ids = load_ids(args.ids)
    if not ids:
        logger.error("No valid IDs in %s", args.ids)
        return 1
    if args.limit:
        ids = ids[:args.limit]
        logger.info("Test mode: first %d IDs only", len(ids))

    scraper = Scraper(args)
    if not scraper.preflight(ids[0]):
        return 1

    start = time.time()
    try:
        finished = scraper.run_batches(ids, out_dir, err_dir)
    except KeyboardInterrupt:
        logger.warning("Interrupted. Finished batches are saved; run again to resume.")
        return 130
    logger.info("Run time: %.1f min", (time.time() - start) / 60)

    if not finished:
        return 1
    return 0 if validate(ids, out_dir, err_dir) else 2


if __name__ == "__main__":
    sys.exit(main())
