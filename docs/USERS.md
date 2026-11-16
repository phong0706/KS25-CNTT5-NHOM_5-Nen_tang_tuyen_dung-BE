# Hướng dẫn: API Quản lý tài khoản người dùng (Admin)

Task: Danh sách tài khoản (lọc vai trò / trạng thái, tìm kiếm, phân trang) + khoá / mở tài khoản kèm lý do (bị khoá thì không đăng nhập được).
Ngày thực hiện: 15/11/2026 — Nhóm 5 RIKKEILAB HN-KS25-CNTT5.

---

## 1. Danh sách API

| Method | URL | Mô tả | Auth |
|--------|-----|--------|------|
| GET | `/api/users` | Danh sách tài khoản: lọc role / trạng thái, tìm kiếm, phân trang | Bearer **admin** |
| POST | `/api/users/{user_id}/lock` | Khoá tài khoản kèm lý do | Bearer **admin** |
| POST | `/api/users/{user_id}/unlock` | Mở khoá tài khoản (xoá lý do) | Bearer **admin** |

> Lấy token admin: `POST /api/auth/login` với `admin@tuyendung.com` / `admin123@` (seed data), rồi gắn header `Authorization: Bearer <token>`.

---

## 2. GET /api/users — lọc / tìm kiếm / phân trang

Query params:

| Param | Kiểu | Default | Ý nghĩa |
|-------|------|---------|----------|
| `role` | string | — | Lọc vai trò: `candidate` \| `employer` \| `admin`. Sai giá trị → **400** |
| `is_active` | bool | — | `true` = đang hoạt động, `false` = bị khoá |
| `keyword` | string | — | Tìm theo email / họ tên / số điện thoại (LIKE, không phân biệt hoa thường) |
| `page` | int | 1 | Số trang (>= 1). Sai → **422** |
| `page_size` | int | 20 | Số bản ghi/trang (1..100). Sai → **422** |

Response **200**:

```json
{
  "items": [
    {
      "id": 28,
      "email": "demo-lock@test.com",
      "full_name": "Demo Lock",
      "phone": null,
      "role": "candidate",
      "avatar_url": null,
      "is_active": false,
      "is_verified": false,
      "locked_reason": "Vi pham noi quy",
      "created_at": "2026-11-15T10:00:00",
      "updated_at": "2026-11-15T10:05:00"
    }
  ],
  "total": 23,
  "page": 1,
  "page_size": 20,
  "total_pages": 2
}

```

> Response **KHÔNG bao giờ** chứa trường `password`.

Ví dụ:

```bash
curl "http://127.0.0.1:8000/api/users?role=employer&is_active=false&keyword=nguyen&page=1&page_size=10" \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

---

## 3. POST /api/users/{user_id}/lock — khoá tài khoản

Body:

```json
{ "locked_reason": "Vi phạm nội quy diễn đàn" }
```

- `locked_reason` bắt buộc, 1–500 ký tự (thiếu/rỗng → **422**).
- Thành công **200**: `is_active=false`, `locked_reason` được lưu.

**Hệ quả của việc khoá** ("bị khoá không đăng nhập được"):

| Hành động | Kết quả |
|-----------|---------|
| `POST /api/auth/login` | **403** "Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên." |
| API cần token (`get_current_user`, `role_required`) | **403** ngay cả khi JWT còn hạn |

Lỗi:

| Case | Mã |
|------|----|
| Không tìm thấy user | 404 |
| Đã khoá rồi | 400 |
| Admin tự khoá chính mình | 400 |

---

## 4. POST /api/users/{user_id}/unlock — mở khoá

- Thành công **200**: `is_active=true`, `locked_reason=null` → đăng nhập lại bình thường.
- Chưa bị khoá → **400**; user không tồn tại → **404**.

---

## 5. Luồng xử lý

```
GET /api/users?role=&is_active=&keyword=&page=&page_size=
        │
        ▼
[1] role_required("admin")      — thiếu token → 401, sai role → 403, bị khoá → 403
        │
        ▼
[2] validate role (nếu có)      — sai → 400
        │
        ▼
[3] crud/user.py: get_users()   — WHERE role / is_active / LIKE(email, full_name, phone)
        │                          ORDER BY id DESC, OFFSET/LIMIT, COUNT(*) total
        ▼
[4] UserListOut                 — {items, total, page, page_size, total_pages}

POST /api/users/{id}/lock
        │
        ▼
[1] role_required("admin") → 404 nếu thiếu user → 400 nếu tự khoá mình / đã khoá
        │
        ▼
[2] crud/user.py: lock_user()   — is_active=False, locked_reason=<body> → commit
```

---

## 6. File tạo / sửa

| File | Thay đổi |
|------|----------|
| `app/routers/users.py` | Mới — 3 endpoint: GET /, POST /{id}/lock, POST /{id}/unlock |
| `app/crud/user.py` | Thêm `get_users` (lọc + tìm + phân trang), `lock_user`, `unlock_user` |
| `app/schemas/user.py` | Mới — `UserOut`, `UserListOut`, `UserLockIn` |
| `app/models/user.py` | Thêm cột `locked_reason` |
| `app/schemas/__init__.py` | Export schema user |
| `app/main.py` | `include_router(users.router, prefix="/api")` |
| `sql/init.sql` | Thêm `locked_reason VARCHAR(500)` vào bảng `users` |

> Cột `locked_reason` đã có sẵn trên DB (`VARCHAR(500)`); model giờ map khớp lại.

---

## 7. Kết quả test tự động (22/22 PASS)

```
Phan 1 (phan quyen + loc + tim + phan trang):
[OK]  khong token -> 401
[OK]  candidate token -> 403
[OK]  admin -> 200, co locked_reason, KHONG co password
[OK]  role=employer -> chi employer
[OK]  is_active=false -> chi user bi khoa
[OK]  keyword=nguyen -> tim email/full_name/phone
[OK]  page=2&page_size=5 -> items=5, total_pages dung
[OK]  role=superadmin -> 400
[OK]  page=0 -> 422

Phan 2 (khoa / mo khoa):
[OK]  lock kem ly do -> is_active=False, locked_reason luu duoc
[OK]  login khi bi khoa -> 403 "Tai khoan da bi khoa..."
[OK]  token cu cua user bi khoa -> 403
[OK]  lock lan 2 -> 400
[OK]  unlock -> is_active=True, locked_reason=None
[OK]  unlock lan 2 -> 400
[OK]  lock user ko ton tai -> 404
[OK]  login sau mo khoa -> 200
[OK]  lock khong co ly do -> 422
[OK]  admin tu khoa chinh minh -> 400 (admin van hoat dong)
```

---

## 8. Lỗi hay gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|------------|----------|
| `401` khi gọi `/api/users` | Thiếu token hoặc token hết hạn | `POST /api/auth/login` lấy token mới |
| `403` dù đúng role admin | Tài khoản admin bị khoá (`is_active=False`) | Admin khác mở khoá, hoặc sửa DB |
| `403` khi gọi bằng token candidate | Endpoint này chỉ dành cho `role=admin` | Dùng token admin |
| `400` role không hợp lệ | `role` chỉ nhận `candidate/employer/admin` | Truyền đúng giá trị |
| `400` "Đã bị khoá trước đó" | User đã bị khoá | Gọi unlock trước khi lock lại |
| `400` "Không thể khoá chính tài khoản của mình" | Admin khoá chính mình | Không cho phép — tránh tự khoá mình |