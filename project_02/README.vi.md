# Project 02 – Tiki Product Scraper

🌐 [English](README.md) | **Tiếng Việt**

Lấy khoảng **200.000 sản phẩm** từ API sản phẩm của Tiki bằng Python, giữ các trường cần thiết, làm sạch, và lưu thành các file JSON khoảng 1.000 sản phẩm mỗi file. Mọi ID lỗi được ghi lại kèm lý do.

📘 **Quá trình xây dựng từng bậc:** [GUIDE.vi.md](GUIDE.vi.md) · [GUIDE.md](GUIDE.md)

## Yêu cầu (DoD)

- [x] Lấy thông tin sản phẩm cho mọi ID trong danh sách đầu vào
- [x] Giữ `id`, `name`, `url_key`, `price`, `description`, `images`
- [x] Làm sạch `description` (HTML → text)
- [x] Lưu khoảng 1.000 sản phẩm mỗi file `.json`
- [x] Ghi lại các ID lỗi kèm lý do
- [ ] Tìm phương án rút ngắn thời gian lấy dữ liệu: _đã đo, xem [Rút ngắn thời gian chạy](#rút-ngắn-thời-gian-chạy)_
- [ ] Chạy đủ khoảng 200.000 ID: _đang chạy_

## Kết quả

| Chỉ số | Giá trị |
|---|---|
| Số ID đầu vào (không trùng) | 200.000 |
| Số sản phẩm đã lưu | _[điền từ `step8_check_results.py`]_ |
| Số ID lỗi | _[điền]_, chủ yếu là _[lý do chính]_ |
| OK + lỗi = số ID đầu vào | _[KHỚP / KHÔNG KHỚP]_ |
| Số id trùng trong output | _[điền]_ |
| Thời gian trung vị mỗi batch 1.000 ID | _[điền từ `step8c_runtime.py`]_ |
| Tổng thời gian thực tế | _[điền]_ |

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

## Rút ngắn thời gian chạy

Lấy lần lượt 200.000 sản phẩm, mỗi sản phẩm khoảng 1,4 giây, mất hơn 3 ngày. Những gì đã thử và kết quả:

| Cách làm | Kết quả |
|---|---|
| `requests.Session()` (dùng lại kết nối) | Dùng trong cả hai phiên bản: không phải bắt tay TCP/TLS lại cho mỗi request |
| Gửi request song song bằng `ThreadPoolExecutor` (`scraper.py`, `benchmark()`) | Đã thử 10, 20 và 50 worker: _[điền: thời gian và số lỗi mỗi mức]_ |
| Tìm tốc độ an toàn bằng `probe_rate.py` | _[điền: tốc độ mà Tiki bắt đầu chặn]_ → giữ 1 worker, nghỉ 1 giây |
| Không bao giờ chạy lại `HTTP 404` | Sản phẩm không còn chỉ tốn một request, không phải nhiều lần |
| Loại bỏ gián đoạn (không sleep, không restart, `tmux`) | Gián đoạn chiếm _[điền từ `step8c_runtime.py`]_ tổng thời gian thực tế |

**Kết luận:** _[điền, ví dụ "điểm nghẽn là giới hạn tốc độ của Tiki, không phải code: trên X request/giây thì API chặn, nên cách rút ngắn thực tế là loại bỏ gián đoạn"]_.

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
│   └── step8c_runtime.py            # thời gian chạy: mỗi batch, các lần gián đoạn, dự báo
├── GUIDE.md / GUIDE.vi.md
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

## Bài học rút ra

- **Ước tính thời gian chạy trước.** Với 1,4 giây mỗi ID, 200.000 ID mất hơn 3 ngày. Điều đó quyết định thiết kế: batch, checkpoint và `tmux`.
- **Status 200 vẫn có thể là lỗi.** Trang chặn bot trả về `200 OK` kèm HTML. Kiểm tra `Content-Type` sẽ phát hiện được.
- **Lỗi vĩnh viễn khác lỗi tạm thời.** `HTTP 404` (sản phẩm không còn) không bao giờ chạy lại; timeout, `429` và `5xx` thì có.
- **`tmux` không sống sót qua restart Windows.** Restart để sửa wifi làm tắt WSL và scraper. Checkpoint giới hạn thiệt hại ở một batch.
- **"Chạy xong" không có nghĩa là "đủ dữ liệu".** Số sản phẩm + số lỗi phải bằng số ID đầu vào; `step8_check_results.py` kiểm tra điều này.

Danh sách đầy đủ các vấn đề và cách giải quyết nằm trong [GUIDE.vi.md](GUIDE.vi.md).
