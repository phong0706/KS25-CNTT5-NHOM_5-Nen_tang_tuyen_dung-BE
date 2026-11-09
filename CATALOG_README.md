# Hướng dẫn sử dụng Models & Seed Data

## 📋 Tổng quan

Dự án đã có các models sau:
- **Industry** (Ngành nghề): tên duy nhất, trạng thái
- **Location** (Địa điểm): tên duy nhất, trạng thái  
- **Skill** (Kỹ năng): tên duy nhất, trạng thái
- **Report** (Báo cáo vi phạm): người báo cáo, tin, lý do, trạng thái (PENDING/RESOLVED/REJECTED), kết quả xử lý

## 🗂️ Cấu trúc Files

```
BE/
├── app/
│   ├── models/
│   │   ├── catalog.py          # Models: Industry, Location, Skill
│   │   ├── report.py           # Model: Report + ReportStatus enum
│   │   └── __init__.py         # Import tất cả models
│   └── schemas/
│       ├── catalog_schema.py   # Schemas cho catalog (CRUD)
│       ├── report_schema.py    # Schemas cho report (CRUD)
│       └── __init__.py
├── sql/
│   ├── init.sql                      # Tạo database + users
│   └── catalog_and_reports.sql       # Tạo bảng + seed data ⭐ MỚI
└── seed_catalog.py                   # Python seeder ⭐ MỚI
```

## 🚀 Cách sử dụng

### Phương án 1: Sử dụng SQL Script (Khuyến nghị)

1. Mở **MySQL Workbench**
2. File > Open SQL Script > chọn `sql/catalog_and_reports.sql`
3. Bấm nút ⚡ Execute
4. Refresh SCHEMAS để xem kết quả

**File này sẽ:**
- ✅ Tạo 4 bảng: `industries`, `locations`, `skills`, `reports`
- ✅ Seed 15 ngành nghề
- ✅ Seed 10 địa điểm  
- ✅ Seed 40 kỹ năng
- ✅ Hiển thị tổng kết

### Phương án 2: Sử dụng Python Seeder

```bash
# Trong thư mục BE, chạy:
python seed_catalog.py
```

**Output mẫu:**
```
🌱 Bắt đầu seed dữ liệu...

📊 Seeding Industries...
   ✓ Tổng số ngành nghề: 15

📍 Seeding Locations...
   ✓ Tổng số địa điểm: 10

💼 Seeding Skills...
   ✓ Tổng số kỹ năng: 40

✅ Seed dữ liệu hoàn tất!
```

## 📊 Dữ liệu đã seed

### 15 Ngành nghề (Industries)
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

### 10 Địa điểm (Locations)
1. Hà Nội
2. Hồ Chí Minh
3. Đà Nẵng
4. Hải Phòng
5. Cần Thơ
6. Bình Dương
7. Đồng Nai
8. Khánh Hòa
9. Lâm Đồng
10. Quảng Ninh

### 40 Kỹ năng (Skills)
**Lập trình & IT:** Python, Java, JavaScript, React, Node.js, Angular, Vue.js, PHP, C#, .NET, SQL, MySQL, PostgreSQL, MongoDB, Docker, Kubernetes, AWS, Azure, DevOps, Git

**Kinh doanh & Marketing:** Sales, Marketing Digital, SEO/SEM, Content Marketing, Social Media, Google Ads, Facebook Ads

**Kỹ năng mềm:** Giao tiếp, Làm việc nhóm, Quản lý dự án, Lãnh đạo, Giải quyết vấn đề, Tư duy phản biện

**Chuyên môn khác:** Kế toán, Tài chính, Photoshop, Illustrator, UI/UX Design, AutoCAD, Tiếng Anh

## 🔍 Kiểm tra dữ liệu

```sql
-- Xem tất cả ngành nghề
SELECT * FROM industries;

-- Xem tất cả địa điểm
SELECT * FROM locations;

-- Xem tất cả kỹ năng
SELECT * FROM skills;

-- Xem tổng số bản ghi
SELECT 'Industries' as Table_Name, COUNT(*) as Total FROM industries
UNION ALL SELECT 'Locations', COUNT(*) FROM locations
UNION ALL SELECT 'Skills', COUNT(*) FROM skills;
```

## 📝 Sử dụng trong code

### Ví dụ CRUD cho Industry

```python
from sqlalchemy.orm import Session
from app.models.catalog import Industry
from app.schemas.catalog_schema import CatalogCreate, CatalogUpdate

# CREATE
def create_industry(db: Session, data: CatalogCreate):
    industry = Industry(**data.model_dump())
    db.add(industry)
    db.commit()
    db.refresh(industry)
    return industry

# READ
def get_all_industries(db: Session):
    return db.query(Industry).filter_by(status="active").all()

# UPDATE
def update_industry(db: Session, industry_id: int, data: CatalogUpdate):
    industry = db.query(Industry).filter_by(id=industry_id).first()
    if industry:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(industry, key, value)
        db.commit()
        db.refresh(industry)
    return industry

# DELETE (soft delete - đổi status)
def delete_industry(db: Session, industry_id: int):
    industry = db.query(Industry).filter_by(id=industry_id).first()
    if industry:
        industry.status = "inactive"
        db.commit()
    return industry
```

### Ví dụ CRUD cho Report

```python
from app.models.report import Report, ReportStatus
from app.schemas.report_schema import ReportCreate, ReportUpdate

# CREATE - User tạo báo cáo vi phạm
def create_report(db: Session, user_id: int, data: ReportCreate):
    report = Report(
        user_id=user_id,
        post_id=data.post_id,
        reason=data.reason,
        status=ReportStatus.PENDING
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report

# UPDATE - Admin xử lý báo cáo
def resolve_report(db: Session, report_id: int, data: ReportUpdate):
    report = db.query(Report).filter_by(id=report_id).first()
    if report:
        report.status = data.status
        report.resolution_result = data.resolution_result
        db.commit()
        db.refresh(report)
    return report

# READ - Lấy tất cả báo cáo đang chờ xử lý
def get_pending_reports(db: Session):
    return db.query(Report).filter_by(status=ReportStatus.PENDING).all()
```

## 🎯 Lưu ý

- Tất cả các bảng catalog có **unique constraint** trên trường `name`
- Chạy lại script SQL nhiều lần không bị lỗi (sử dụng `ON DUPLICATE KEY UPDATE`)
- Model Report có enum `ReportStatus` với 3 giá trị: PENDING, RESOLVED, REJECTED
- Trường `resolution_result` trong Report có thể NULL (admin điền khi xử lý)
