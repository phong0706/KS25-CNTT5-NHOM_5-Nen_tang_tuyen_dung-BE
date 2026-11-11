"""
Script seed dữ liệu cho các bảng catalog (Industry, Location, Skill).

Cách chạy:
    python seed_catalog.py

Lưu ý: Chạy sau khi đã tạo bảng bằng SQL hoặc Base.metadata.create_all()
"""
from sqlalchemy.orm import Session
from app.db.session import engine, Base
from app.models.catalog import Industry, Location, Skill

# Dữ liệu 15 ngành nghề
INDUSTRIES = [
    "Công nghệ thông tin",
    "Kinh doanh / Bán hàng",
    "Marketing / Truyền thông",
    "Tài chính / Kế toán",
    "Nhân sự / Hành chính",
    "Giáo dục / Đào tạo",
    "Y tế / Chăm sóc sức khỏe",
    "Xây dựng / Kiến trúc",
    "Sản xuất / Vận hành",
    "Du lịch / Khách sạn",
    "Logistics / Vận tải",
    "Luật / Pháp lý",
    "Thiết kế / Nghệ thuật",
    "Bất động sản",
    "Nông nghiệp / Lâm nghiệp"
]

# Dữ liệu 10 địa điểm
LOCATIONS = [
    "Hà Nội",
    "Hồ Chí Minh",
    "Đà Nẵng",
    "Hải Phòng",
    "Cần Thơ",
    "Bình Dương",
    "Đồng Nai",
    "Khánh Hòa",
    "Lâm Đồng",
    "Quảng Ninh"
]

# Dữ liệu 40 kỹ năng
SKILLS = [
    # Kỹ năng lập trình & IT
    "Python", "Java", "JavaScript", "React", "Node.js",
    "Angular", "Vue.js", "PHP", "C#", ".NET",
    "SQL", "MySQL", "PostgreSQL", "MongoDB", "Docker",
    "Kubernetes", "AWS", "Azure", "DevOps", "Git",
    
    # Kỹ năng kinh doanh & marketing
    "Sales", "Marketing Digital", "SEO/SEM", "Content Marketing",
    "Social Media", "Google Ads", "Facebook Ads",
    
    # Kỹ năng mềm & quản lý
    "Giao tiếp", "Làm việc nhóm", "Quản lý dự án",
    "Lãnh đạo", "Giải quyết vấn đề", "Tư duy phản biện",
    
    # Kỹ năng chuyên môn khác
    "Kế toán", "Tài chính", "Photoshop", "Illustrator",
    "UI/UX Design", "AutoCAD", "Tiếng Anh"
]


def seed_data():
    """Seed dữ liệu vào database."""
    
    # Tạo tất cả các bảng nếu chưa có
    Base.metadata.create_all(bind=engine)
    
    with Session(engine) as session:
        print("🌱 Bắt đầu seed dữ liệu...")
        
        # Seed Industries
        print("\n📊 Seeding Industries...")
        for name in INDUSTRIES:
            existing = session.query(Industry).filter_by(name=name).first()
            if not existing:
                industry = Industry(name=name, status="active")
                session.add(industry)
        session.commit()
        industry_count = session.query(Industry).count()
        print(f"   ✓ Tổng số ngành nghề: {industry_count}")
        
        # Seed Locations
        print("\n📍 Seeding Locations...")
        for name in LOCATIONS:
            existing = session.query(Location).filter_by(name=name).first()
            if not existing:
                location = Location(name=name, status="active")
                session.add(location)
        session.commit()
        location_count = session.query(Location).count()
        print(f"   ✓ Tổng số địa điểm: {location_count}")
        
        # Seed Skills
        print("\n💼 Seeding Skills...")
        for name in SKILLS:
            existing = session.query(Skill).filter_by(name=name).first()
            if not existing:
                skill = Skill(name=name, status="active")
                session.add(skill)
        session.commit()
        skill_count = session.query(Skill).count()
        print(f"   ✓ Tổng số kỹ năng: {skill_count}")
        
        print("\n Seed dữ liệu hoàn tất!")
        print(f"\nTổng kết:")
        print(f"  - Industries: {industry_count}")
        print(f"  - Locations: {location_count}")
        print(f"  - Skills: {skill_count}")


if __name__ == "__main__":
    seed_data()
