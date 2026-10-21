# Project 02 – Tiki Product Scraper

🌐 **English** | [Tiếng Việt](README.vi.md)

Fetch about **200,000 products** from the Tiki product API with Python, keep the fields that matter, clean them, and save them as JSON files of about 1,000 products each, with every failed ID recorded with its reason.

📘 **How it was built, step by step:** [GUIDE.md](GUIDE.md) · [GUIDE.vi.md](GUIDE.vi.md)

## Requirements (DoD)

- [x] Fetch product details for every ID in the input list
- [x] Keep `id`, `name`, `url_key`, `price`, `description`, `images`
- [x] Clean `description` (HTML → plain text)
- [x] Save about 1,000 products per `.json` file
- [x] Record failed IDs with the reason
- [ ] Find a way to shorten the fetch time: _measured, see [Shortening the run time](#shortening-the-run-time)_
- [ ] Full run of all ~200,000 IDs: _in progress_

## Results

| Metric | Value |
|---|---|
| Unique input IDs | 200,000 |
| Products saved | _[fill in from `step8_check_results.py`]_ |
| Failed IDs | _[fill in]_, mostly _[main reason]_ |
| OK + failed = input IDs | _[MATCH / MISMATCH]_ |
| Duplicate ids in output | _[fill in]_ |
| Median time per batch of 1,000 | _[fill in from `step8c_runtime.py`]_ |
| Total wall-clock time | _[fill in]_ |

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

## Shortening the run time

Fetching 200,000 products one by one at about 1.4 s each takes more than 3 days. What was tried, and what it gave:

| Approach | Result |
|---|---|
| `requests.Session()` (reuse the connection) | Used in both versions: no new TCP/TLS handshake for every request |
| Parallel requests with `ThreadPoolExecutor` (`scraper.py`, `benchmark()`) | Tested with 10, 20 and 50 workers: _[fill in: time and errors per setting]_ |
| Finding the safe rate with `probe_rate.py` | _[fill in: the rate at which Tiki started blocking]_ → kept at 1 worker, 1 s delay |
| Never retrying `HTTP 404` | Products that no longer exist cost one request, not several |
| Removing pauses (no sleep, no restart, `tmux`) | Pauses were _[fill in from `step8c_runtime.py`]_ of the wall-clock time |

**Conclusion:** _[fill in, e.g. "the bottleneck is Tiki's rate limit, not the code: above X requests per second the API blocks, so the realistic gain is in removing pauses"]_.

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
│   └── step8c_runtime.py            # runtime: time per batch, pauses, forecast
├── GUIDE.md / GUIDE.vi.md
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

## Lessons learned

- **Estimate the runtime first.** At 1.4 s per ID, 200,000 IDs take more than 3 days. That decided the design: batches, checkpoints and `tmux`.
- **A 200 status can still be a failure.** Anti-bot pages arrive as `200 OK` with HTML. Checking `Content-Type` catches them.
- **Permanent and temporary errors are different.** `HTTP 404` (product gone) is never retried; timeouts, `429` and `5xx` are.
- **`tmux` does not survive a Windows restart.** Restarting to fix Wi-Fi stopped WSL and the scraper with it. The checkpoint limited the loss to one batch.
- **"Finished" is not "complete".** Products + errors must equal the number of input IDs; `step8_check_results.py` checks this.

The full list of problems and fixes is in [GUIDE.md](GUIDE.md).
