# Tiki Product Scraper – Hướng dẫn từng bậc (Project 02)

🌐 [English](GUIDE.md) | **Tiếng Việt**

**Mục tiêu:** lấy khoảng 200.000 sản phẩm Tiki qua API, giữ 6 trường (`id`, `name`, `url_key`, `price`, `description`, `images`), làm sạch `description`, lưu khoảng 1.000 sản phẩm mỗi file JSON, và ghi lại mọi ID lỗi kèm lý do.

Guide này không bắt đầu bằng code hoàn chỉnh. Mỗi bậc mở đầu bằng một **vấn đề**. Hãy thử trả lời phần **🤔 Tự nghĩ trước** rồi mới mở lời giải. Hai phiên bản cuối là `scraper_simple.py` (bậc 6) và `scraper.py` (bậc 9).

| Phần | Ý nghĩa |
|---|---|
| 🎯 Mục tiêu | Bậc này làm được gì |
| ⚠️ Vấn đề | Bậc trước còn thiếu gì, hoặc chuyện gì xảy ra khi chạy thật |
| 🤔 Tự nghĩ trước | Dừng lại suy nghĩ trước khi đọc tiếp |
| 💡 Gợi ý | Hàm hoặc khái niệm cần dùng |
| ✅ Lời giải | Code (đang thu gọn, bấm để mở) |
| 📌 Bài học | Khái niệm data engineering rút ra |

## Lộ trình

| Bậc | Xây dựng gì | Vấn đề dẫn sang bậc sau |
|---|---|---|
| 0 | `curl` một ID bằng tay | Làm tay 200k lần là không thể |
| 1 | Python: một sản phẩm, 6 trường | `description` là HTML lộn xộn |
| 2 | `clean_description()` | Mới làm được một ID |
| 3 | Lặp nhiều ID, lưu một file | Một response lỗi là crash hết |
| 4 | Xử lý lỗi | Chạy hơn 3 ngày; restart là làm lại từ đầu |
| 5 | Batch + checkpoint | Tiki chặn bot |
| 6 | Phát hiện bị chặn → `scraper_simple.py` | Đóng terminal hay restart máy là scraper chết |
| 7 | Vận hành: `tmux`, log | Kết quả đã đủ và đúng chưa? |
| 8 | Kiểm tra kết quả | Muốn chắc chắn và tự động hơn |
| 9 | Hoàn thiện → `scraper.py` (v4) | — |

---

## Bậc 0 – Xem API bằng tay

🎯 **Mục tiêu:** hiểu một lần gọi API trả về gì trước khi viết Python.

⚠️ **Vấn đề:** chưa biết định dạng response. Có phải JSON không? Có cần header đặc biệt không?

🤔 **Tự nghĩ trước:** làm sao kiểm tra một endpoint trả về JSON hay trang HTML mà **không** in cả body ra?

💡 **Gợi ý:** tùy chọn `-o` (body đi đâu) và `-w` (in một biến sau request) của `curl`.

<details>
<summary>✅ Lời giải</summary>

