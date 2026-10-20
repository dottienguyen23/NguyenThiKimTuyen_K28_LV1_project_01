# =====================================================================
# DE Project 01 - Level 1: Phân tích dữ liệu phim TMDB bằng Linux command line
# Tác giả: Nguyen Thi Kim Tuyen - K28
# Yêu cầu: wget, mlr (Miller), awk, sort, cut, tr, uniq, grep
# Cách chạy: bash NguyenThiKimTuyen_K28_LV1_project_01.sh
# =====================================================================

mkdir -p output

# ---------------------------------------------------------------------
# 0. Tải dữ liệu gốc
# ---------------------------------------------------------------------
wget https://raw.githubusercontent.com/yinghaoz1/tmdb-movie-dataset-analysis/master/tmdb-movies.csv

# ---------------------------------------------------------------------
# 1. Làm sạch: CSV -> TSV
#    Các cột text (overview, tagline, cast, ...) chứa dấu phẩy và ký tự
#    xuống dòng bên trong dấu nháy "...", nên tách cột theo ',' sẽ bị sai.
#    Miller đọc CSV đúng chuẩn và ghi mỗi phim trên đúng một dòng.
# ---------------------------------------------------------------------
mlr --icsv --otsv cat tmdb-movies.csv > tmdb.tsv

# Kiểm tra: mỗi dòng phải có 21 cột (kết quả mong đợi: 10867 21)
echo "== Kiểm tra: số cột trên mỗi dòng =="
awk -F'\t' '{print NF}' tmdb.tsv | sort -n | uniq -c

# Bảng cột: 4 budget | 5 revenue | 6 original_title | 7 cast | 9 director
#           14 genres | 16 release_date (m/d/yy) | 17 vote_count
#           18 vote_average | 19 release_year

# ---------------------------------------------------------------------
# Q1. Sắp xếp phim theo ngày phát hành giảm dần -> lưu file mới
#     Ngày dạng m/d/yy không sort đúng được khi là text, nên tạo key
#     YYYYMMDD (lấy năm từ release_year), sort theo key, rồi bỏ key đi.
# ---------------------------------------------------------------------
head -1 tmdb.tsv > output/movies_sorted_by_date.tsv
tail -n +2 tmdb.tsv | awk -F'\t' '{ split($16, d, "/"); printf "%04d%02d%02d\t%s\n", $19, d[1], d[2], $0 }' | sort -t$'\t' -k1,1r | cut -f2- >> output/movies_sorted_by_date.tsv
echo
echo "== Q1: 5 phim mới nhất (file: output/movies_sorted_by_date.tsv) =="
head -6 output/movies_sorted_by_date.tsv | cut -f6,16

# ---------------------------------------------------------------------
# Q2. Lọc phim có vote_average > 7.5 -> lưu file mới
# ---------------------------------------------------------------------
awk -F'\t' 'NR==1 || $18 > 7.5' tmdb.tsv > output/movies_rating_above_7_5.tsv
echo
echo "== Q2: số dòng trong output/movies_rating_above_7_5.tsv (gồm 1 dòng header) =="
wc -l output/movies_rating_above_7_5.tsv

# ---------------------------------------------------------------------
# Q3. Phim có doanh thu cao nhất và thấp nhất
#     revenue = 0 nghĩa là thiếu dữ liệu -> loại khỏi phần "thấp nhất"
# ---------------------------------------------------------------------
cut -f5,6 tmdb.tsv | tail -n +2 | sort -t$'\t' -k1,1n > output/revenue_sorted.tsv
echo
echo "== Q3: doanh thu cao nhất =="
tail -1 output/revenue_sorted.tsv
echo "== Q3: số phim có revenue = 0 (thiếu dữ liệu) =="
awk -F'\t' '$1 == 0' output/revenue_sorted.tsv | wc -l
echo "== Q3: doanh thu thấp nhất (đã loại revenue = 0 vì thiếu dữ liệu) =="
awk -F'\t' '$1 > 0' output/revenue_sorted.tsv | head -3

# ---------------------------------------------------------------------
# Q4. Tổng doanh thu của tất cả các phim
# ---------------------------------------------------------------------
echo
echo "== Q4: tổng doanh thu (USD) =="
awk -F'\t' 'NR > 1 { s += $5 } END { print s }' tmdb.tsv

# ---------------------------------------------------------------------
# Q5. Top 10 phim có lợi nhuận cao nhất (revenue - budget),
#     chỉ tính phim có cả budget và revenue
# ---------------------------------------------------------------------
echo
echo "== Q5: top 10 phim lợi nhuận cao nhất =="
awk -F'\t' 'NR > 1 && $4 > 0 && $5 > 0 { print $5 - $4 "\t" $6 }' tmdb.tsv | sort -t$'\t' -k1,1nr | head -10 > output/top10_profit.tsv
awk -F'\t' '{
      v = $1
      if      (v >= 1e9) s = sprintf("$%.2fB", v / 1e9)
      else if (v >= 1e6) s = sprintf("$%.2fM", v / 1e6)
      else if (v >= 1e3) s = sprintf("$%.2fK", v / 1e3)
      else               s = "$" v
      print s "\t" $2
    }' output/top10_profit.tsv

# ---------------------------------------------------------------------
# Q6. Đạo diễn có nhiều phim nhất và diễn viên đóng nhiều phim nhất
#     Tách ô có nhiều giá trị (A|B) và bỏ giá trị rỗng trước khi đếm
# ---------------------------------------------------------------------
echo
echo "== Q6: đạo diễn có nhiều phim nhất =="
cut -f9 tmdb.tsv | tail -n +2 | tr '|' '\n' | grep -v '^$' | sort | uniq -c | sort -nr | head -5
echo "== Q6: diễn viên đóng nhiều phim nhất =="
cut -f7 tmdb.tsv | tail -n +2 | tr '|' '\n' | grep -v '^$' | sort | uniq -c | sort -nr | head -5

# ---------------------------------------------------------------------
# Q7. Số lượng phim theo thể loại (một phim có thể thuộc nhiều thể loại)
# ---------------------------------------------------------------------
echo
echo "== Q7: số phim theo thể loại =="
cut -f14 tmdb.tsv | tail -n +2 | tr '|' '\n' | grep -v '^$' | sort | uniq -c | sort -nr
echo "== Q7: số phim không có thể loại =="
cut -f14 tmdb.tsv | tail -n +2 | grep -c '^$'

# ---------------------------------------------------------------------
# Q8. Ý tưởng: phân tích chất lượng dữ liệu (chi tiết trong README, mục 4)
#
# Các vấn đề tìm thấy trong lúc làm bài:
#  1. Dấu phẩy bên trong text có dấu nháy: 9.173 / 10.879 dòng bị tách sai khi dùng dấu phẩy
#  2. Xuống dòng bên trong cột overview: 10.879 dòng nhưng chỉ có 10.866 phim
#  3. Định dạng ngày m/d/yy: không sắp xếp đúng được, năm 2 chữ số không rõ thế kỷ
#  4. Revenue = 0 (thiếu dữ liệu): 6.016 phim
#  5. Đạo diễn hoặc thể loại bị rỗng: 44 phim không có đạo diễn, 23 phim không có thể loại
#  6. Ký tự bị lỗi (mojibake), ví dụ â€œ
# ---------------------------------------------------------------------