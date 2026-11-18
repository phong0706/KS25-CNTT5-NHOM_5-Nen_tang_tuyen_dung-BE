# TechRecruit Backend — FastAPI + SQLAlchemy + MySQL

Backend REST API cho nền tảng tuyển dụng CNTT **TechRecruit** (Nhóm 5 — HN-KS25-CNTT5).

---

## 1. Repo Frontend liên kết & Nhánh cần checkout

- **Repo Frontend**: https://github.com/phong0706/KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-FE.git
- **Nhánh Frontend cần checkout**: `chore/restructure-project`
- **Nhánh Backend cần checkout**: `add/chucnang`

> **Lưu ý quan trọng khi mới clone**: Mặc định `git clone` sẽ đứng ở `main`. Hãy chạy ngay:
> ```bash
> git clone https://github.com/phong0706/KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-BE.git
> cd KS25-CNTT5-NHOM_5-Nen_tang_tuyen_dung-BE
> git checkout add/chucnang
> ```

---

## 2. Yêu cầu hệ thống

- **Python**: `3.10+` (đã kiểm thử ổn định trên `Python 3.14.7`)
- **MySQL**: `8.0+` (khuyến nghị cài MySQL Server 8 + MySQL Workbench, hoặc dùng `docker-compose.yml` đi kèm)
- **Docker** *(tùy chọn)*: dùng `docker compose up -d` trong thư mục này nếu muốn chạy nhanh MySQL 8.0 ở cổng `3307`

---

## 3. Tạo file `.env` (KHÔNG commit `.env`)

Mở terminal tại thư mục gốc của repo backend và copy file mẫu:

```bash
# Windows PowerShell / CMD
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Mở `.env` và điền các giá trị bắt buộc (ứng dụng sẽ **dừng khởi động** và báo rõ tên biến nếu thiếu):

- `DB_PASSWORD`: mật khẩu tài khoản MySQL của bạn (`root` hoặc `app_password` nếu dùng Docker).
- `JWT_SECRET`: chuỗi bí mật ngẫu nhiên tối thiểu 32 ký tự. Tạo nhanh bằng:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- `CORS_ORIGINS`: giữ đủ 4 địa chỉ Live Server để tránh lỗi CORS giữa `127.0.0.1` và `localhost`:
  ```env
  CORS_ORIGINS=http://127.0.0.1:5501,http://localhost:5501,http://127.0.0.1:5502,http://localhost:5502
  ```

> Tuyệt đối không commit file `.env` lên Git (đã được chặn trong `.gitignore`).
> **Lưu ý**: Đổi `JWT_SECRET` sẽ làm mọi token đăng nhập cũ không còn dùng được — toàn bộ người dùng đang mở phiên cũ cần đăng nhập lại để nhận token mới.

---

## 4. Cài đặt thư viện Python

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# Windows CMD
.venv\Scripts\activate.bat
# Mac / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 5. Khởi tạo Database (`sql/`)

Chạy lần lượt các tệp SQL trong thư mục `sql/` trên MySQL 8.0 (`utf8mb4`) theo đúng thứ tự phụ thuộc khóa ngoại sau:

1. `sql/init.sql` — Tạo database `app_db`, bảng `users`, `items` và tài khoản mẫu. *(Hoặc chạy nhanh: `python scripts/run_init_sql.py`)*
2. `sql/catalog_and_reports.sql` — Tạo danh mục `industries`, `locations`, `skills` và bảng `reports`.
3. `sql/companies.sql` — Tạo bảng `companies`.
4. `sql/companies_profile_migration.sql` — Bổ sung các cột hồ sơ công ty (`slug`, `logo_url`, `cover_url`, `size`, ...).
5. `sql/company_verification_migration.sql` — Bổ sung cột xác minh trên `companies`.
6. `sql/migrate_company_verification.sql` — Tạo bảng `company_verifications`, cột `verification_status` và `audit_logs.reason` *(hoặc chạy: `python scripts/migrate_company_verification.py`)*.
7. `sql/candidate_profiles.sql` — Tạo bảng `candidate_profiles`, `candidate_skills`, `experiences`, `educations`.
8. `sql/jobs_module.sql` — Tạo bảng `jobs`, `job_skills`, `saved_jobs` và các bảng danh mục việc làm.
9. `sql/applications_and_interviews.sql` — Tạo bảng `cvs`, `applications`, `application_status_history`, `interviews`, mẫu thư.
10. Các bản vá bổ sung *(thứ tự tương đối giữa các file patch/migration độc lập ở nhóm này có thể linh hoạt miễn chạy sau các bảng gốc ở bước 1–9)*:
    - `sql/patch_notifications.sql` *(bảng `notifications`)*
    - `sql/patch_forgot_password.sql` *(bảng `password_reset_tokens`)*
    - `sql/patch_mega_menu.sql`
    - `sql/migrate_reports_schema.sql` *(nâng cấp bảng `reports` nếu đã chạy bản cũ)*
11. Dữ liệu mẫu (tùy chọn): `sql/seed.sql`, `sql/seed_public.sql`, hoặc chạy `python scripts/seed.py`, `python scripts/seed_company.py`.

---

## 6. Chạy server Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Khi khởi động thành công, terminal sẽ hiển thị `[DB] Đã kết nối MySQL 127.0.0.1:3306/app_db`.

---

## 7. Kiểm tra hoạt động

- Mở **Swagger UI**: http://127.0.0.1:8000/docs → trả trang tài liệu API (`200 OK`).
- Gọi thử endpoint danh sách việc làm:
  http://127.0.0.1:8000/api/jobs?page_size=3 → trả về JSON có danh sách việc làm (`total`, `items`).
- Kiểm tra sức khỏe hệ thống: http://127.0.0.1:8000/api/health → `{"status":"ok","database":"connected"}`.
- Chạy bộ kiểm thử tự động: `pytest -q`.

---

## 8. Lỗi thường gặp & Cách khắc phục

| Lỗi gặp phải | Nguyên nhân & Cách xử lý |
| :--- | :--- |
| `RuntimeError: Thiếu biến môi trường bắt buộc trong .env: DB_PASSWORD, JWT_SECRET` | Chưa tạo `.env` hoặc bỏ trống 2 biến này. Copy `.env.example` thành `.env`, điền đúng tên biến được báo trong thông báo rồi chạy lại `uvicorn`. |
| Trình duyệt báo `blocked by CORS policy` | Kiểm tra `CORS_ORIGINS` trong `.env` phải chứa đúng origin đang mở frontend (cả `127.0.0.1` lẫn `localhost`, cổng `5501` hoặc `5502`). Sửa `.env` xong phải khởi động lại `uvicorn`. |
| `Unknown database 'app_db'` hoặc API `/api/jobs` trả rỗng | Database chưa được khởi tạo hoặc chưa nạp dữ liệu. Chạy lại các file trong `sql/` theo đúng thứ tự ở mục 5. |
| `Error loading ASGI app. Could not import module "app.main"` | Đang chạy lệnh ở ngoài thư mục gốc của repo backend. Hãy `cd` vào đúng thư mục chứa `app/` và `.env` trước khi chạy `uvicorn`. |
