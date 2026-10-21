# Project 02 – Runbook: the full process, start to finish

🌐 **English** | [Tiếng Việt](RUNBOOK.vi.md)

Every command needed to run this project from an empty folder to a published result, in order. The *why* behind each step is in [GUIDE.md](GUIDE.md); the results are in [README.md](README.md).

All commands run in WSL from the project folder:
```bash
cd /mnt/c/Users/Admin/Desktop/Project_02
source .venv/bin/activate
```

## Golden rules

1. **Only one job talks to Tiki at a time.** The scraper, the retry and the probes share one IP address, so Tiki adds their traffic together.
2. **Never restart Windows or let it sleep during a run.** That stops WSL, `tmux` and the scraper. Set *Settings → System → Power* → sleep **Never**. Fix Wi-Fi by toggling Airplane mode, not by restarting.
3. **Always keep a log on disk:** `python -u <script> 2>&1 | tee -a logs/<name>.log`.
4. **Never change `BATCH_SIZE` between runs**, and keep `LIMIT` a multiple of `BATCH_SIZE`. The checkpoint depends on batch numbers.
5. **After a block, rest before the next request-heavy step.** Check with the `curl` command in step 2 until it returns JSON, then wait 5 more minutes.

---

## 1. Setup (once)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data output errors logs
```
Put the ID list from the course at `data/ids.csv` (one ID per line, header `id`). Check it:
```bash
head -3 data/ids.csv
wc -l data/ids.csv          # about 200,001 lines (IDs + header)
```
`.gitignore` must contain: `.venv/`, `data/`, `output/`, `errors/`, `logs/`, `output_retry/`, `errors_retry/`, `final_errors.csv`, `retry_ids.csv`, `*.tmp`.

## 2. Look at the API

```bash
curl -s -o /dev/null --max-time 10 -w "%{http_code} %{content_type}\n" -A "Mozilla/5.0" \
  https://api.tiki.vn/product-detail/api/v1/products/1391347
```
| Output | Meaning |
|---|---|
| `200 application/json; charset=utf-8` | ✅ API works, not blocked |
| `200 text/html` / `429` / `403` | ❌ blocked: wait (see the loop below) |
| `000` | no connection: your network |

Wait automatically until a block ends (checks every 2 minutes):
```bash
while true; do
  r=$(curl -s -o /dev/null --max-time 10 -w "%{http_code} %{content_type}" -A "Mozilla/5.0" \
      https://api.tiki.vn/product-detail/api/v1/products/1391347)
  echo "$(date +%H:%M:%S)  $r"
  case "$r" in *json*) echo "✅ Not blocked any more"; break ;; esac
  sleep 120
done
```
Then try one product in Python:
```bash
python steps/step1_one_product.py
python steps/step2_clean_description.py
```

## 3. Find the safe speed

One request at a time, at a given delay (`python probe_rate.py <delay> <requests>`):
```bash
python probe_rate.py 1 150      # measured: ~0.7 req/s, no block
# rest + curl check before the next one
python probe_rate.py 0.2 150    # measured: ~1.9 req/s, blocked after 11 requests
```
Parallel workers, the way `scraper.py` sends requests:
```bash
python -u steps/probe_workers.py 2>&1 | tee -a logs/probe_workers.log
# measured: 1 worker 0.64 req/s ok; 2 workers 1.43 req/s blocked
```
**Result:** Tiki blocks somewhere between 0.75 and 1.4 req/s → **1 worker, 1 s delay**.

## 4. Test run

In `scraper_simple.py` set `LIMIT = 3000` (a multiple of 1000), then:
```bash
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
python steps/step8_check_results.py
```
Check: 3 files in `output/`, about 23 minutes per batch, errors mostly `HTTP 404`.
Then set `LIMIT = None` for the full run. Batches 1–3 are kept and skipped.

## 5. Full run (several days)

```bash
tmux new -s tiki
source .venv/bin/activate
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
# Ctrl-b then d  -> detach; the scraper keeps running
```
| Command | Purpose |
|---|---|
| `tmux ls` | list sessions |
| `tmux attach -t tiki` | watch the progress (leave with `Ctrl-b` then `d`, **never** `Ctrl-c`) |
| `pgrep -af scraper` | is the process alive? |
| `kill <PID>` | stop politely; the checkpoint lets it resume later |

## 6. Monitor (at least twice a day)

```bash
tail -5 logs/run.log                                     # last batches
ls -lt output/ | head -3                                 # newest batch and when it was saved
cut -d, -f2 "$(ls -t errors/*.csv | head -1)" | sort | uniq -c | sort -rn   # errors of the newest batch
```
| Red flag | Likely cause | Action |
|---|---|---|
| A batch takes about **3 hours** instead of ~23 min | every request times out (11 s each): Wi-Fi or network down | Check Wi-Fi (`curl` command in step 2). Fix without restarting |
| Newest batch: nearly all `ReadTimeout` / `ConnectTimeout` | same | same; those IDs go to the retry in step 8 |
| `Bị chặn` messages keep repeating | Tiki is blocking | leave it: the scraper waits and retries the same ID |
| No new file for more than 1 hour, process alive | stuck, or Windows slept | `tmux attach -t tiki` and look |
| `pgrep` shows nothing | the scraper stopped | start step 5 again: finished batches are skipped |

## 7. Check the result

```bash
python steps/step8_check_results.py      # completeness: ok + errors = IDs? errors by reason; writes retry_ids.csv
python steps/step8b_profile_products.py  # quality: empty fields, prices, descriptions, unusual batches
python steps/step8c_runtime.py           # runtime: time per batch, pauses, time lost
```

## 8. Retry the temporary errors

`retry_ids.csv` holds every failed ID except `HTTP 404` (products that no longer exist are never retried).
```bash
wc -l retry_ids.csv
tmux new -s retry
source .venv/bin/activate
python -u steps/step9_retry_failed.py 2>&1 | tee -a logs/retry.log
# Ctrl-b then d
```
It writes to `output_retry/` and `errors_retry/` (the first pass is not touched), uses a 5 s timeout, and has a **circuit breaker**: after 20 network errors in a row it stops, waits until Tiki answers, and redoes those IDs. If it stops with `Stopped: no answer for 60 min`, run the same command again later; finished retry batches are skipped.
```bash
tail -3 logs/retry.log      # "Done / Xong!" = finished
```

## 9. Final report

```bash
python steps/step10_final_report.py
```
It combines both passes, checks **products + errors = input IDs**, and writes `final_errors.csv` (id, final reason). That file is the DoD's list of failed products with the reason. Copy its numbers into the **Results** table of the README.

## 10. Commit and publish

In `Project_02`:
```bash
git status                 # nothing from data/, output*/, errors*/, logs/
git add .gitignore README.md README.vi.md RUNBOOK.md RUNBOOK.vi.md GUIDE.md GUIDE.vi.md steps/ *.py requirements.txt
git commit -m "<what changed>"
```
In the journey repo:
```bash
cd /mnt/c/Users/Admin/Desktop/data-engineering-journey
git update-index --refresh
git subtree pull --prefix=project_02 /mnt/c/Users/Admin/Desktop/Project_02 main -m "Update project_02 from Project_02"
git push
```
Check `https://github.com/dottienguyen23/data-engineering-journey/tree/main/project_02`.

## 11. Submit

- [ ] README results table filled in from step 9
- [ ] `final_errors.csv` exists (committed, or its summary in the README)
- [ ] Repo pushed and checked on GitHub
- [ ] Repo link submitted through the course's Google Form
- [ ] Daily Task Report written ("taki taki")
