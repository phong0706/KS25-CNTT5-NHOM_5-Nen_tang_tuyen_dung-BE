"""Script dọn dẹp dữ liệu công ty test và chuẩn hóa 10 công ty công nghệ thực tế (<= 195 dòng).
Chạy: python scripts/cleanup_and_seed_companies.py
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import delete, func, select, text
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.company import Company, CompanyStatus
from app.models.company_verification import CompanyVerification
from app.models.job import Job
from app.models.user import User
from app.services.employer_criteria_service import CRITERION_META
from app.services.public_company_rules import normalize_search_text

LIC_DIR = BASE_DIR / "storage" / "company_licenses"
LIC_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_PDF = LIC_DIR / "giay_phep_kinh_doanh_chuan.pdf"
if not SAMPLE_PDF.exists():
    SAMPLE_PDF.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")

COMPANIES_DATA = [
    # 4 Công ty ĐÃ XÁC MINH (đạt đủ 5/5 tiêu chí)
    ("rikkeisoft", "Rikkeisoft", "0105875417", "tuyendung@rikkeisoft.com", "https://rikkeisoft.com", "Tầng 21 Handico Tower, Phạm Hùng, Nam Từ Liêm, Hà Nội", "Khát vọng đưa công nghệ Việt vươn tầm thế giới", "Rikkeisoft là doanh nghiệp CNTT hàng đầu thành lập năm 2012, chuyên xuất khẩu phần mềm, chuyển đổi số, AI cho thị trường Nhật Bản, Mỹ và APAC.", "1000+", 2012, "da_xac_minh", None),
    ("fpt-software", "FPT Software", "0101248141", "careers@fptsoftware.com", "https://fptsoftware.com", "Tòa nhà FPT, Phố Duy Tân, Cầu Giấy, Hà Nội", "Công ty phần mềm toàn cầu hàng đầu Đông Nam Á", "FPT Software hiện diện tại hơn 30 quốc gia với hơn 30.000 nhân sự, cung cấp dịch vụ chuyển đổi số, Cloud và kỹ thuật phần mềm thế hệ mới.", "1000+", 1999, "da_xac_minh", None),
    ("viettel-solutions", "Viettel Solutions", "0100109106", "contact@viettelsolutions.vn", "https://viettelsolutions.vn", "Số 1 Trần Hữu Dực, Mỹ Đình 2, Nam Từ Liêm, Hà Nội", "Đồng hành chuyển đổi số cùng Chính phủ và Doanh nghiệp", "Đơn vị nòng cốt của Tập đoàn Viettel tiên phong triển khai thành phố thông minh, y tế số, giáo dục số và an toàn thông tin quốc gia.", "1000+", 2018, "da_xac_minh", None),
    ("vng-corporation", "VNG Corporation", "0303541170", "recruitment@vng.com.vn", "https://vng.com.vn", "Z06 Đường số 13, KCX Tân Thuận, Quận 7, TP. Hồ Chí Minh", "Kiến tạo công nghệ và phát triển con người", "Kỳ lân công nghệ đầu tiên của Việt Nam với hệ sinh thái ứng dụng nhắn tin Zalo, cổng thanh toán ZaloPay, Cloud và game trực tuyến thịnh hành.", "1000+", 2004, "da_xac_minh", None),
    # 4 Công ty ĐANG CHỜ DUYỆT
    ("momo", "MoMo (M-Service)", "0305175960", "tuyendung@momo.vn", "https://momo.vn", "Tòa nhà Phú Mỹ Hưng, 8 Hoàng Văn Thái, Quận 7, TP. Hồ Chí Minh", "Siêu ứng dụng tài chính hàng đầu Việt Nam", "Nền tảng thanh toán di động và dịch vụ tài chính toàn diện phục vụ hơn 30 triệu người dùng tại Việt Nam.", "501-1000", 2007, "cho_duyet", None),
    ("vnpt-it", "VNPT IT", "0100684378", "tuyendung@vnpt.vn", "https://vnptit.vn", "Số 57 Huỳnh Thúc Kháng, Láng Hạ, Đống Đa, Hà Nội", "Hạ tầng số và giải pháp CNTT quốc gia", "Công ty CNTT trực thuộc Tập đoàn VNPT phát triển giải pháp then chốt cho Chính phủ điện tử, Y tế, Giáo dục và Doanh nghiệp.", "1000+", 2018, "cho_duyet", None),
    ("tiki", "Tiki", "0309995576", "careers@tiki.vn", "https://tiki.vn", "Số 52 Út Tịch, Phường 4, Tân Bình, TP. Hồ Chí Minh", "Hệ sinh thái thương mại số đáng tin cậy", "Sàn thương mại điện tử uy tín với chuỗi cung ứng TikiNOW giao nhanh 2 giờ và nền tảng mua sắm trực tuyến hiện đại.", "501-1000", 2010, "cho_duyet", None),
    ("one-mount-group", "One Mount Group", "0108906385", "careers@onemount.com", "https://onemount.com", "Tòa nhà Times City, 458 Minh Khai, Hai Bà Trưng, Hà Nội", "Kiến tạo hệ sinh thái số lớn nhất Việt Nam", "Hệ sinh thái công nghệ kết nối người tiêu dùng và doanh nghiệp với các mũi nhọn: VinShop, VinID và OneHousing.", "1000+", 2019, "cho_duyet", None),
    # 2 Công ty CHƯA ĐƯỢC DUYỆT (từ chối kèm lý do)
    ("zalopay", "ZaloPay (ZION)", "0303912992", "tuyendung@zalopay.vn", "https://zalopay.vn", "Khu Công Nghệ Cao, Long Thạnh Mỹ, TP. Thủ Đức, TP. Hồ Chí Minh", "Ví điện tử quốc dân chuyển tiền nhanh trong Zalo", "Nền tảng ví điện tử và trung gian thanh toán tích hợp trực tiếp trong Zalo, hỗ trợ giao dịch 24/7 tức thì.", "201-500", 2005, "tu_choi", "Ảnh giấy phép kinh doanh bị mất góc, không đối chiếu được mã số thuế trên hệ thống quốc gia."),
    ("kms-technology", "KMS Technology", "0309139824", "careers@kms-technology.com", "https://kms-technology.com", "Số 2 Tân Viên, Phường 2, Tân Bình, TP. Hồ Chí Minh", "Giải pháp phần mềm chất lượng cao cho thị trường quốc tế", "Doanh nghiệp dịch vụ kỹ thuật phần mềm có vốn đầu tư Hoa Kỳ, chuyên tư vấn kiến trúc và kiểm thử tự động hóa cao cấp.", "501-1000", 2009, "tu_choi", "Mã số thuế trên hồ sơ đối chiếu chưa khớp với thông tin trên Cổng thông tin quốc gia về đăng ký doanh nghiệp."),
]

def cleanup_test_data(db):
    print("=== 1. DỌN DẸP DỮ LIỆU CÔNG TY TEST NGẪU NHIÊN ===")
    p = re.compile(r"^(Công ty(\s+Cổ\s+phần)?|Company|Comp)\s+[0-9a-fA-F]{6,8}$", re.IGNORECASE)
    test_comps = [c for c in db.scalars(select(Company)).all() if p.match(c.name.strip())]
    if not test_comps:
        print("[DỌN DẸP] Không có công ty test ngẫu nhiên nào cần xóa.")
        return 0
    t_ids = [c.id for c in test_comps]
    t_emp_ids = [c.employer_id for c in test_comps if c.employer_id]
    id_in = ",".join(str(i) for i in t_ids)

    job_ids = [r[0] for r in db.execute(text(f"SELECT id FROM jobs WHERE company_id IN ({id_in})")).fetchall()]
    if job_ids:
        j_in = ",".join(str(j) for j in job_ids)
        for tbl in ["job_status_history", "applications", "job_applications", "saved_jobs", "job_skills", "application_drafts"]:
            db.execute(text(f"DELETE FROM {tbl} WHERE job_id IN ({j_in})"))
        db.execute(text(f"DELETE FROM jobs WHERE id IN ({j_in})"))
        print(f"  - Đã xóa {len(job_ids)} tin tuyển dụng và toàn bộ hồ sơ ứng tuyển liên quan.")

    db.execute(text(f"DELETE FROM company_verifications WHERE company_id IN ({id_in})"))
    db.execute(text(f"DELETE FROM audit_logs WHERE target_id IN ({id_in}) AND target_type IN ('company', 'employer_criterion')"))
    db.execute(text(f"DELETE FROM companies WHERE id IN ({id_in})"))
    print(f"  - Đã xóa an toàn {len(t_ids)} công ty test dạng ngẫu nhiên.")

    if t_emp_ids:
        emp_in = ",".join(str(e) for e in set(t_emp_ids))
        cnt_u = db.execute(text(f"DELETE FROM users WHERE id IN ({emp_in}) AND email LIKE '%@test.com'")).rowcount
        print(f"  - Đã dọn {cnt_u} tài khoản employer test đi kèm.")
    db.commit()
    return len(t_ids)

def seed_real_companies(db):
    print("=== 2. TẠO MỚI / CHUẨN HÓA 10 CÔNG TY CÔNG NGHỆ THỰC TẾ ===")
    admin = db.scalars(select(User).where(User.role == "admin")).first()
    now = datetime.now()
    old_date = now - timedelta(days=210)
    for slug, name, mst, email, web, addr, tag, desc, sz, yr, vst, reason in COMPANIES_DATA:
        emp = db.scalar(select(User).where(User.email == email))
        if not emp:
            emp = User(email=email, password=hash_password("TechRecruit2026!"), full_name=f"Tuyển dụng {name}", role="employer", is_active=True, created_at=old_date)
            db.add(emp); db.flush()
        else:
            emp.full_name, emp.is_active = f"Tuyển dụng {name}", True
            if not emp.created_at or emp.created_at > old_date:
                emp.created_at = old_date
            db.flush()

        comp = db.scalar(select(Company).where((Company.slug == slug) | (Company.name == name)))
        c_st = CompanyStatus.VERIFIED if vst == "da_xac_minh" else (CompanyStatus.REJECTED if vst == "tu_choi" else CompanyStatus.PENDING)
        if not comp:
            comp = Company(slug=slug, name=name, employer_id=emp.id, owner_id=emp.id)
            db.add(comp); db.flush()
        comp.name, comp.slug, comp.employer_id, comp.owner_id = name, slug, emp.id, emp.id
        comp.tax_code, comp.website, comp.address, comp.tagline = mst, web, addr, tag
        comp.description, comp.size_range, comp.founded_year = desc, sz, yr
        comp.status, comp.verification_status, comp.is_verified = c_st, vst, (vst == "da_xac_minh")
        comp.is_visible, comp.is_draft, comp.verification_rejection_reason = True, False, reason
        comp.search_text = normalize_search_text(name, tag, addr)[:500]
        db.flush()

        verif = db.scalar(select(CompanyVerification).where(CompanyVerification.company_id == comp.id).order_by(CompanyVerification.id.desc()))
        if not verif:
            verif = CompanyVerification(
                company_id=comp.id, mst=mst, mst_raw=mst, submitted_by=emp.id, version=1,
                status=vst, license_storage_key="giay_phep_kinh_doanh_chuan.pdf",
                license_original_name=f"DKKD_{slug}.pdf", license_mime_type="application/pdf",
                license_size_bytes=102400, rejection_reason=reason,
            )
            db.add(verif); db.flush()
        else:
            verif.mst, verif.mst_raw, verif.status, verif.rejection_reason = mst, mst, vst, reason
            verif.license_storage_key = "giay_phep_kinh_doanh_chuan.pdf"
            verif.license_original_name = f"DKKD_{slug}.pdf"
            verif.license_mime_type, verif.license_size_bytes = "application/pdf", 102400
        if vst in ("da_xac_minh", "tu_choi"):
            verif.reviewed_by = admin.id if admin else emp.id
            verif.reviewed_at = now - timedelta(days=5)

        if vst == "da_xac_minh":
            for crit_code in CRITERION_META.keys():
                has_log = db.scalar(select(AuditLog.id).where(AuditLog.target_type == "employer_criterion", AuditLog.target_id == comp.id, AuditLog.new_value == crit_code))
                if not has_log:
                    db.add(AuditLog(actor_id=admin.id if admin else emp.id, actor_name="System Admin", actor_role="admin", target_type="employer_criterion", target_id=comp.id, target_label=f"{name} · {CRITERION_META[crit_code][0]}", action="MANUAL_VERIFY_CRITERION", new_value=crit_code, reason="Hồ sơ doanh nghiệp hợp lệ đã xác minh", created_at=now - timedelta(days=5)))
        db.commit()
        print(f"  ✓ {name:20} | MST: {mst} | {vst:14} | Email: {email}")

def main():
    db = SessionLocal()
    try:
        cleanup_test_data(db)
        seed_real_companies(db)
        print("\n[HOÀN TẤT] Đã dọn dẹp và chuẩn hóa 10 công ty công nghệ thực tế thành công!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
