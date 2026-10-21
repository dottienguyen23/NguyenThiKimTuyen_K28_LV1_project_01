# Project 02 – Runbook: toàn bộ quy trình, từ đầu đến cuối

🌐 [English](RUNBOOK.md) | **Tiếng Việt**

Mọi lệnh cần để chạy project này, từ thư mục trống đến kết quả đã công bố, theo đúng thứ tự. Lý do của từng bước nằm trong [GUIDE.vi.md](GUIDE.vi.md); kết quả nằm trong [README.vi.md](README.vi.md).

Mọi lệnh chạy trong WSL, từ thư mục project:
```bash
cd /mnt/c/Users/Admin/Desktop/Project_02
source .venv/bin/activate
```

## Nguyên tắc vàng

1. **Mỗi lúc chỉ một job gửi request đến Tiki.** Scraper, lượt chạy lại và các bài đo dùng chung một địa chỉ IP, nên Tiki cộng dồn lưu lượng của chúng.
2. **Không restart Windows và không để máy sleep khi đang chạy.** Làm vậy sẽ tắt WSL, `tmux` và scraper. Vào *Settings → System → Power* → đặt sleep thành **Never**. Sửa wifi bằng bật/tắt Airplane mode, không restart.
3. **Luôn lưu log ra ổ đĩa:** `python -u <script> 2>&1 | tee -a logs/<tên>.log`.
4. **Không đổi `BATCH_SIZE` giữa các lần chạy**, và giữ `LIMIT` là bội số của `BATCH_SIZE`. Checkpoint dựa vào số thứ tự batch.
5. **Sau khi bị chặn, nghỉ trước bước gửi nhiều request tiếp theo.** Kiểm tra bằng lệnh `curl` ở bước 2 đến khi nhận JSON, rồi chờ thêm 5 phút.

---

## 1. Cài đặt (một lần)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data output errors logs
```
Đặt danh sách ID của khóa học ở `data/ids.csv` (mỗi dòng một ID, dòng tiêu đề `id`). Kiểm tra:
```bash
head -3 data/ids.csv
wc -l data/ids.csv          # khoảng 200.001 dòng (ID + dòng tiêu đề)
```
`.gitignore` phải có: `.venv/`, `data/`, `output/`, `errors/`, `logs/`, `output_retry/`, `errors_retry/`, `final_errors.csv`, `retry_ids.csv`, `*.tmp`.

## 2. Xem API

```bash
curl -s -o /dev/null --max-time 10 -w "%{http_code} %{content_type}\n" -A "Mozilla/5.0" \
  https://api.tiki.vn/product-detail/api/v1/products/1391347
```
| Kết quả | Ý nghĩa |
|---|---|
| `200 application/json; charset=utf-8` | ✅ API hoạt động, không bị chặn |
| `200 text/html` / `429` / `403` | ❌ bị chặn: chờ (xem vòng lặp bên dưới) |
| `000` | không có kết nối: lỗi mạng của bạn |

Tự động chờ đến khi hết bị chặn (2 phút kiểm tra một lần):
```bash
while true; do
  r=$(curl -s -o /dev/null --max-time 10 -w "%{http_code} %{content_type}" -A "Mozilla/5.0" \
      https://api.tiki.vn/product-detail/api/v1/products/1391347)
  echo "$(date +%H:%M:%S)  $r"
  case "$r" in *json*) echo "✅ Not blocked any more"; break ;; esac
  sleep 120
