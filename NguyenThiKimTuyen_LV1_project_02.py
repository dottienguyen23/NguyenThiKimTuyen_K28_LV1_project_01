"""
DE Project 02 – Level 1 · Tiki Product Scraper
Submission file: Nguyen Thi Kim Tuyen

This file is the entry point required by the course naming rule (Ho_Ten_LV1_project_02).
The scraper itself lives in scraper_simple.py, so the code exists in one place only.
File này là điểm chạy theo quy định đặt tên của khóa học. Code scraper nằm trong
scraper_simple.py, để code chỉ tồn tại ở một nơi.

What it does / Chức năng:
  1. Read ~200,000 product IDs from data/ids.csv (skip the header and duplicates)
  2. Split them into batches of 1,000 IDs
  3. For each ID: call the Tiki API, keep id, name, url_key, price, description, images,
     clean the HTML description into plain text
  4. Save each batch as output/products_XXXX.json; failed IDs with the reason as
     errors/errors_XXXX.csv
  5. Skip batches that already have a file (checkpoint), so a stopped run resumes
  6. When Tiki returns an HTML block page instead of JSON, wait and retry the same ID

Full process and results / Toàn bộ quy trình và kết quả:
  README.md · GUIDE.md (why) · RUNBOOK.md (how to run) · steps/ (checks, retry, final report)

Run from the project folder / Chạy từ thư mục project:
    python -u NguyenThiKimTuyen_LV1_project_02.py 2>&1 | tee -a logs/run.log
"""

from scraper_simple import main

if __name__ == "__main__":
    main()
