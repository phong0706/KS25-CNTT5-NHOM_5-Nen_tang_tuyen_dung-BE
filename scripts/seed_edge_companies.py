import sys
from pathlib import Path
from sqlalchemy import select

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app.db.session import SessionLocal
from app.models.company import Company, CompanyStatus
from app.services.public_company_rules import normalize_search_text

EDGE_COMPANIES = [
    {
        "slug": "trung-tam-ai-sao-phuong-nam",
        "name": "Trung tâm Nghiên cứu và Phát triển Hạ tầng Trí tuệ Nhân tạo Sao Phương Nam",
        "tagline": "Nghiên cứu mô hình ngôn ngữ tiếng Việt và thị giác máy tính",
        "is_verified": True,
        "is_visible": True,
        "status": CompanyStatus.VERIFIED,
        "size_range": "501-1000",
        "industry_id": 3,
        "location_id": 1,
    },
    {
        "slug": "edge-unbroken-word-tech",
        "name": "Tập đoàn SiêuCôngNghệA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6 Toàn Cầu",
        "tagline": "Chống tràn từ siêu dài không khoảng trắng",
        "is_verified": True,
        "is_visible": True,
        "status": CompanyStatus.VERIFIED,
        "size_range": "201-500",
        "industry_id": 1,
        "location_id": 2,
    },
    {
        "slug": "edge-emoji-special-corp",
        "name": "🚀 Tech Corp & Co. #1 ★★★ (AI/ML) 🌐",
        "tagline": "Doanh nghiệp đặc biệt không ngành không địa điểm",
        "is_verified": False,
        "is_visible": True,
        "status": CompanyStatus.VERIFIED,
        "size_range": "1-50",
        "industry_id": None,
        "location_id": None,
    },
    {
        "slug": "edge-unverified-standard",
        "name": "Khởi nghiệp Công nghệ Xanh Lam",
        "tagline": "Doanh nghiệp chưa xác minh đối chiếu với đã xác minh",
        "is_verified": False,
        "is_visible": True,
        "status": CompanyStatus.VERIFIED,
        "size_range": "51-200",
        "industry_id": 2,
        "location_id": 1,
    }
]

def seed_edge():
    db = SessionLocal()
    try:
        for data in EDGE_COMPANIES:
            comp = db.scalar(select(Company).where(Company.slug == data["slug"]))
            if not comp:
                comp = Company(
                    employer_id=24,
                    owner_id=24,
                    slug=data["slug"],
                    name=data["name"],
                    tagline=data["tagline"],
                    is_verified=data["is_verified"],
                    is_visible=data["is_visible"],
                    is_draft=False,
                    status=data["status"],
                    size_range=data["size_range"],
                    industry_id=data["industry_id"],
                    location_id=data["location_id"],
                    search_text=normalize_search_text(f"{data['name']} {data['tagline']}")
                )
                db.add(comp)
            else:
                comp.name = data["name"]
                comp.tagline = data["tagline"]
                comp.is_verified = data["is_verified"]
                comp.is_visible = data["is_visible"]
                comp.is_draft = False
                comp.status = data["status"]
                comp.size_range = data["size_range"]
                comp.industry_id = data["industry_id"]
                comp.location_id = data["location_id"]
                comp.search_text = normalize_search_text(f"{data['name']} {data['tagline']}")
        db.commit()
        print("Successfully seeded edge test companies!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_edge()