```bash
# Chỉ xem status code và content type
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" -A "Mozilla/5.0" \
  https://api.tiki.vn/product-detail/api/v1/products/1391347
# -> 200 application/json; charset=utf-8

# In đẹp 40 dòng đầu của body
curl -s -A "Mozilla/5.0" https://api.tiki.vn/product-detail/api/v1/products/1391347 \
  | python -m json.tool | head -40
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `-s` | chế độ im lặng, không hiện thanh tiến độ |
| `-o /dev/null` | bỏ body đi |
| `-w "..."` | write-out: chỉ in các biến này |
| `-A "Mozilla/5.0"` | đặt header User-Agent |
| `\` | viết tiếp lệnh ở dòng sau |

</details>

📌 **Bài học:** xem nguồn dữ liệu trước khi viết code. `Content-Type` cho biết mình nhận được **dữ liệu** (`application/json`) hay **trang chặn** (`text/html`).

---

## Bậc 1 – Một sản phẩm bằng Python

🎯 **Mục tiêu:** cùng request đó bằng Python, chỉ giữ 6 trường cần thiết.

⚠️ **Vấn đề:** API trả về khoảng 60 trường (`badges`, `inventory`, `seller`...). Mình chỉ cần 6.

🤔 **Tự nghĩ trước:** tại sao dùng `p.get("name")` thay vì `p["name"]`?

💡 **Gợi ý:** `requests.get(..., timeout=10)`, `r.json()`, `dict.get()`.

<details>
<summary>✅ Lời giải: <code>steps/step1_one_product.py</code></summary>

```python
r = requests.get(API_URL.format(PRODUCT_ID), headers=HEADERS, timeout=10)
p = r.json()
product = {
    "id": p.get("id"),
    "name": p.get("name"),
    "url_key": p.get("url_key"),
    "price": p.get("price"),
    "description": p.get("description"),
    "images": [img.get("base_url") for img in (p.get("images") or [])],
}
```

**Trả lời:** `p["name"]` báo `KeyError` nếu sản phẩm không có `name`; `p.get("name")` trả về `None` và chương trình chạy tiếp.
`(p.get("images") or [])` xử lý được cả trường hợp thiếu trường lẫn giá trị `null`.

</details>

**Quan sát từ dữ liệu thật**
- API có trường viết là `promitions` (lỗi chính tả của Tiki). Giữ nguyên tên key của nguồn, nếu không phần mapping sẽ hỏng.
- `name` có thể chứa hai khoảng trắng liền nhau: `Tia Sáng  Gương`.
- `price` là số nguyên, đơn vị VND: `211200`.

📌 **Bài học:** đây là bước **Extract**: chỉ lấy những gì bước sau cần.

---

## Bậc 2 – Làm sạch description

🎯 **Mục tiêu:** biến `description` dạng HTML thành text sạch.

⚠️ **Vấn đề:** `description` chứa tag (`<p>`, `<br>`), ký tự mã hóa (`&amp;`, `&nbsp;`) và rất nhiều dấu xuống dòng.

🤔 **Tự nghĩ trước:** có ba loại "nhiễu" khác nhau cần bỏ. Đó là gì?

💡 **Gợi ý:** `BeautifulSoup(...).get_text(" ")`, `html.unescape()`, `re.sub(r"\s+", " ", ...)`.

<details>
<summary>✅ Lời giải: <code>steps/step2_clean_description.py</code></summary>

```python
def clean_description(raw_html):
    if not raw_html:
        return ""
    text = BeautifulSoup(raw_html, "html.parser").get_text(" ")  # 1. bỏ tag
    text = html.unescape(text)                                   # 2. &amp; -> &
    return re.sub(r"\s+", " ", text).strip()                     # 3. gộp khoảng trắng
```

</details>

**Lưu ý**
- Không có dấu phân cách `" "`, `get_text()` sẽ dính các chữ vào nhau: `<p>Xin</p><p>chào</p>` → `Xinchào`.
- `\s` khớp cả `\xa0` (ký tự sinh ra từ `&nbsp;`), nên bước 3 bỏ luôn ký tự này.

📌 **Bài học:** đây là bước **Transform**. Chuẩn hóa text **trước khi** lưu, để mọi nơi dùng dữ liệu đều nhận cùng một giá trị sạch.

---

## Bậc 3 – Lặp qua nhiều ID

🎯 **Mục tiêu:** đọc danh sách ID, lấy từng sản phẩm, lưu tất cả vào một file JSON.

⚠️ **Vấn đề:** ID nằm trong `data/ids.csv` (200.000 dòng).

🤔 **Tự nghĩ trước:**
1. Dòng đầu tiên của file là tiêu đề `id`. Chuyện gì xảy ra nếu coi nó là ID sản phẩm?
2. Nếu một ID xuất hiện hai lần thì sao?
3. 200.000 request với tốc độ 1 request/giây mất bao lâu?

💡 **Gợi ý:** `str.isdigit()`, `list(dict.fromkeys(ids))`, `time.sleep()`, `json.dump(..., ensure_ascii=False)`.

<details>
<summary>✅ Lời giải: <code>steps/step3_loop.py</code></summary>

```python
def read_ids(path):
    ids = []
    with open(path, encoding="utf-8-sig") as f:    # utf-8-sig bỏ ký tự BOM của Excel
        for line in f:
            value = line.strip()
            if value.isdigit():                    # bỏ dòng tiêu đề "id" và dòng trống
                ids.append(value)
    return list(dict.fromkeys(ids))                # bỏ trùng, giữ nguyên thứ tự
