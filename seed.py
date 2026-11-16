import sys
import os

# đường dẫn thư mục BE vào hệ thống để Python nhận diện được app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.catalog import Industry, Location, Skill

def run_seed():
    db = SessionLocal()
    try:
        print("Đang tiến hành seed dữ liệu...")

        # 1. Seed 15 Ngành nghề (Industries)
        industries = [
            "Công nghệ thông tin", "Kinh doanh / Bán hàng", "Marketing / Truyền thông", 
            "Tài chính / Kế toán", "Nhân sự / Hành chính", "Giáo dục / Đào tạo", 
            "Y tế / Chăm sóc sức khỏe", "Xây dựng / Kiến trúc", "Sản xuất / Vận hành", 
            "Du lịch / Khách sạn", "Logistics / Vận tải", "Luật / Pháp lý", 
            "Thiết kế / Nghệ thuật", "Bất động sản", "Nông nghiệp / Lâm nghiệp"
        ]
        for name in industries:
            exists = db.query(Industry).filter_by(name=name).first()
            if not exists:
                db.add(Industry(name=name, status="active"))
        print(f"Đã kiểm tra và seed xong {len(industries)} ngành nghề.")

        # 2. Seed 10 Địa điểm (Locations)
        locations = [
            "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", 
            "Bình Dương", "Đồng Nai", "Khánh Hòa", "Lâm Đồng", "Quảng Ninh"
        ]
        for name in locations:
            exists = db.query(Location).filter_by(name=name).first()
            if not exists:
                db.add(Location(name=name, status="active"))
        print(f"Đã kiểm tra và seed xong {len(locations)} địa điểm.")

        # 3. Seed 40 Kỹ năng (Skills)
        skills = [
            # Kỹ năng lập trình & IT (20)
            "Python", "Java", "JavaScript", "React", "Node.js",
            "Angular", "Vue.js", "PHP", "C#", ".NET",
            "SQL", "MySQL", "PostgreSQL", "MongoDB", "Docker",
            "Kubernetes", "AWS", "Azure", "DevOps", "Git",
            
            # Kỹ năng kinh doanh & marketing (7)
            "Sales", "Marketing Digital", "SEO/SEM", "Content Marketing",
            "Social Media", "Google Ads", "Facebook Ads",
            
            # Kỹ năng mềm & quản lý (6)
            "Giao tiếp", "Làm việc nhóm", "Quản lý dự án",
            "Lãnh đạo", "Giải quyết vấn đề", "Tư duy phản biện",
            
            # Kỹ năng chuyên môn khác (7)
            "Kế toán", "Tài chính", "Photoshop", "Illustrator",
            "UI/UX Design", "AutoCAD", "Tiếng Anh"
        ]
        for name in skills:
            exists = db.query(Skill).filter_by(name=name).first()
            if not exists:
                db.add(Skill(name=name, status="active"))
        print(f"Đã kiểm tra và seed xong {len(skills)} kỹ năng.")

        # Lưu thay đổi vào cơ sở dữ liệu
        db.commit()
        print("Seed dữ liệu thành công hoàn toàn!")

    except Exception as e:
        db.rollback()
        print(f"Lỗi xảy ra khi seed dữ liệu: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()