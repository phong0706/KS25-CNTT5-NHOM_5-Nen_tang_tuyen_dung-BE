# 📂 Tổng Quan Cấu Trúc Dự Án

## ✅ Đã hoàn thành

### 1️⃣ Models (app/models/)

#### **catalog.py** - Các danh mục hệ thống
```python
class Industry(Base):
    """Ngành nghề"""
    __tablename__ = "industries"
    - id: int (PK)
    - name: str (unique, indexed)
    - status: str (default="active")

class Location(Base):
    """Địa điểm"""
    __tablename__ = "locations"
    - id: int (PK)
    - name: str (unique, indexed)
    - status: str (default="active")

class Skill(Base):
    """Kỹ năng"""
    __tablename__ = "skills"
    - id: int (PK)
    - name: str (unique, indexed)
    - status: str (default="active")
```

#### **report.py** - Báo cáo vi phạm
```python
class ReportStatus(Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

class Report(Base):
    """Báo cáo vi phạm bài đăng"""
    __tablename__ = "reports"
    - id: int (PK)
    - user_id: int (người báo cáo)
    - post_id: int (tin bị báo cáo)
    - reason: Text (lý do báo cáo)
    - status: ReportStatus (trạng thái xử lý)
    - resolution_result: Text | None (kết quả xử lý)
```

### 2️⃣ Schemas (app/schemas/)

#### **catalog_schema.py**
- `CatalogBase` - Base schema với name, status
- `CatalogCreate` - Tạo mới (name, status)
- `CatalogUpdate` - Cập nhật (các trường optional)
- `CatalogResponse` - Response có thêm id

#### **report_schema.py**
- `ReportCreate` - Tạo báo cáo (post_id, reason)
- `ReportUpdate` - Admin cập nhật (status, resolution_result)
- `ReportResponse` - Response đầy đủ thông tin

### 3️⃣ SQL Scripts (sql/)

#### **catalog_and_reports.sql** ⭐ MỚI
Tạo bảng + seed dữ liệu:
- ✅ Tạo 4 bảng: industries, locations, skills, reports
- ✅ Seed 15 ngành nghề
- ✅ Seed 10 địa điểm
- ✅ Seed 40 kỹ năng
- ✅ Query kiểm tra tổng kết

**Cách chạy:**
```bash
# MySQL Workbench: File > Open SQL Script > Execute
```

### 4️⃣ Python Seeders

#### **seed.py** (đã cập nhật)
Script seed dữ liệu Python, đồng nhất với SQL:
```bash
python seed.py
```

**Output:**
```
Đang tiến hành seed dữ liệu...
Đã kiểm tra và seed xong 15 ngành nghề.
Đã kiểm tra và seed xong 10 địa điểm.
Đã kiểm tra và seed xong 40 kỹ năng.
Seed dữ liệu thành công hoàn toàn!
```

## 📊 Dữ liệu Seed

### 15 Ngành nghề
1. Công nghệ thông tin
2. Kinh doanh / Bán hàng
3. Marketing / Truyền thông
4. Tài chính / Kế toán
5. Nhân sự / Hành chính
6. Giáo dục / Đào tạo
7. Y tế / Chăm sóc sức khỏe
8. Xây dựng / Kiến trúc
9. Sản xuất / Vận hành
10. Du lịch / Khách sạn
11. Logistics / Vận tải
12. Luật / Pháp lý
13. Thiết kế / Nghệ thuật
14. Bất động sản
15. Nông nghiệp / Lâm nghiệp

### 10 Địa điểm
Hà Nội, Hồ Chí Minh, Đà Nẵng, Hải Phòng, Cần Thơ, Bình Dương, Đồng Nai, Khánh Hòa, Lâm Đồng, Quảng Ninh

### 40 Kỹ năng
**IT (20):** Python, Java, JavaScript, React, Node.js, Angular, Vue.js, PHP, C#, .NET, SQL, MySQL, PostgreSQL, MongoDB, Docker, Kubernetes, AWS, Azure, DevOps, Git

**Business (7):** Sales, Marketing Digital, SEO/SEM, Content Marketing, Social Media, Google Ads, Facebook Ads

**Soft Skills (6):** Giao tiếp, Làm việc nhóm, Quản lý dự án, Lãnh đạo, Giải quyết vấn đề, Tư duy phản biện

**Other (7):** Kế toán, Tài chính, Photoshop, Illustrator, UI/UX Design, AutoCAD, Tiếng Anh

## 🔧 Sử dụng

### Tạo bảng và seed dữ liệu

**Phương án 1: SQL Script (Khuyến nghị)**
```bash
# Mở MySQL Workbench
# File > Open SQL Script > chọn sql/catalog_and_reports.sql
# Execute (⚡)
```

**Phương án 2: Python**
```bash
cd BE
python seed.py
```

### Truy vấn dữ liệu

```sql
-- Xem tất cả ngành nghề active
SELECT * FROM industries WHERE status = 'active';

-- Xem tất cả kỹ năng
SELECT * FROM skills ORDER BY name;

-- Xem báo cáo đang chờ xử lý
SELECT * FROM reports WHERE status = 'PENDING';

-- Tổng kết
SELECT 'Industries' as table_name, COUNT(*) as total FROM industries
UNION ALL SELECT 'Locations', COUNT(*) FROM locations
UNION ALL SELECT 'Skills', COUNT(*) FROM skills;
```

## 📝 Files đã tạo/cập nhật

```
BE/
├── app/
│   ├── models/
│   │   ├── catalog.py          ✅ (Industry, Location, Skill)
│   │   ├── report.py           ✅ (Report, ReportStatus)
│   │   └── __init__.py         ✅ (imports đầy đủ)
│   └── schemas/
│       ├── catalog_schema.py   ✅
│       ├── report_schema.py    ✅
│       └── __init__.py         ✅
├── sql/
│   ├── init.sql
│   └── catalog_and_reports.sql ⭐ MỚI (5.4 KB)
├── seed.py                     ✅ ĐÃ CẬP NHẬT
├── seed_catalog.py             ⭐ MỚI (alternative seeder)
├── CATALOG_README.md           ⭐ MỚI (hướng dẫn chi tiết)
└── README.md
```

## ✨ Tính năng chính

✅ **Unique constraint** trên tên (không trùng lặp)  
✅ **Indexed** trên name và status (tìm kiếm nhanh)  
✅ **Soft delete** (đổi status thay vì xóa)  
✅ **Enum status** cho Report (type-safe)  
✅ **ON DUPLICATE KEY UPDATE** (chạy lại SQL không lỗi)  
✅ **UTF-8 support** (tiếng Việt không bị lỗi)  

## 🎯 Các bước tiếp theo (nếu cần)

1. Tạo CRUD endpoints cho các models
2. Tạo middleware/permissions cho Report (chỉ admin xử lý)
3. Tạo relationship giữa Report và User/Post
4. Tạo API pagination cho danh sách
5. Tạo API search/filter

Xem chi tiết trong **CATALOG_README.md**! 🚀
