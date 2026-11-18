# Tài liệu Migration & Seed Công ty Công khai (`/api/companies*`)

## 1. Nếu bạn đang dùng database cũ (đã tạo trước đây)
Chạy file migration idempotent (kiểm tra cột và index tồn tại trước khi thêm, chạy lại nhiều lần không lỗi):

```bash
# Cách 1: Chạy trực tiếp bằng MySQL CLI (thay tên DB đúng với DB_NAME trong backend/.env)
mysql -u root -p app_db < backend/sql/migrations/20261118_companies_public.sql

# Cách 2: Chạy qua script Python (tự động nạp migration SQL + cập nhật search_text + seed mẫu)
cd backend
python scripts/seed_public_companies.py
```

> Lưu ý: Script `seed_public_companies.py` giữ nguyên dữ liệu công ty sẵn có (`id 7..12`), đồng bộ lại `search_text` (bỏ dấu tiếng Việt, `đ -> d`) cho toàn bộ công ty, và chỉ bổ sung các công ty hư cấu nếu chưa tồn tại theo `slug` (chạy lại liên tiếp không nhân đôi dữ liệu).

## 2. Nếu bạn khởi tạo database mới hoàn toàn
1. Chạy `sql/01_schema.sql` (hoặc `sql/init.sql`) để tạo cấu trúc bảng.
2. Chạy `python scripts/seed_public_companies.py` trong `backend/` để đảm bảo các cột mở rộng, index và tối thiểu 12 công ty công khai được nạp đầy đủ.

## 3. Kiểm tra nhanh bằng pytest
```bash
cd backend
pytest tests/test_public_companies.py -v
```
