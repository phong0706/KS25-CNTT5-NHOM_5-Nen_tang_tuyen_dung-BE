"""Seed 5 công ty đã xác minh (VERIFIED).

Yêu cầu: đã chạy sql/init.sql (bảng users) và seed.py (bảng industries) trước.
Chạy:  python seed_company.py
"""
import os
import sys

# đường dẫn thư mục BE vào hệ thống để Python nhận diện được app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.catalog import Industry
from app.models.company import Company, CompanyStatus
from app.models.item import Item  # noqa: F401 - chỉ để SQLAlchemy nhận đủ các bảng

# (email_chủ_tài_khoản, tên_công_ty, logo, ảnh_bìa, mã_số_thuế, quy_mô, tên_ngành, địa_chỉ, website, mô_tả)
COMPANIES = [
    (
        "hr1@tuyendung.com",
        "FPT Software",
        "https://example.com/logos/fpt.png",
        "https://example.com/covers/fpt.png",
        "0301363748",
        "1000+",
        "Công nghệ thông tin",
        "Tòa nhà FPT, 17 Tố Hữu, Nam Từ Liêm, Hà Nội",
        "https://fpt.com",
        "FPT Software là đơn vị hàng đầu Việt Nam về xuất khẩu phần mềm và dịch vụ CNTT.",
    ),
    (
        "hr2@tuyendung.com",
        "VNG Corporation",
        "https://example.com/logos/vng.png",
        "https://example.com/covers/vng.png",
        "0305126689",
        "1000+",
        "Công nghệ thông tin",
        "Z06, Khu Công Nghệ Cao, Đường D1, TP. Thủ Đức, Hồ Chí Minh",
        "https://vng.com.vn",
        "VNG là công ty công nghệ Internet đầu tiên của Việt Nam, phát triển game và Zalo.",
    ),
    (
        "hr3@tuyendung.com",
        "Viettel Group",
        "https://example.com/logos/viettel.png",
        "https://example.com/covers/viettel.png",
        "0100626389",
        "1000+",
        "Công nghệ thông tin",
        "Tòa nhà Viettel, 285 Cầu Giấy, Dịch Vọng, Cầu Giấy, Hà Nội",
        "https://viettel.vn",
        "Tập đoàn Công nghiệp - Viễn thông Quân đội, nhà mạng lớn nhất Việt Nam.",
    ),
    (
        "hr4@tuyendung.com",
        "Vingroup",
        "https://example.com/logos/vingroup.png",
        "https://example.com/covers/vingroup.png",
        "0101341018",
        "1000+",
        "Bất động sản",
        "Tòa nhà Vincom Center, 191 Bà Triệu, Hai Bà Trưng, Hà Nội",
        "https://vingroup.net",
        "Tập đoàn kinh tế tư nhân lớn nhất Việt Nam, hoạt động trong bất động sản, bán lẻ và y tế.",
    ),
    (
        "hr5@tuyendung.com",
        "Masan Group",
        "https://example.com/logos/masan.png",
        "https://example.com/covers/masan.png",
        "0106202113",
        "1000+",
        "Sản xuất / Vận hành",
        "Tòa nhà Masan, 26-28 Đường số 5, Khu đô thị Him Lam, Bình Hưng, Hồ Chí Minh",
        "https://masangroup.com",
        "Tập đoàn Masan hoạt động trong lĩnh vực hàng tiêu dùng nhanh (FMCG) và bán lẻ.",
    ),
]


def run_seed():
    db = SessionLocal()
    try:
        print("Đang tiến hành seed dữ liệu công ty...")

        industries = {ind.name: ind.id for ind in db.query(Industry).all()}
        if not industries:
            print(
                "Cảnh báo: chưa có dữ liệu ngành (industries). Hãy chạy seed.py trước."
            )

        added = 0
        skipped = 0

        for (
            owner_email,
            name,
            logo,
            cover_image,
            tax_code,
            company_size,
            industry_name,
            address,
            website,
            description,
        ) in COMPANIES:
            if db.query(Company).filter_by(name=name).first():
                skipped += 1
                continue

            row = db.execute(
                text(
                    "SELECT id FROM users WHERE email IN (:email, :fallback_email) LIMIT 1"
                ),
                {
                    "email": owner_email,
                    "fallback_email": owner_email.replace("@", ""),
                },
            ).first()
            if row is None:
                print(
                    f"Bỏ qua '{name}': không tìm thấy user email='{owner_email}'. Hãy chạy sql/init.sql trước."
                )
                skipped += 1
                continue
            owner_id = row[0]

            industry_id = industries.get(industry_name)

            db.add(
                Company(
                    employer_id=owner_id,
                    owner_id=owner_id,
                    name=name,
                    logo=logo,
                    cover_image=cover_image,
                    tax_code=tax_code,
                    company_size=company_size,
                    industry_id=industry_id,
                    address=address,
                    website=website,
                    description=description,
                    status=CompanyStatus.VERIFIED,
                    is_draft=False,
                )
            )
            added += 1

        db.commit()
        print(
            f"Seed công ty thành công! Đã thêm {added} công ty VERIFIED, bỏ qua {skipped} công ty đã có/thiếu chủ."
        )

    except Exception as e:
        db.rollback()
        print(f"Lỗi xảy ra khi seed dữ liệu công ty: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