```

`ensure_ascii=False` giữ tiếng Việt đọc được trong file (`Gương`) thay vì `\u01b0\u01a1...`.

</details>

**Quan sát khi chạy thật**
- Log hiện `1 không hợp lệ ['id']`: chính là dòng tiêu đề, bị đếm là không hợp lệ. Vô hại, và chứng tỏ phần kiểm tra hoạt động đúng.
- Tốc độ đo được: khoảng **1,4 giây mỗi ID** (nghỉ 1 giây + thời gian phản hồi) → 200.000 × 1,4 giây ≈ **78 giờ (hơn 3 ngày)**.

📌 **Bài học:** **ước tính thời gian chạy trước khi chạy.** Một job 3 ngày cần thiết kế rất khác một job 3 phút.

⚠️ **Vấn đề mới:** `r.json()` crash ngay ở response lỗi đầu tiên, và mọi sản phẩm chỉ nằm trong bộ nhớ đến cuối, nên mất hết.

---

## Bậc 4 – Xử lý lỗi mà không dừng

🎯 **Mục tiêu:** ID lỗi được ghi lại kèm lý do; vòng lặp chạy tiếp.

🤔 **Tự nghĩ trước:** liệt kê mọi thứ có thể hỏng với **một** request.

<details>
<summary>Đáp án</summary>

| Chuyện gì xảy ra | Biểu hiện |
|---|---|
| Mất mạng, rớt wifi | `ConnectionError` |
| Server phản hồi quá chậm | `Timeout` |
| Sản phẩm không còn tồn tại | `HTTP 404` |
| Gửi quá nhiều request | `HTTP 429` |
| Lỗi phía server | `HTTP 500`–`504` |
| Trang chặn bot | `200` nhưng là HTML thay vì JSON |
| Body bị hỏng | `r.json()` báo `ValueError` |

</details>

💡 **Gợi ý:** `try/except requests.RequestException`, `timeout=10`, trả về tuple `(product, error)`, `requests.Session()`.

<details>
<summary>✅ Lời giải: <code>steps/step4_errors.py</code></summary>

```python
def get_product(session, product_id):
    """Trả về (sản phẩm, None) nếu thành công, hoặc (None, lý do) nếu lỗi."""
    try:
        r = session.get(API_URL.format(product_id), headers=HEADERS, timeout=10)
    except requests.RequestException as e:   # lớp cha của Timeout, ConnectionError, ...
        return None, type(e).__name__
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    try:
        p = r.json()
    except ValueError:
        return None, "bad_json"
    return {...}, None
```

Nơi gọi hàm:
```python
product, error = get_product(session, product_id)
if product:
    products.append(product)
else:
    errors.append([product_id, error])   # -> errors.csv với 2 cột id, reason
