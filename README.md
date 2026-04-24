# Tích Truyện Pháp Cú — EPUB & PDF

Tự động tải và chuyển đổi bộ kinh **Tích truyện Pháp Cú** (Thiền viện Viên Chiếu) từ [budsas.org](https://www.budsas.org/uni/u-kinh-phapcu-ev/ttpc00.htm) sang định dạng EPUB và PDF.

## Tính năng

- Tải toàn bộ 26 phẩm (hơn 300 câu chuyện) từ nguồn gốc
- Cache HTML thô để không tải lại khi chạy nhiều lần
- Làm sạch nội dung: bỏ thanh điều hướng, footer, thẻ MS Word thừa
- Tạo mục lục (TOC) có liên kết đến từng câu chuyện trong EPUB
- Nhúng ảnh bìa vào cả hai định dạng
- Xuất đồng thời file `.epub` và `.pdf`

## File mẫu

- [Tích truyện pháp cú (PDF)](./tich-truyen-phap-cu.pdf)
- [Tích truyện pháp cú (EPUB)](./tich-truyen-phap-cu.epub)
  
## Yêu cầu

- Python 3.12+

## Cài đặt

```bash
# Tạo môi trường ảo
python -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows

# Cài đặt thư viện
pip install -r requirements.txt
```

## Cách sử dụng

```bash
source .venv/bin/activate
python scrape_epub.py
```

Lần đầu chạy sẽ tải toàn bộ HTML từ budsas.org về thư mục `raw_htmls/`. Các lần sau sẽ dùng cache nên chạy nhanh hơn.

Sau khi hoàn thành, hai file được tạo ra trong thư mục gốc:

| File | Mô tả |
|------|-------|
| `tich-truyen-phap-cu.epub` | Định dạng EPUB, dùng cho máy đọc sách |
| `tich-truyen-phap-cu.pdf` | Định dạng PDF, in ấn hoặc đọc trên máy tính |

## Cấu trúc thư mục

```
.
├── scrape_epub.py          # Script chính
├── cover.png               # Ảnh bìa
├── requirements.txt        # Danh sách thư viện
├── raw_htmls/              # Cache HTML (tự động tạo)
├── tich-truyen-phap-cu.epub
└── tich-truyen-phap-cu.pdf
```

## Nguồn

Nội dung kinh được lấy từ trang **BuddhaSasana** do Bình Anson duy trì:
https://www.budsas.org/uni/u-kinh-phapcu-ev/ttpc00.htm
