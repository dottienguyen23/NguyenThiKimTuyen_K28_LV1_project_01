# Data Engineering Journey

🌐 [English](README.md) | **Tiếng Việt**

Hành trình thực hành để trở thành data engineer của mình: mỗi project một thư mục, gồm code, kết quả, và **quá trình đi đến kết quả đó**, kể cả những lỗi, hướng sai và cách sửa trên đường.

## Các project

| # | Project | Công cụ | Trạng thái |
|---|---|---|---|
| 01 | [Phân tích dữ liệu phim TMDB bằng dòng lệnh Linux](project_01/) | Bash, `awk`, `sort`, `cut`, `uniq`... | ✅ Hoàn thành |
| 02 | [Tiki scraper: khoảng 200.000 sản phẩm từ API ra JSON](project_02/) · [hướng dẫn từng bậc](project_02/GUIDE.vi.md) | Python, `requests`, BeautifulSoup, `tmux`, Git | 🚧 Đang làm |

## Cách mỗi project được ghi lại

- **README**: bài toán, kết quả, và cách chạy.
- **Quá trình quan trọng hơn bề ngoài**: mỗi project giữ lại những lỗi mình gặp và cách giải quyết, vì đó là nơi học được nhiều nhất.
- **Hướng dẫn từng bậc** (từ Project 02): lời giải được xây dựng từng bậc, bắt đầu từ phiên bản đơn giản nhất chạy được. Mỗi bậc mở đầu bằng một vấn đề để tự suy nghĩ trước khi xem lời giải.

## Cấu trúc repo

```
data-engineering-journey/
├── project_01/     # TMDB – Linux CLI
├── project_02/     # Tiki scraper – Python
└── .gitignore      # quy tắc chung: file data, output và môi trường ảo không đưa lên Git
```

Dữ liệu thô và output sinh ra **không** được commit. README của từng project giải thích cách tải hoặc tạo lại chúng.

## Kỹ năng đã thực hành

- **Linux & shell**: di chuyển trong hệ thống file, pipeline xử lý text, `tmux`, process, log
- **Lấy dữ liệu**: gọi REST API, giới hạn tốc độ, xử lý khi bị chặn và khi lỗi
- **Làm sạch dữ liệu**: HTML sang text, bỏ trùng, kiểm tra input
- **Độ tin cậy của pipeline**: batching, checkpoint, ghi nguyên tử, chạy tiếp sau khi dừng, đối soát kết quả
- **Git & GitHub**: commit, `.gitignore`, đổi tên và tái cấu trúc repo mà không mất lịch sử