done
```
Sau đó thử một sản phẩm bằng Python:
```bash
python steps/step1_one_product.py
python steps/step2_clean_description.py
```

## 3. Tìm tốc độ an toàn

Mỗi lần một request: `python probe_rate.py <khoảng cách> <số request> [vị trí ID bắt đầu]`.
`<khoảng cách>` là thời gian giữa hai lần **bắt đầu** request, nên `1.0` nghĩa là đúng 1 request mỗi giây, dù Tiki trả lời nhanh hay chậm. Trước khi đo, script kiểm tra API đang trả JSON (không còn lệnh chặn cũ); nó dừng ngay ở trang chặn đầu tiên, `403`, `429` hoặc 5 lỗi mạng liên tiếp.
```bash
python probe_rate.py 1.0 300 20000     # đã đo: 1,00 req/s, không bị chặn (Tiki trả lời ~0,42 giây)
# nghỉ ít nhất 5 phút trước lần tiếp theo
python probe_rate.py 0.85 300 30000    # đã đo: 1,17 req/s, không bị chặn
```
Mỗi lần dùng vị trí ID khác nhau, để mỗi lần đo hỏi những sản phẩm khác nhau.

Đo bằng phiên bản đầu của `probe_rate.py` (nghỉ **sau** mỗi phản hồi): ~0,7 req/s an toàn; ~1,9 req/s bị chặn sau 11 request.
Nhiều worker song song, giống cách `scraper.py` gửi request:
```bash
python -u steps/probe_workers.py 2>&1 | tee -a logs/probe_workers.log
# đã đo: 1 worker 0,64 req/s ok; 2 worker 1,43 req/s bị chặn
```
**Kết quả:** Tiki chấp nhận ít nhất **1,17 req/s** và chặn ở **1,43 req/s** → **1 worker, cứ 0,85 giây bắt đầu một request** (~1,18 req/s, thấp hơn mức bị chặn khoảng 18%). Khi đó 200.000 ID mất khoảng **47 giờ (~2 ngày)**.

| Cách nghỉ | Tốc độ | 200k ID | Kết quả |
|---|---|---|---|
| Nghỉ 1 giây sau mỗi phản hồi (lần chạy đầu) | ~0,7 req/s | ~74 giờ | ✅ |
| Cứ 1,0 giây một request | 1,00 req/s | ~56 giờ | ✅ |
| **Cứ 0,85 giây một request** | **1,17 req/s** | **~47 giờ** | ✅ **dùng mức này** |
| 2 worker | 1,43 req/s | — | ❌ bị chặn sau ~38 request |
| Cứ ~0,2 giây một request | ~1,9 req/s | — | ❌ bị chặn sau 11 request |

## 4. Chạy thử

Trong `scraper_simple.py` đặt `LIMIT = 3000` (bội số của 1000), rồi:
```bash
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
python steps/step8_check_results.py
```
Kiểm tra: có 3 file trong `output/`, khoảng 23 phút mỗi batch, lỗi chủ yếu là `HTTP 404`.
Sau đó đặt `LIMIT = None` để chạy toàn bộ. Batch 1–3 được giữ lại và bỏ qua.

## 5. Chạy toàn bộ (vài ngày)

```bash
tmux new -s tiki
source .venv/bin/activate
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
# Ctrl-b rồi d  -> thoát ra; scraper vẫn chạy
```
`python -u NguyenThiKimTuyen_LV1_project_02.py` làm y hệt: đây là file nộp bài và nó chạy `scraper_simple.py`.

Lần chạy đầu nghỉ 1 giây sau mỗi phản hồi (~0,7 req/s, ~23 phút mỗi batch). Muốn dùng tốc độ nhanh hơn đã đo, sửa phần nghỉ trong `scraper_simple.py` giống `steps/step9_retry_failed.py` (`INTERVAL = 0.85`: chỉ nghỉ phần còn thiếu của khoảng cách). Khi đó mỗi batch mất khoảng 14 phút.
| Lệnh | Mục đích |
|---|---|
| `tmux ls` | liệt kê các session |
| `tmux attach -t tiki` | xem tiến độ (thoát bằng `Ctrl-b` rồi `d`, **không bao giờ** dùng `Ctrl-c`) |
| `pgrep -af scraper` | process còn sống không? |
| `kill <PID>` | dừng lịch sự; checkpoint cho phép chạy tiếp sau |

## 6. Theo dõi (ít nhất hai lần mỗi ngày)

```bash
tail -5 logs/run.log                                     # các batch gần nhất
ls -lt output/ | head -3                                 # batch mới nhất và thời điểm lưu
cut -d, -f2 "$(ls -t errors/*.csv | head -1)" | sort | uniq -c | sort -rn   # lỗi của batch mới nhất
```
| Dấu hiệu bất thường | Nguyên nhân có thể | Cách xử lý |
|---|---|---|
| Một batch mất khoảng **3 giờ** thay vì ~23 phút | mọi request đều timeout (11 giây mỗi request): mất wifi hoặc mạng | Kiểm tra wifi (lệnh `curl` ở bước 2). Sửa mà không restart |
| Batch mới nhất gần như toàn `ConnectionError` / `ReadTimeout` / `ConnectTimeout` | như trên | như trên; các ID này được chạy lại ở bước 8 |
| Thông báo `Bị chặn` lặp lại liên tục | Tiki đang chặn | để yên: scraper tự chờ và thử lại đúng ID đó |
| Hơn 1 giờ không có file mới, process vẫn sống | bị treo, hoặc Windows đã sleep | `tmux attach -t tiki` để xem |
| `pgrep` không hiện gì | scraper đã dừng | chạy lại bước 5: các batch đã xong được bỏ qua |

## 7. Kiểm tra kết quả

```bash
python steps/step8_check_results.py      # độ đầy đủ: ok + lỗi = số ID? lỗi theo loại; tạo retry_ids.csv
python steps/step8b_profile_products.py  # chất lượng: trường rỗng, giá, description, batch bất thường
python steps/step8c_runtime.py           # thời gian: mỗi batch, các lần gián đoạn, thời gian bị mất
```

## 8. Chạy lại các lỗi tạm thời

`retry_ids.csv` chứa mọi ID lỗi trừ `HTTP 404` (sản phẩm không còn thì không bao giờ chạy lại).
```bash
wc -l retry_ids.csv
tmux new -s retry
source .venv/bin/activate
python -u steps/step9_retry_failed.py 2>&1 | tee -a logs/retry.log
# Ctrl-b rồi d
```
Script ghi vào `output_retry/` và `errors_retry/` (không đụng vào lượt một), cứ **0,85 giây** bắt đầu một request (khoảng 2,8 giờ cho ~12.000 ID), dùng timeout 5 giây, và có **circuit breaker**: sau 20 lỗi mạng liên tiếp thì dừng, chờ đến khi Tiki trả lời, rồi chạy lại các ID đó. Nếu nó dừng với `Stopped: no answer for 60 min`, chạy lại đúng lệnh đó sau; các batch đã xong được bỏ qua.
```bash
tail -3 logs/retry.log      # "Done / Xong!" = đã xong
```

## 9. Báo cáo cuối

```bash
python steps/step10_final_report.py
```
Script gộp hai lượt, kiểm tra **sản phẩm + lỗi = số ID đầu vào**, và tạo `final_errors.csv` (id, lý do cuối cùng). File này chính là danh sách sản phẩm lỗi kèm lý do mà DoD yêu cầu. Chép các con số vào bảng **Kết quả** của README.

## 10. Commit và công bố

Trong `Project_02`:
```bash
git status                 # không có gì từ data/, output*/, errors*/, logs/
git add .gitignore README.md README.vi.md RUNBOOK.md RUNBOOK.vi.md GUIDE.md GUIDE.vi.md steps/ *.py requirements.txt
git commit -m "<thay đổi gì>"
```
Trong repo journey:
```bash
cd /mnt/c/Users/Admin/Desktop/data-engineering-journey
git update-index --refresh
git subtree pull --prefix=project_02 /mnt/c/Users/Admin/Desktop/Project_02 main -m "Update project_02 from Project_02"
git push
```
Kiểm tra `https://github.com/dottienguyen23/data-engineering-journey/tree/main/project_02`.

## 11. Nộp bài

- [ ] Bảng kết quả trong README đã điền từ bước 9
- [ ] Có `final_errors.csv` (đã commit, hoặc phần tóm tắt nằm trong README)
- [ ] Repo đã push và kiểm tra trên GitHub
- [ ] Đã nộp link repo qua Google Form của khóa học
- [ ] Đã viết Task Report hằng ngày ("taki taki")
