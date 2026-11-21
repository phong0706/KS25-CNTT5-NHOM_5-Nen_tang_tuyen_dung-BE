# API Theo dõi công ty

Các endpoint sau dành cho tài khoản ứng viên và yêu cầu Bearer token.

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/api/candidate/followed-companies/{company_id}` | Theo dõi công ty (idempotent) |
| GET | `/api/candidate/followed-companies` | Danh sách công ty đang theo dõi |
| DELETE | `/api/candidate/followed-companies/{company_id}` | Bỏ theo dõi (idempotent) |

## Theo dõi

```http
POST /api/candidate/followed-companies/12
Authorization: Bearer <token>
```

```json
{
  "company_id": 12,
  "is_following": true,
  "message": "Đã theo dõi công ty"
}
```

Công ty không tồn tại, đang ẩn hoặc còn ở trạng thái nháp trả về `404`.

## Danh sách công ty

```http
GET /api/candidate/followed-companies?q=tech&page=1&page_size=10
Authorization: Bearer <token>
```

`q`, `page` và `page_size` là tùy chọn. Kết quả chỉ chứa công ty đang hiển thị công khai.

```json
{
  "items": [
    {
      "id": 12,
      "name": "Công ty công nghệ",
      "slug": "cong-ty-cong-nghe",
      "logo": "/uploads/logos/company.png",
      "tagline": "Cùng phát triển",
      "followed_at": "2026-11-20T13:00:00",
      "active_jobs_count": 3
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

Khi tin tuyển dụng mới lần đầu được đăng, hệ thống tạo thông báo `company_new_job`
cho từng người theo dõi. Mở lại tin đã từng đăng không tạo thông báo tin mới.

## Database

Chạy migration `sql/migrations/20261120_company_follows.sql` trên database hiện tại.
Database mới có thể tạo bảng tự động qua `Base.metadata.create_all()`.