```

</details>

**Điểm chính**
- `timeout=10` rất quan trọng: không có nó, một kết nối chết có thể treo **mãi mãi**. Mặt trái là mỗi lần timeout tốn 10 giây.
- `requests.Session()` dùng lại kết nối TCP/TLS, nhanh hơn nhiều so với `requests.get()` khi gọi hàng nghìn lần.
- **404 và 429 cần xử lý khác nhau:** 404 là lỗi vĩnh viễn (không bao giờ chạy lại); 429, 5xx, `Timeout`, `ConnectionError` là lỗi tạm thời (chạy lại sau).

**Quan sát khi chạy thật:** khoảng **31% mỗi batch 1.000 ID bị lỗi** (689 ok / 311 lỗi, rồi 687 / 313). Tỷ lệ lỗi ổn định như vậy thường đến từ **dữ liệu**, nhiều khả năng là các sản phẩm đã bị xóa từ khi danh sách ID được tạo. Cột `reason` là cách kiểm chứng thay vì đoán.

**Lỗi trong phiên bản đầu:** `p = r.json()` nằm ngoài mọi `try`, nên chỉ một body hỏng cũng có thể làm crash cả batch.

📌 **Bài học:** một bản ghi lỗi không bao giờ được làm dừng pipeline. Bản ghi lỗi được chuyển sang một nơi riêng **kèm lý do** (thường gọi là file hoặc hàng đợi *dead-letter*) để phân tích và chạy lại.

---

## Bậc 5 – Batch + checkpoint

🎯 **Mục tiêu:** nếu đang chạy mà bị dừng, chạy lại sẽ tiếp tục từ chỗ đã dừng.

⚠️ **Vấn đề:** một job 3 ngày **chắc chắn** sẽ bị gián đoạn (restart, wifi, crash). Với một file lớn duy nhất, mọi thứ mất sạch.

🤔 **Tự nghĩ trước:**
1. Sau khi chạy lại, làm sao script biết phần nào đã xong?
2. Nếu máy tắt **đúng lúc** đang ghi file thì sao?

💡 **Gợi ý:** mỗi 1.000 ID một file, `os.path.exists()`, ghi ra `.tmp` rồi `os.replace()`.

<details>
<summary>✅ Lời giải: <code>steps/step5_batch_checkpoint.py</code></summary>

```python
for start in range(0, len(ids), BATCH_SIZE):
    batch_no = start // BATCH_SIZE + 1
    batch = ids[start:start + BATCH_SIZE]

    # Chính file output là bằng chứng batch đã xong
    if os.path.exists(f"{OUTPUT_DIR}/products_{batch_no:04d}.json"):
        continue
    ...
    save_batch(batch_no, products, errors)
```

```python
# Ghi nguyên tử: crash giữa chừng không bao giờ để lại file JSON dở dang
out = f"{OUTPUT_DIR}/products_{batch_no:04d}.json"
with open(out + ".tmp", "w", encoding="utf-8") as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
os.replace(out + ".tmp", out)
```

</details>

**Đáp án**
1. File output **chính là** checkpoint. Nếu `products_0007.json` tồn tại thì batch 7 đã xong.
2. Nếu script ghi thẳng vào `products_0007.json` rồi chết giữa chừng, một file hỏng sẽ tồn tại và bị bỏ qua ở lần sau. Ghi ra `.tmp` rồi đổi tên bằng `os.replace()` làm file cuối cùng xuất hiện **một lần trọn vẹn**, vì thao tác đổi tên là nguyên tử (atomic).

**Bẫy cần tránh**
- **Không bao giờ đổi `BATCH_SIZE` giữa các lần chạy.** Số thứ tự batch sẽ trỏ sang những ID khác.
- **`LIMIT` phải là bội số của `BATCH_SIZE`.** Với `LIMIT = 3500`, batch 4 chỉ có 500 ID nhưng vẫn được lưu thành `products_0004.json`. Khi chạy toàn bộ, nó bị coi là "đã xong" và 500 ID còn lại **không bao giờ được lấy**.

**Quan sát khi chạy thật:** restart Windows để kết nối lại wifi đã làm scraper dừng. Chỉ batch **đang chạy dở** bị mất; các batch đã xong được bỏ qua khi chạy lại.

📌 **Bài học:** job dài phải **resumable** (chạy tiếp được) và **idempotent** (chạy lại cho cùng kết quả, không trùng lặp). Ghi nguyên tử giữ cho output luôn đáng tin.

---

## Bậc 6 – Bị chặn → `scraper_simple.py`

🎯 **Mục tiêu:** nhận ra khi Tiki chặn bot và chờ, thay vì ghi hàng nghìn lỗi giả.

⚠️ **Vấn đề:** hệ thống chống bot thường trả `200 OK` kèm một **trang HTML** ("access denied", captcha). Status trông bình thường nhưng không có dữ liệu.

🤔 **Tự nghĩ trước:** làm sao phân biệt trang chặn với sản phẩm thật? Khi đó script nên làm gì?

💡 **Gợi ý:** kiểm tra `Content-Type` có chữ `"json"`; khi bị chặn thì `sleep` rồi thử lại **đúng ID đó**.

<details>
<summary>✅ Lời giải: <code>scraper_simple.py</code></summary>

```python
if "json" not in r.headers.get("Content-Type", ""):
    return None, "blocked"
