# Project 02 – Tiki Product Scraper

🌐 **English** | [Tiếng Việt](README.vi.md)

Fetch about **200,000 products** from the Tiki product API with Python, keep the fields that matter, clean them, and save them as JSON files of about 1,000 products each, with every failed ID recorded with its reason.

📘 **How it was built, step by step:** [GUIDE.md](GUIDE.md) · [GUIDE.vi.md](GUIDE.vi.md)

🛠️ **How to run it, start to finish:** [RUNBOOK.md](RUNBOOK.md) · [RUNBOOK.vi.md](RUNBOOK.vi.md)

## Requirements (DoD)

- [x] Fetch product details for every ID in the input list
- [x] Keep `id`, `name`, `url_key`, `price`, `description`, `images`
- [x] Clean `description` (HTML → plain text)
- [x] Save about 1,000 products per `.json` file
- [x] Record failed IDs with the reason
- [x] Find a way to shorten the fetch time: see [Shortening the run time](#shortening-the-run-time)
- [x] Full run of all ~200,000 IDs: 200/200 batches (first pass); retry pass for temporary errors _in progress_

## Results

| Metric | Value |
|---|---|
| Unique input IDs | 200,000 |
| Products saved (after the retry pass) | _[fill in from `step10_final_report.py`]_ |
| Recovered in the retry pass | _[fill in]_ |
| Final failed IDs | _[fill in]_, mostly `HTTP 404` (products removed from Tiki) |
| Products + failed = input IDs | _[MATCH / MISMATCH]_ |
| Duplicate ids in output | _[fill in]_ |
| Time per healthy batch of 1,000 | about 23 min (≈ 1.4 s per ID) |
| Total wall-clock time (first pass) | about 6 days, see [Run timeline](#run-timeline-1521-oct-2026) |

**From the test run** (3,000 IDs, `scraper.py`): about 31% of each batch failed (689 ok / 311 failed, then 687 / 313), and a normal batch took about 23 minutes (about 1.4 s per ID with a 1 s delay).

## How it works

```
data/ids.csv ──► read & deduplicate IDs ──► batches of 1,000
                                              │
                  for each ID: API call ──► extract 6 fields ──► clean description
                                              │
           output/products_0001.json      errors/errors_0001.csv
           (skipped next run = checkpoint)  (id, reason)
```

- **Rate limit:** one request at a time, 1 s apart. Faster runs were blocked by Tiki's anti-bot protection.
- **Errors never stop the run:** network errors, HTTP errors and non-JSON responses become a row in `errors/` with the reason.
- **Resumable:** each finished batch is a file. After a crash or restart, finished batches are skipped.
- **Atomic writes:** each JSON file is written to `.tmp` and then renamed, so a crash never leaves a half-written file.
- **Block detection:** an HTML response instead of JSON means "blocked". The scraper waits and tries again instead of recording thousands of false errors.

## Run timeline (15–21 Oct 2026)

Measured with `steps/step8c_runtime.py` from the time each output file was saved.

| When | What happened | Comment |
|---|---|---|
| 15 Oct 08:57 → 12:38 | Test run with `scraper.py` (`LIMIT = 3000`). Batch 1: 23 min, batch 2: **3h18m** | Blocked in batch 2; v4 waits, then redoes the whole batch |
| 15 Oct 12:38 → 16 Oct 07:27 | Batches 3 and 4 | Mostly idle time between test sessions, not slow scraping |
| 16 Oct 07:27 → 17 Oct 08:28 | Batches 5–61 at a steady pace | ✅ Healthy: about 23 min per batch (≈ 1.4 s per ID) |
| **17 Oct 08:28 → 18 Oct ~23:45** | Batches 62–73 took **exactly 3h03m each** | ❌ 3h03m ≈ 1,000 × (10 s timeout + 1 s delay): nearly every request timed out |
| 18 Oct ~23:45 | Windows restarted to fix the Wi-Fi | The batch in progress (74) was lost |
| 18 Oct 23:51 → 19 Oct 00:15 | Scraper restarted in `tmux`, batch 74 finished | ✅ The checkpoint skipped batches 1–73 |
| 19 Oct → 21 Oct morning | Batches 75–200 at a steady pace, two interruptions of ~1h40m (before 157 and 187) | ✅ Run complete: 200/200 batches |

**Key finding:** the timeout period lines up with the Wi-Fi problem. The connection was most likely unstable or down for about 1.5 days, and `scraper_simple.py` kept going, spending about 40 hours on requests that could not succeed and turning about 12,000 IDs into `ReadTimeout`/`ConnectTimeout` errors. Those IDs go to the retry pass (`steps/step9_retry_failed.py`).

| Time | Value |
|---|---|
| Wall-clock time of the full run | about 6 days |
| Time counted as pauses by `step8c_runtime.py` | 60h55m (43%), including idle time between the test and the main run |
| Time lost to the dead connection (batches 62–74) | about 40 h |
| Expected time with no incidents (200 × 23 min) | about 77 h (3.2 days) |
| Minimum possible at 1 s per ID | 55.5 h |

## Shortening the run time

| Approach | Result |
|---|---|
| `requests.Session()` (reuse the connection) | Used in both versions: no new TCP/TLS handshake for every request |
| Checking the safe rate with `probe_rate.py` (one request at a time) | **1 s delay (~0.75 req/s real):** 150 requests in 200 s, **no block**, 93 ok / 57 `HTTP 404` |
| | **0.2 s delay (~1.9 req/s real):** **blocked after only 11 requests (6 s)** |
| | Running `probe_rate.py 1 150` straight after: blocked at request 1. The block was still active, so a rest between tests is needed. A `curl` check a few minutes later returned JSON again |
| Parallel requests with `ThreadPoolExecutor`, tested with `steps/probe_workers.py` | **1 worker (0.64 req/s):** 100 requests, no block, 55 ok / 45 `HTTP 404`. **2 workers (1.43 req/s):** **blocked**: 62 of 100 requests got the block page (31 ok / 7 `HTTP 404` before it). Tiki's limit is **below ~1.4 req/s**, so more workers cannot speed this up → `MAX_WORKERS = 1` |
| User-Agent check | `curl` with its default `curl/8.5.0` User-Agent also got JSON: the block is about **request rate**, not about the header |
| Never retrying `HTTP 404` | About 31% of IDs are products that no longer exist; each costs one request, not several |
| **Circuit breaker** (retry pass) | After 20 network errors in a row: stop, wait until the API answers, redo those IDs. Would have saved most of the ~40 h |
| **Shorter timeout** (retry pass) | `TIMEOUT = 5` instead of 10: a dead request costs 6 s instead of 11 s |
| Avoiding pauses | `tmux`, Windows sleep set to *Never*, fixing Wi-Fi without restarting |

**Conclusion:** the code was not the bottleneck. Tiki blocks somewhere between 0.75 and 1.4 requests per second, so the rate limit sets the minimum (about 55–75 h), and the biggest avoidable loss (about 40 h) came from running blind on a dead connection. The most effective way to shorten the run is to **detect failure early**, not to send requests faster.

## Mistakes and improvements

| # | Mistake | Effect | Improvement |
|---|---|---|---|
| 1 | `scraper_simple.py` did not notice many timeouts in a row | ~40 h wasted, ~12,000 IDs to retry | Circuit breaker + shorter timeout (`step9_retry_failed.py`) |
| 2 | No monitoring during the run | The problem went unnoticed for 1.5 days | Print errors by reason per batch, warn when a batch is all timeouts, check `tail logs/run.log` twice a day |
| 3 | `scraper_simple.py` run without `tee` | No log to analyse afterwards | Always `\| tee -a logs/run.log`, or use `logging` as in `scraper.py` |
| 4 | Restarting Windows to fix the Wi-Fi | Killed WSL, `tmux` and the scraper; one batch lost | Toggle Airplane mode or the Wi-Fi adapter instead of restarting |
| 5 | `scraper.py` redoes the whole batch after a block | Batch 2 took 3h18m | A deliberate trade-off: every saved batch is complete |
| 6 | Project on the Windows drive (`/mnt/c`) | Slower file writes; false "modified" errors from `git subtree` | Keep long-running projects in the WSL file system (`~/projects/`) |

Not a mistake: the ~31% `HTTP 404` rate comes from the data. Those products were removed from Tiki after the ID list was created, and they are correctly never retried.

## Project structure

```
project_02/
├── scraper_simple.py   # simple version (~150 lines): the one to read first
├── scraper.py          # hardened version: retries, logging, progress bar, block time limit, validation
├── probe_rate.py       # measures how fast the API can be called before it blocks
├── steps/              # the guide's code, one small runnable script per level
│   ├── step1_one_product.py ... step5_batch_checkpoint.py
│   ├── step8_check_results.py       # completeness: nothing missing or duplicated
│   ├── step8b_profile_products.py   # data quality: empty fields, prices, descriptions
│   ├── step8c_runtime.py            # runtime: time per batch, pauses, forecast
│   ├── probe_workers.py             # how many parallel workers Tiki tolerates
│   ├── step9_retry_failed.py        # second pass for temporary errors, with a circuit breaker
│   └── step10_final_report.py       # combines both passes -> final_errors.csv
├── GUIDE.md / GUIDE.vi.md
├── RUNBOOK.md / RUNBOOK.vi.md   # every command, in order
└── requirements.txt
```

Not in Git (see `.gitignore`): `data/` (input IDs), `output/`, `errors/`, `logs/`, `.venv/`.

## How to run

```bash
cd project_02
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# put the ID list provided by the course at data/ids.csv (one ID per line, header "id")

# quick test first: set LIMIT = 3000 in scraper_simple.py (must be a multiple of 1000)
python scraper_simple.py
```

The full run takes several days, so start it inside `tmux` and keep a log file:

```bash
tmux new -s tiki
source .venv/bin/activate
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
# Ctrl-b then d to detach; tmux attach -t tiki to come back
```

Check the result after (or during) the run:

```bash
python steps/step8_check_results.py
python steps/step8b_profile_products.py
python steps/step8c_runtime.py
```

Retry the temporary errors, then build the final report:

```bash
python steps/step8_check_results.py                 # writes retry_ids.csv (all errors except HTTP 404)
python -u steps/step9_retry_failed.py 2>&1 | tee -a logs/retry.log
python steps/step10_final_report.py                 # writes final_errors.csv (id, final reason)
```

## Lessons learned

- **Estimate the runtime first.** At 1.4 s per ID, 200,000 IDs take more than 3 days. That decided the design: batches, checkpoints and `tmux`.
- **A 200 status can still be a failure.** Anti-bot pages arrive as `200 OK` with HTML. Checking `Content-Type` catches them.
- **Permanent and temporary errors are different.** `HTTP 404` (product gone) is never retried; timeouts, `429` and `5xx` are.
- **`tmux` does not survive a Windows restart.** Restarting to fix Wi-Fi stopped WSL and the scraper with it. The checkpoint limited the loss to one batch.
- **Handling each error is not enough; watch the error rate.** Every timeout was recorded correctly, yet 1.5 days of them went unnoticed. In real pipelines this is the job of **monitoring and alerting**.
- **"Finished" is not "complete".** Products + errors must equal the number of input IDs; `step8_check_results.py` and `step10_final_report.py` check this.

The full list of problems and fixes is in [GUIDE.md](GUIDE.md).
