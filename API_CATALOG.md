# API Danh Mục (Catalog APIs)

## 📋 Tổng quan

API CRUD đầy đủ cho 3 loại danh mục:
- **Industries** (Ngành nghề) - `/api/industries`
- **Locations** (Địa điểm) - `/api/locations`
- **Skills** (Kỹ năng) - `/api/skills`

## ✨ Tính năng

✅ **Thêm/Sửa/Ẩn danh mục** (soft delete)  
✅ **Tên duy nhất** - không cho phép trùng lặp  
✅ **Bảo vệ dữ liệu** - không xóa khi đang được sử dụng  
✅ **API dropdown** - lấy danh sách active cho các module khác  
✅ **Lọc theo status** - active/inactive/all  

---

## 🔗 API Endpoints

### Cấu trúc chung (giống nhau cho cả 3 loại)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/{type}?status=active` | Danh sách (dropdown) |
| GET | `/api/{type}/{id}` | Chi tiết 1 item |
| POST | `/api/{type}` | Tạo mới |
| PUT | `/api/{type}/{id}` | Cập nhật |
| DELETE | `/api/{type}/{id}` | Ẩn (soft delete) |

*Thay `{type}` = `industries` hoặc `locations` hoặc `skills`*

---

## 📖 Chi tiết API

### 1. GET - Lấy danh sách (Dropdown)

```http
GET /api/industries?status=active
GET /api/locations?status=active
GET /api/skills?status=active
```

**Query Parameters:**
- `status` (optional): 
  - `active` (default) - lấy danh mục đang hoạt động
  - `inactive` - lấy danh mục đã ẩn
  - không truyền - lấy tất cả

**Response 200:**
```json
[
  {
    "id": 1,
    "name": "Công nghệ thông tin",
    "status": "active"
  },
  {
    "id": 2,
    "name": "Kinh doanh / Bán hàng",
    "status": "active"
  }
]
```

**Use case:** Dùng cho dropdown trong form tạo công việc, hồ sơ ứng viên...

---

### 2. GET - Chi tiết 1 danh mục

```http
GET /api/industries/1
```

**Response 200:**
```json
{
  "id": 1,
  "name": "Công nghệ thông tin",
  "status": "active"
}
```

**Response 404:**
```json
{
  "detail": "Không tìm thấy ngành nghề id=999"
}
```

---

### 3. POST - Tạo mới

```http
POST /api/industries
Content-Type: application/json

{
  "name": "Nông nghiệp công nghệ cao",
  "status": "active"
}
```

**Request Body:**
- `name` (required, string, 1-255 chars) - Tên danh mục
- `status` (optional, string, default="active") - Trạng thái

**Response 201:**
```json
{
  "id": 16,
  "name": "Nông nghiệp công nghệ cao",
  "status": "active"
}
```

**Response 400 - Tên trùng:**
```json
{
  "detail": "Tên 'Công nghệ thông tin' đã tồn tại"
}
```

---

### 4. PUT - Cập nhật

```http
PUT /api/industries/1
Content-Type: application/json

{
  "name": "Công nghệ thông tin & Viễn thông",
  "status": "active"
}
```

**Request Body:** (tất cả optional)
- `name` (string) - Tên mới
- `status` (string) - Trạng thái mới

**Response 200:**
```json
{
  "id": 1,
  "name": "Công nghệ thông tin & Viễn thông",
  "status": "active"
}
```

**Response 400 - Tên trùng:**
```json
{
  "detail": "Tên 'Marketing / Truyền thông' đã tồn tại"
}
```

---

### 5. DELETE - Ẩn danh mục (Soft Delete)

```http
DELETE /api/industries/1
```

**Response 200:**
```json
{
  "id": 1,
  "name": "Công nghệ thông tin",
  "status": "inactive"
}
```

**Response 400 - Đang được sử dụng:**
```json
{
  "detail": "Không thể xóa ngành nghề đang được sử dụng"
}
```

**Lưu ý:** 
- Không xóa hẳn khỏi DB, chỉ đổi `status="inactive"`
- Danh mục inactive không hiện trong dropdown
- Bảo vệ dữ liệu: không xóa nếu đang có job/user sử dụng

---

## 🎯 Ví dụ sử dụng

### Dropdown cho form
```javascript
// Lấy danh sách cho dropdown
const industries = await fetch('/api/industries?status=active').then(r => r.json());
const locations = await fetch('/api/locations?status=active').then(r => r.json());
const skills = await fetch('/api/skills?status=active').then(r => r.json());

// Hiển thị trong select/dropdown
<select>
  {industries.map(item => (
    <option value={item.id}>{item.name}</option>
  ))}
</select>
```

### Admin thêm danh mục mới
```javascript
await fetch('/api/skills', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'AI/Machine Learning',
    status: 'active'
  })
});
```

### Admin ẩn danh mục
```javascript
await fetch('/api/industries/10', {
  method: 'DELETE'
});
```

---

## 🔒 Business Rules

1. **Tên duy nhất**: Không cho phép 2 danh mục cùng tên
2. **Soft delete**: DELETE chỉ đổi status, không xóa khỏi DB
3. **Bảo vệ dữ liệu**: Không xóa nếu đang được sử dụng (TODO: implement khi có bảng liên quan)

---

## 🧪 Testing

Mở Swagger UI: http://127.0.0.1:8000/docs

Test flow:
1. GET `/api/industries?status=active` - xem danh sách
2. POST `/api/industries` - tạo mới "Test Industry"
3. POST `/api/industries` - tạo trùng tên -> lỗi 400
4. PUT `/api/industries/{id}` - đổi tên
5. DELETE `/api/industries/{id}` - ẩn
6. GET `/api/industries?status=active` - không còn thấy

---

## 📁 Files liên quan

- Models: `app/models/catalog.py`
- Schemas: `app/schemas/catalog_schema.py`
- CRUD: `app/crud/catalog.py`
- Routers: `app/routers/industries.py`, `locations.py`, `skills.py`
- Main: `app/main.py` (đã include routers)
