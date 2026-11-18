# API theo dõi công ty

## Quy ước

- Tất cả endpoint thao tác follow yêu cầu JWT Bearer và role `candidate`.
- Công ty hợp lệ để theo dõi phải có `status = VERIFIED` và `is_draft = false`.
- Theo dõi và bỏ theo dõi đều **idempotent**. Gọi lặp trả `200`, không tạo bản ghi trùng; bỏ theo dõi công ty chưa theo dõi cũng trả `200`.
- `follower_count` được tính từ `company_follows`, không lưu bộ đếm denormalized nên không có bộ đếm cần đồng bộ.
- Phân trang lỗi tham số trả `422` theo chuẩn validation FastAPI; các lỗi nghiệp vụ/auth trả `detail` tiếng Việt.

## Endpoints

### `POST /api/companies/{company_id}/follow`

Theo dõi công ty. Request body không cần.

```json
{
  "success": true,
  "data": { "company_id": 42, "is_following": true },
  "message": "Đã theo dõi công ty."
}
```

### `DELETE /api/companies/{company_id}/follow`

Bỏ theo dõi; idempotent cả khi chưa theo dõi.

```json
{
  "success": true,
  "data": { "company_id": 42, "is_following": false },
  "message": "Đã bỏ theo dõi công ty."
}
```

### `GET /api/candidates/me/followed-companies?page=1&limit=10&keyword=tech`

`page >= 1`, `1 <= limit <= 50`, tìm kiếm tùy chọn theo tên công ty. Danh sách sắp xếp theo thời gian follow mới nhất. Số tin đang tuyển được tổng hợp bằng subquery, tránh N+1.

```json
{
  "success": true,
  "data": {
    "items": [{
      "id": 42,
      "name": "Công ty ABC",
      "logo": "/uploads/abc.png",
      "industry": "Công nghệ thông tin",
      "location": "Hà Nội",
      "active_job_count": 3,
      "followed_at": "2026-11-18T12:00:00"
    }]
  },
  "message": "Đã lấy danh sách công ty đang theo dõi.",
  "meta": { "page": 1, "limit": 10, "total": 1 }
}
```

### `GET /api/companies/{company_id}/follow-status`

Ứng viên lấy trạng thái nút theo dõi và tổng follower.

```json
{
  "success": true,
  "data": { "company_id": 42, "is_following": true, "follower_count": 18 },
  "message": "Đã lấy trạng thái theo dõi."
}
```

Chi tiết công ty `GET /api/companies/{slug}` cũng trả thêm `isFollowing` và `followerCount`; khách truy cập/role khác nhận `isFollowing: false`.

## Mã lỗi

| HTTP | Trường hợp | Ví dụ `detail` |
|---|---|---|
| 400 | Công ty chưa hoạt động/được xác minh | `Chỉ có thể theo dõi công ty đang hoạt động.` |
| 401 | Thiếu/sai JWT | `Token không hợp lệ hoặc đã hết hạn` |
| 403 | Không phải ứng viên hoặc tài khoản bị khóa | `Chức năng này chỉ dành cho: candidate` |
| 404 | Công ty không tồn tại | `Công ty không tồn tại.` |
| 409 | Không dùng cho thao tác follow; duplicate được xử lý idempotent | — |
| 422 | Query/path sai định dạng hoặc ngoài giới hạn | FastAPI validation response |
| 500 | Lỗi DB/hệ thống | Lỗi máy chủ |

## Thông báo tin mới

Khi tin chuyển từ trạng thái khác sang `published` qua API tạo tin hoặc thao tác mở lại, sau khi transaction đăng tin commit, FastAPI `BackgroundTasks` gửi notification trong ứng dụng theo lô 500. Draft/pending và chỉnh sửa tin đang published không phát sự kiện. `dedupe_key = followed-company-job:{job_id}` kết hợp unique `(user_id, dedupe_key)` ngăn gửi trùng khi retry. Mỗi lô retry tối đa 3 lần; lỗi cuối được ghi log và ném lại để runtime ghi nhận.

Payload notification giữ `jobId`, `companyId`, tên công ty, tiêu đề, địa điểm và lương; đường dẫn là `/pages/job-detail.html?id={job_id}`. `BackgroundTasks` là cơ chế nội bộ, không bền vững qua sự cố tiến trình; khi triển khai nhiều worker/đòi hỏi bảo đảm giao nhận, nên chuyển sang transactional outbox + Redis/BullMQ hoặc RabbitMQ. Email/push chưa bật vì hiện chưa có cấu hình ưu tiên/kênh người dùng; notification in-app luôn được tạo.