```

```python
def get_product_wait_if_blocked(session, product_id):
    while True:
        product, error = get_product(session, product_id)
        if error != "blocked":
            return product, error
        print(f"Bị chặn ở ID {product_id}, chờ {WAIT_IF_BLOCKED}s...")
        time.sleep(WAIT_IF_BLOCKED)
```

</details>

**Giới hạn của phiên bản này**
- Chờ **mãi mãi** nếu không bao giờ hết bị chặn.
- Trang chặn trả về dạng `HTTP 403` không được nhận ra mà bị ghi thành lỗi bình thường. Nhiều lỗi `HTTP 403` liên tiếp gần như chắc chắn nghĩa là đang bị chặn.
- `r.headers.get("Content-Type", "")`: giá trị mặc định `""` tránh lỗi `TypeError` khi thiếu header.

📌 **Bài học:** đừng chỉ tin status code; hãy kiểm tra dữ liệu nhận về có đúng **kiểu** mình mong đợi.

---

## Bậc 7 – Chạy nhiều ngày (vận hành)

🎯 **Mục tiêu:** scraper sống sót khi đóng terminal và để lại log trên ổ đĩa.

⚠️ **Vấn đề:** process chạy trong terminal sẽ chết theo terminal đó, và output của `print` biến mất.

<details>
<summary>✅ Lời giải</summary>

```bash
cd /mnt/c/Users/Admin/Desktop/Project_02
tmux new -s tiki                          # session có tên, sống sót khi đóng cửa sổ
source .venv/bin/activate
python -u scraper_simple.py 2>&1 | tee -a logs/run.log
# Ctrl-b rồi d  -> thoát ra (detach), scraper vẫn chạy
```

| Lệnh | Mục đích |
|---|---|
| `python -u` | không đệm output: log hiện ra ngay |
| `2>&1` | gộp lỗi vào output thường |
| `tee -a logs/run.log` | in ra màn hình **và** ghi thêm vào file |
| `tmux ls` | liệt kê các session |
| `tmux attach -t tiki` | vào lại để xem tiến độ |
| `pgrep -af scraper` | process còn sống không? (hiện PID) |
| `tail -f logs/run.log` | theo dõi log trực tiếp |
| `kill <PID>` | dừng lịch sự (SIGTERM) |

</details>

**Quan sát khi chạy thật**
- **Restart Windows làm tắt WSL**, kéo theo tmux và scraper. tmux bảo vệ khi đóng cửa sổ, **không** bảo vệ khi tắt máy hay sleep → đặt chế độ sleep của Windows thành *Never* khi đang scrape.
- VS Code hiện `* History restored`: nó khôi phục **chữ** của terminal cũ, không khôi phục **process**. Màn hình trông như còn chạy nhưng thực ra không có gì chạy.
- `^[[A^[[B` trong thanh tiến độ = phím mũi tên ↑/↓ bị bấm khi script đang chạy. Vô hại.
- Project nằm trên `/mnt/c/...` (ổ Windows). WSL chậm hơn ở đó với nhiều thao tác ghi file nhỏ; `~/projects/` nhanh hơn cho I/O nặng.

📌 **Bài học:** pipeline gồm code **và** cách nó được vận hành. Log nằm trên ổ đĩa và process sống sót khi mất kết nối là nền tảng của vận hành.

---

## Bậc 8 – Kiểm tra kết quả

🎯 **Mục tiêu:** chứng minh không thiếu, không trùng, và biết lỗi nào đáng chạy lại.

🤔 **Tự nghĩ trước:** phương trình nào phải đúng ở cuối cùng?

<details>
<summary>Đáp án</summary>

**số sản phẩm OK + số lỗi = số ID duy nhất**, và **0 id trùng** trong output. Nếu không khớp thì có batch chưa xong hoặc bị thiếu.

</details>

💡 **Gợi ý:** `glob`, `csv.DictReader`, `collections.Counter`.

<details>
<summary>✅ Lời giải: <code>steps/step8_check_results.py</code></summary>

Script này:
1. đếm sản phẩm trong `output/products_*.json` và lỗi trong `errors/errors_*.csv`;
2. kiểm tra `ok + lỗi == len(ids)` và đếm id trùng;
3. in số lỗi theo từng `reason`;
4. ghi mọi ID lỗi khác 404 vào `retry_ids.csv` để chạy lượt hai.

`csv.DictReader` đọc theo tên cột, nên dùng được cả khi file lỗi có 2 cột (`scraper_simple.py`) hay 3 cột (`scraper.py`).

</details>

📌 **Bài học:** đây là **đối soát (reconciliation)**, một kiểm tra chất lượng dữ liệu cốt lõi. "Script chạy xong" không có nghĩa là "dữ liệu đã đủ".

---

## Bậc 9 – Hoàn thiện → `scraper.py` (v4)

Những gì v4 thêm so với `scraper_simple.py`, và lý do:

| Phần thêm | Lý do |
|---|---|
| `BASE_DIR = Path(__file__).resolve().parent` | Đường dẫn đúng dù chạy từ thư mục nào |
| `load_ids()` báo số dòng không hợp lệ và trùng | Input lỗi được nhìn thấy, không bị bỏ qua im lặng |
| `explore_one()` gọi thử trước khi chạy | Dừng sớm nếu API lỗi hoặc đang chặn |
| `Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, ...])` | Lỗi tạm thời được tự động thử lại, thời gian chờ tăng dần |
| `logging` ra màn hình **và** `logs/run.log` | Log được lưu mà không cần `tee` |
| `tqdm` + `logging_redirect_tqdm` | Thanh tiến độ với ETA tính theo trung bình |
| `BLOCKED` (`threading.Event`) | Khi bị chặn thì ngừng gửi request (gửi thêm chỉ kéo dài thời gian bị chặn) |
| `BLOCK_MAX_WAIT` | Bỏ cuộc sau 1 giờ thay vì chờ mãi |
| Làm lại cả batch sau khi bị chặn | Batch nào được lưu cũng luôn đầy đủ |
| `ThreadPoolExecutor` + `MAX_WORKERS` | Gửi request song song (giữ ở 1: nhanh hơn thì bị chặn) |
| `validate()` | Bậc 8 được tích hợp sẵn |

**Quan sát khi chạy thật:** batch 1 mất **1.382 giây**, batch 2 mất **11.880 giây** (chậm gấp 8,6 lần). Nguyên nhân khả dĩ là quy tắc "làm lại cả batch sau khi bị chặn": bị chặn giữa batch 2 nghĩa là phải chờ, rồi lấy lại toàn bộ 1.000 ID. Kiểm tra bằng:
```bash
grep "bị chặn" logs/run.log
```

📌 **Bài học:** mỗi tính năng tăng độ bền đều là một **sự đánh đổi**. Làm lại batch tốn tới 999 request thừa nhưng đảm bảo file luôn đầy đủ; chờ theo từng ID (bản simple) không tốn thêm request nhưng có thể treo vô hạn.

---

## Phụ lục – Các lỗi Git gặp trên đường

| Lỗi | Hậu quả | Cách sửa |
|---|---|---|
| Chạy `git config user.name/email` **sau** commit đầu tiên | Commit đầu mang danh tính cũ | `git commit --amend --reset-author --no-edit` (chỉ khi chưa push) |
| `user.email "<me@gmail.com>"` có dấu ngoặc nhọn | Dấu ngoặc bị lưu vào email; GitHub không liên kết commit với tài khoản | `git config --global user.email "me@gmail.com"` |
| `data/` chưa có trong `.gitignore` | `git add .` sẽ commit cả file dữ liệu lớn | Thêm `data/` vào `.gitignore` |
| Chữ `U` cạnh file trong VS Code | File chưa được theo dõi, chưa nằm trong commit nào | `git add <file>` rồi commit |

Mẹo: mỗi bậc một commit (`step 3: loop over IDs`) để `git log` kể lại đúng câu chuyện như guide này.
