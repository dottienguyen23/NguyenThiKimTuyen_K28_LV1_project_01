# Project 02 – Tiki Product Scraper

🌐 [English](README.md) | **Tiếng Việt**

Lấy khoảng **200.000 sản phẩm** từ API sản phẩm của Tiki bằng Python, giữ các trường cần thiết, làm sạch, và lưu thành các file JSON khoảng 1.000 sản phẩm mỗi file. Mọi ID lỗi được ghi lại kèm lý do.

📘 **Quá trình xây dựng từng bậc:** [GUIDE.vi.md](GUIDE.vi.md) · [GUIDE.md](GUIDE.md)

🛠️ **Cách chạy từ đầu đến cuối:** [RUNBOOK.vi.md](RUNBOOK.vi.md) · [RUNBOOK.md](RUNBOOK.md)

## Yêu cầu (DoD)

- [x] Lấy thông tin sản phẩm cho mọi ID trong danh sách đầu vào
- [x] Giữ `id`, `name`, `url_key`, `price`, `description`, `images`
- [x] Làm sạch `description` (HTML → text)
- [x] Lưu khoảng 1.000 sản phẩm mỗi file `.json`
- [x] Ghi lại các ID lỗi kèm lý do
- [x] Tìm phương án rút ngắn thời gian lấy dữ liệu: xem [Rút ngắn thời gian chạy](#rút-ngắn-thời-gian-chạy)
- [x] Chạy đủ khoảng 200.000 ID: 200/200 batch (lượt một); lượt chạy lại cho lỗi tạm thời _đang chạy_

## Kết quả

| Chỉ số | Giá trị |
|---|---|
| Số ID đầu vào (không trùng) | 200.000 |
| Số sản phẩm đã lưu (sau lượt chạy lại) | _[điền từ `step10_final_report.py`]_ |
| Lấy lại được ở lượt chạy lại | _[điền]_ |
| Số ID lỗi cuối cùng | _[điền]_, chủ yếu là `HTTP 404` (sản phẩm đã bị xóa khỏi Tiki) |
| Sản phẩm + lỗi = số ID đầu vào | _[KHỚP / KHÔNG KHỚP]_ |
| Số id trùng trong output | _[điền]_ |
| Thời gian mỗi batch 1.000 ID khi chạy bình thường | khoảng 23 phút (≈ 1,4 giây mỗi ID) |
| Tổng thời gian thực tế (lượt một) | khoảng 6 ngày, xem [Dòng thời gian](#dòng-thời-gian-lần-chạy-1510--21102026) |

**Từ lần chạy thử** (3.000 ID, `scraper.py`): khoảng 31% mỗi batch bị lỗi (689 ok / 311 lỗi, rồi 687 / 313), và một batch bình thường mất khoảng 23 phút (khoảng 1,4 giây mỗi ID với thời gian nghỉ 1 giây).

## Cách hoạt động

```
data/ids.csv ──► đọc & bỏ trùng ID ──► chia batch 1.000 ID
                                          │
              với mỗi ID: gọi API ──► lấy 6 trường ──► làm sạch description
                                          │
       output/products_0001.json      errors/errors_0001.csv
       (lần sau bỏ qua = checkpoint)    (id, reason)
```

- **Giới hạn tốc độ:** mỗi lần một request, cách nhau 1 giây. Chạy nhanh hơn thì bị hệ thống chống bot của Tiki chặn.
- **Lỗi không làm dừng chương trình:** lỗi mạng, lỗi HTTP và response không phải JSON được ghi thành một dòng trong `errors/` kèm lý do.
- **Chạy tiếp được:** mỗi batch xong là một file. Sau khi crash hay restart, các batch đã xong được bỏ qua.
- **Ghi nguyên tử:** file JSON được ghi ra `.tmp` rồi mới đổi tên, nên crash giữa chừng không bao giờ để lại file dở dang.
- **Phát hiện bị chặn:** nhận HTML thay vì JSON nghĩa là đang bị chặn. Scraper chờ rồi thử lại, thay vì ghi hàng nghìn lỗi giả.

## Dòng thời gian lần chạy (15/10 – 21/10/2026)

Đo bằng `steps/step8c_runtime.py`, dựa trên thời điểm lưu mỗi file output.

| Thời gian | Chuyện gì xảy ra | Nhận xét |
|---|---|---|
| 15/10 08:57 → 12:38 | Chạy thử `scraper.py` (`LIMIT = 3000`). Batch 1: 23 phút, batch 2: **3h18m** | Bị chặn ở batch 2; bản v4 chờ rồi làm lại cả batch |
| 15/10 12:38 → 16/10 07:27 | Batch 3 và 4 | Phần lớn là thời gian nghỉ giữa các lần test, không phải scraper chạy chậm |
| 16/10 07:27 → 17/10 08:28 | Batch 5–61 chạy đều | ✅ Bình thường: khoảng 23 phút mỗi batch (≈ 1,4 giây mỗi ID) |
| **17/10 08:28 → 18/10 ~23:45** | Batch 62–73 **mỗi batch đúng 3h03m** | ❌ 3h03m ≈ 1.000 × (timeout 10 giây + nghỉ 1 giây): gần như mọi request đều timeout |
| 18/10 ~23:45 | Restart Windows để sửa wifi | Mất batch đang chạy (74) |
| 18/10 23:51 → 19/10 00:15 | Chạy lại scraper trong `tmux`, batch 74 xong | ✅ Checkpoint bỏ qua batch 1–73 |
| 19/10 → sáng 21/10 | Batch 75–200 chạy đều, có 2 lần gián đoạn khoảng 1h40m (trước batch 157 và 187) | ✅ Xong: 200/200 batch |

**Phát hiện chính:** giai đoạn timeout trùng với lúc wifi có vấn đề. Kết nối nhiều khả năng chập chờn hoặc mất trong khoảng 1,5 ngày, và `scraper_simple.py` vẫn chạy tiếp: tốn khoảng 40 giờ cho các request không thể thành công, và biến khoảng 12.000 ID thành lỗi `ReadTimeout`/`ConnectTimeout`. Các ID này được chạy lại ở lượt hai (`steps/step9_retry_failed.py`).

| Thời gian | Giá trị |
|---|---|
| Tổng thời gian thực tế của lượt một | khoảng 6 ngày |
| Thời gian `step8c_runtime.py` tính là gián đoạn | 60h55m (43%), gồm cả thời gian nghỉ giữa lần test và lần chạy chính |
| Thời gian mất vì kết nối chết (batch 62–74) | khoảng 40 giờ |
| Thời gian dự kiến nếu không có sự cố (200 × 23 phút) | khoảng 77 giờ (3,2 ngày) |
| Mức tối thiểu với 1 giây mỗi ID | 55,5 giờ |

## Rút ngắn thời gian chạy

| Cách làm | Kết quả |
|---|---|
| `requests.Session()` (dùng lại kết nối) | Dùng trong cả hai phiên bản: không phải bắt tay TCP/TLS lại cho mỗi request |
| Kiểm tra tốc độ an toàn bằng `probe_rate.py` (mỗi lần một request) | **Nghỉ 1 giây (~0,75 req/s thực tế):** 150 request trong 200 giây, **không bị chặn**, 93 ok / 57 `HTTP 404` |
| | **Nghỉ 0,2 giây (~1,9 req/s thực tế):** **bị chặn chỉ sau 11 request (6 giây)** |
| | Chạy `probe_rate.py 1 150` ngay sau đó: bị chặn ở request đầu tiên. Lệnh chặn vẫn còn hiệu lực, nên cần nghỉ giữa các lần thử. Kiểm tra bằng `curl` vài phút sau thì đã nhận lại JSON |
| Gửi request song song bằng `ThreadPoolExecutor`, đo bằng `steps/probe_workers.py` | **1 worker (0,64 req/s):** 100 request, không bị chặn, 55 ok / 45 `HTTP 404`. **2 worker (1,43 req/s):** **bị chặn**: 62 trên 100 request nhận trang chặn (31 ok / 7 `HTTP 404` trước đó). Giới hạn của Tiki **dưới ~1,4 req/s**, nên thêm worker không thể làm nhanh hơn → `MAX_WORKERS = 1` |
| Kiểm tra User-Agent | `curl` với User-Agent mặc định `curl/8.5.0` cũng nhận được JSON: lệnh chặn dựa vào **tốc độ request**, không dựa vào header |
| Không bao giờ chạy lại `HTTP 404` | Khoảng 31% ID là sản phẩm không còn; mỗi ID chỉ tốn một request, không phải nhiều lần |
| **Circuit breaker** (lượt chạy lại) | Sau 20 lỗi mạng liên tiếp: dừng, chờ đến khi API trả lời, chạy lại các ID đó. Lẽ ra đã tiết kiệm được phần lớn khoảng 40 giờ |
| **Timeout ngắn hơn** (lượt chạy lại) | `TIMEOUT = 5` thay vì 10: một request chết tốn 6 giây thay vì 11 giây |
| Tránh gián đoạn | `tmux`, đặt Windows sleep = *Never*, sửa wifi mà không restart |

**Kết luận:** code không phải điểm nghẽn. Tiki chặn ở đâu đó giữa 0,75 và 1,4 request/giây, nên giới hạn tốc độ quyết định mức tối thiểu (khoảng 55–75 giờ), và phần lãng phí lớn nhất có thể tránh được (khoảng 40 giờ) đến từ việc chạy mù trên một kết nối đã chết. Cách rút ngắn hiệu quả nhất là **phát hiện lỗi sớm**, không phải gửi request nhanh hơn.

## Chỗ sai và cách cải thiện

| # | Chỗ sai | Hậu quả | Cải thiện |
|---|---|---|---|
| 1 | `scraper_simple.py` không nhận ra nhiều timeout liên tiếp | ~40 giờ lãng phí, ~12.000 ID phải chạy lại | Circuit breaker + timeout ngắn hơn (`step9_retry_failed.py`) |
| 2 | Không theo dõi trong lúc chạy | Sự cố không ai thấy trong 1,5 ngày | In số lỗi theo loại mỗi batch, cảnh báo khi một batch toàn timeout, xem `tail logs/run.log` hai lần mỗi ngày |
| 3 | Chạy `scraper_simple.py` không có `tee` | Không có log để phân tích sau | Luôn dùng `\| tee -a logs/run.log`, hoặc dùng `logging` như `scraper.py` |
| 4 | Restart Windows để sửa wifi | Tắt WSL, `tmux` và scraper; mất một batch | Bật/tắt Airplane mode hoặc adapter wifi thay vì restart |
| 5 | `scraper.py` làm lại cả batch sau khi bị chặn | Batch 2 mất 3h18m | Đánh đổi có chủ ý: batch nào được lưu cũng đầy đủ |
| 6 | Project nằm trên ổ Windows (`/mnt/c`) | Ghi file chậm hơn; `git subtree` báo thay đổi giả | Project chạy lâu nên để trong hệ thống file của WSL (`~/projects/`) |

Không phải lỗi: khoảng 31% `HTTP 404` đến từ dữ liệu. Các sản phẩm này đã bị xóa khỏi Tiki sau khi danh sách ID được tạo, và đúng là không nên chạy lại chúng.

## Cấu trúc project

```
project_02/
├── scraper_simple.py   # bản đơn giản (~150 dòng): nên đọc bản này trước
├── scraper.py          # bản hoàn thiện: retry, logging, thanh tiến độ, giới hạn thời gian chờ khi bị chặn, kiểm tra kết quả
├── probe_rate.py       # đo xem gọi API nhanh đến mức nào thì bị chặn
├── steps/              # code của guide, mỗi bậc một script nhỏ chạy được
│   ├── step1_one_product.py ... step5_batch_checkpoint.py
│   ├── step8_check_results.py       # độ đầy đủ: không thiếu, không trùng
│   ├── step8b_profile_products.py   # chất lượng: trường rỗng, giá, description
│   ├── step8c_runtime.py            # thời gian chạy: mỗi batch, các lần gián đoạn, dự báo
│   ├── probe_workers.py             # Tiki chịu được bao nhiêu worker song song
│   ├── step9_retry_failed.py        # lượt hai cho lỗi tạm thời, có circuit breaker
│   └── step10_final_report.py       # gộp hai lượt -> final_errors.csv
├── GUIDE.md / GUIDE.vi.md
├── RUNBOOK.md / RUNBOOK.vi.md   # mọi lệnh, theo thứ tự
└── requirements.txt
```

Không đưa lên Git (xem `.gitignore`): `data/` (danh sách ID), `output/`, `errors/`, `logs/`, `.venv/`.

## Cách chạy

```bash
cd project_02
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# đặt danh sách ID do khóa học cung cấp ở data/ids.csv (mỗi dòng một ID, dòng tiêu đề "id")

# chạy thử trước: đặt LIMIT = 3000 trong scraper_simple.py (phải là bội số của 1000)
python scraper_simple.py
```

Chạy toàn bộ mất vài ngày, nên chạy trong `tmux` và lưu log ra file:

```bash
tmux new -s tiki
source .venv/bin/activate
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
# Ctrl-b rồi d để thoát ra; tmux attach -t tiki để vào lại
```

Kiểm tra kết quả sau khi chạy (hoặc trong lúc đang chạy):

```bash
python steps/step8_check_results.py
python steps/step8b_profile_products.py
python steps/step8c_runtime.py
```

Chạy lại các lỗi tạm thời, rồi tạo báo cáo cuối:

```bash
python steps/step8_check_results.py                 # tạo retry_ids.csv (mọi lỗi trừ HTTP 404)
python -u steps/step9_retry_failed.py 2>&1 | tee -a logs/retry.log
python steps/step10_final_report.py                 # tạo final_errors.csv (id, lý do cuối cùng)
```

## Bài học rút ra

- **Ước tính thời gian chạy trước.** Với 1,4 giây mỗi ID, 200.000 ID mất hơn 3 ngày. Điều đó quyết định thiết kế: batch, checkpoint và `tmux`.
- **Status 200 vẫn có thể là lỗi.** Trang chặn bot trả về `200 OK` kèm HTML. Kiểm tra `Content-Type` sẽ phát hiện được.
- **Lỗi vĩnh viễn khác lỗi tạm thời.** `HTTP 404` (sản phẩm không còn) không bao giờ chạy lại; timeout, `429` và `5xx` thì có.
- **`tmux` không sống sót qua restart Windows.** Restart để sửa wifi làm tắt WSL và scraper. Checkpoint giới hạn thiệt hại ở một batch.
- **Xử lý từng lỗi là chưa đủ; phải theo dõi tỷ lệ lỗi.** Mọi timeout đều được ghi lại đúng, vậy mà 1,5 ngày timeout không ai nhận ra. Trong pipeline thật, đây là việc của **monitoring và alerting**.
- **"Chạy xong" không có nghĩa là "đủ dữ liệu".** Số sản phẩm + số lỗi phải bằng số ID đầu vào; `step8_check_results.py` và `step10_final_report.py` kiểm tra điều này.

Danh sách đầy đủ các vấn đề và cách giải quyết nằm trong [GUIDE.vi.md](GUIDE.vi.md).
