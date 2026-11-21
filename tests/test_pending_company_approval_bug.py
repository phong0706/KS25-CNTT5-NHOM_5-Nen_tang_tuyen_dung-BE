"""
Test tích hợp mô phỏng luồng employer gửi logo / thông tin công ty và admin kiểm tra danh sách chờ duyệt.
Mục đích: Tái hiện đúng bug khi employer gửi logo thành công nhưng admin không nhận được / không thấy.
"""
import uuid
from pathlib import Path
import sys
from fastapi.testclient import TestClient
import pytest
from PIL import Image, ImageDraw
import io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.db.session import SessionLocal
from app.models.user import User
from app.models.company import Company, CompanyStatus
from app.models.company_logo import CompanyLogo
from app.models.notification import Notification
from app.core.security import hash_password, create_access_token


def create_test_image_bytes():
    im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([30, 30, 90, 90], fill=(255, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_employer_upload_logo_must_be_visible_to_admin():
    """
    Kịch bản:
    1. Employer có công ty (chưa xác minh hoặc đã xác minh) tải logo lên qua POST /api/company/me/logo.
    2. Employer nhận được response thành công (status='pending').
    3. Admin gọi GET /api/admin/company-verifications?logo_status=pending để xem danh sách logo chờ duyệt.
    4. Admin kiểm tra counts (phải có số đếm logo chờ duyệt hoặc phản ánh vào tab chờ duyệt).
    5. Admin nhận được thông báo (Notification) thông báo có logo công ty mới chờ duyệt.
    """
    client = TestClient(app)
    db = SessionLocal()
    tag = uuid.uuid4().hex[:8]

    emp = User(
        email=f"emp_{tag}@test.vn",
        full_name=f"Employer {tag}",
        password=hash_password("Pass123!"),
        role="employer",
        is_active=True,
    )
    adm = User(
        email=f"adm_{tag}@test.vn",
        full_name=f"Admin {tag}",
        password=hash_password("Pass123!"),
        role="admin",
        is_active=True,
    )
    db.add_all([emp, adm])
    db.commit()
    db.refresh(emp)
    db.refresh(adm)

    comp = Company(
        employer_id=emp.id,
        owner_id=emp.id,
        name=f"Công ty Test Bug {tag}",
        slug=f"cong-ty-test-bug-{tag}",
        status=CompanyStatus.PENDING,
        verification_status="chua_xac_minh",
        logo_status="missing",
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    h_emp = {"Authorization": f"Bearer {create_access_token(emp.id, emp.role)}"}
    h_adm = {"Authorization": f"Bearer {create_access_token(adm.id, adm.role)}"}

    try:
        # BƯỚC 1: Employer upload logo
        png_bytes = create_test_image_bytes()
        r_upload = client.post(
            "/api/company/me/logo",
            files={"file": ("logo.png", png_bytes, "image/png")},
            headers=h_emp,
        )
        assert r_upload.status_code == 200, f"Upload failed: {r_upload.text}"
        data_upload = r_upload.json()
        assert data_upload["status"] == "pending"
        logo_id = data_upload["logo_id"]

        # BƯỚC 2: Kiểm tra database state
        db.rollback()
        db.refresh(comp)
        logo_record = db.query(CompanyLogo).filter_by(id=logo_id).first()
        assert logo_record is not None
        assert logo_record.status == "cho_duyet"

        # BUG 1 CHECK: comp.logo_status phải phản ánh là đang chờ duyệt (pending)
        assert comp.logo_status == "pending", f"Expected comp.logo_status to be 'pending', but got '{comp.logo_status}'"

        # BƯỚC 3: Admin gọi danh sách với bộ lọc logo_status=pending
        r_admin_logo = client.get("/api/admin/company-verifications?logo_status=pending", headers=h_adm)
        assert r_admin_logo.status_code == 200
        res_json = r_admin_logo.json()

        # BUG 2 CHECK: Endpoint admin phải lọc đúng các công ty có logo_status=pending
        item_ids = [item["id"] for item in res_json["items"]]
        assert comp.id in item_ids, f"Company {comp.id} not found in admin items with logo_status=pending"
        
        # Mọi items trả về phải có logo_status='pending' (hoặc có logo chờ duyệt)
        for it in res_json["items"]:
            assert it.get("logo_status") == "pending" or it.get("pending_logo") is not None, f"Item {it['id']} has wrong logo_status: {it.get('logo_status')}"

        # BUG 3 CHECK: counts phải có bộ đếm logo chờ duyệt (logo_pending hoặc tab phản ánh)
        counts = res_json.get("counts", {})
        assert counts.get("logo_pending", 0) > 0 or counts.get("cho_duyet_logo", 0) > 0, f"Counts missing pending logo count: {counts}"

        # BUG 4 CHECK: Admin phải nhận được thông báo
        notifs = db.query(Notification).filter_by(user_id=adm.id).all()
        assert len(notifs) > 0, "Admin did not receive any notification when employer uploaded a logo for approval"
        assert any("logo" in (n.title or "").lower() or "logo" in (n.message or "").lower() for n in notifs), "Notification does not mention logo"

    finally:
        # Dọn dẹp
        db.query(CompanyLogo).filter_by(company_id=comp.id).delete()
        db.query(Notification).filter(Notification.user_id.in_([emp.id, adm.id])).delete()
        db.query(Company).filter_by(id=comp.id).delete()
        db.query(User).filter(User.id.in_([emp.id, adm.id])).delete()
        db.commit()
        db.close()
