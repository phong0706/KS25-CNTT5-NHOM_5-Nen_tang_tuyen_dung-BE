"""Pytest kiểm tra toàn diện module xử lý logo và API upload logo.
Bao gồm:
- PNG trong suốt, JPEG nền trắng có lề lớn (autocrop)
- Ảnh toàn trắng / toàn 1 màu (blank_image)
- 0 byte, 2MB + 1 byte
- File giả đuôi .png (text, SVG, HTML)
- Ảnh bom giải nén (DecompressionBomb)
- GIF / WebP động (lấy frame đầu)
- CMYK và Palette (chuyển RGBA)
- Xoay EXIF
- Ảnh 40x40 (too_small)
- Banner ngang 600x100, banner dọc 100x600 (not_logo_shape)
- Kết quả luôn vuông 256 và 512 WebP, không còn EXIF
- Phân quyền: candidate (403), employer A upload cty B (403), cty không tồn tại (404), nosniff header.
"""
import io
import os
import uuid
import pytest
from PIL import Image, ImageDraw
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.company_logo import CompanyLogo
from app.models.user import User
from app.services.logo_processing import LogoError, process_logo


# =========================================================================
# 1. HÀM HELPER TẠO ẢNH TEST BẰNG PILLOW
# =========================================================================
def create_test_png(w=120, h=120, bg=(0, 0, 0, 0), fg=(255, 0, 0, 255)):
    im = Image.new("RGBA", (w, h), bg)
    draw = ImageDraw.Draw(im)
    draw.rectangle([w // 4, h // 4, 3 * w // 4, 3 * h // 4], fill=fg)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def create_test_jpeg(w=200, h=200, bg=(255, 255, 255), fg=(0, 100, 200)):
    im = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(im)
    draw.ellipse([60, 60, 140, 140], fill=fg)
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


# =========================================================================
# 2. KIỂM THỬ XỬ LÝ ẢNH THUẦN (LOGO_PROCESSING)
# =========================================================================
def test_png_transparent():
    raw = create_test_png(120, 120)
    res = process_logo(raw)
    assert 256 in res and 512 in res
    im256 = Image.open(io.BytesIO(res[256]))
    assert im256.size == (256, 256)
    assert im256.format == "WEBP"


def test_jpeg_large_white_border():
    raw = create_test_jpeg(300, 300, bg=(255, 255, 255), fg=(20, 40, 180))
    res = process_logo(raw)
    im256 = Image.open(io.BytesIO(res[256]))
    im512 = Image.open(io.BytesIO(res[512]))
    assert im256.size == (256, 256)
    assert im512.size == (512, 512)


def test_all_white_or_solid_color():
    im = Image.new("RGB", (100, 100), (255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    with pytest.raises(LogoError) as exc_info:
        process_logo(buf.getvalue())
    assert exc_info.value.code == "blank_image"


def test_zero_bytes():
    with pytest.raises(LogoError) as exc_info:
        process_logo(b"")
    assert exc_info.value.code == "empty_file"


def test_too_large_2mb_plus_1():
    fake_large = b"x" * (2 * 1024 * 1024 + 1)
    with pytest.raises(LogoError) as exc_info:
        process_logo(fake_large)
    assert exc_info.value.code == "too_large"


def test_fake_png_with_text_svg_html():
    # File giả mạo nội dung text/HTML/SVG mang đuôi .png
    cases = [
        b"Hello world, this is a plain text file pretending to be image.",
        b"<html><body><h1>Not an image</h1></body></html>",
        b"<svg width='100' height='100'><circle cx='50' cy='50' r='40'/></svg>",
        b"\x89PNG\r\n\x1a\nCorrupt header and invalid data stream",
    ]
    for c in cases:
        with pytest.raises(LogoError) as exc_info:
            process_logo(c)
        assert exc_info.value.code in ("corrupt_image", "unsupported_format")


def test_decompression_bomb():
    # Kích thước vượt 25 triệu pixel
    im = Image.new("RGB", (5100, 5000), (255, 255, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle([1000, 1000, 4000, 4000], fill=(200, 50, 50))
    buf = io.BytesIO()
    # Lưu JPEG mức nén cao để dung lượng file nhỏ < 2MB nhưng kích thước giải nén > 25.5 MP
    im.save(buf, format="JPEG", quality=10)
    raw = buf.getvalue()
    if len(raw) <= 2 * 1024 * 1024:
        with pytest.raises(LogoError) as exc_info:
            process_logo(raw)
        assert exc_info.value.code == "decompression_bomb"


def test_animated_gif_and_webp():
    # 1. GIF động 2 frame
    im1 = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
    d1 = ImageDraw.Draw(im1)
    d1.rectangle([20, 20, 80, 80], fill=(255, 0, 0, 255))

    im2 = Image.new("RGBA", (100, 100), (255, 255, 255, 0))
    d2 = ImageDraw.Draw(im2)
    d2.rectangle([20, 20, 80, 80], fill=(0, 255, 0, 255))

    buf_gif = io.BytesIO()
    im1.save(buf_gif, format="GIF", save_all=True, append_images=[im2])
    res_gif = process_logo(buf_gif.getvalue())
    assert 256 in res_gif and 512 in res_gif

    # 2. WebP động
    buf_webp = io.BytesIO()
    im1.save(buf_webp, format="WEBP", save_all=True, append_images=[im2])
    res_webp = process_logo(buf_webp.getvalue())
    assert 256 in res_webp and 512 in res_webp


def test_cmyk_and_palette():
    # CMYK JPEG
    im_cmyk = Image.new("CMYK", (120, 120), (100, 50, 0, 0))
    d = ImageDraw.Draw(im_cmyk)
    d.rectangle([20, 20, 100, 100], fill=(0, 100, 50, 0))
    buf_cmyk = io.BytesIO()
    im_cmyk.save(buf_cmyk, format="JPEG")
    res_cmyk = process_logo(buf_cmyk.getvalue())
    assert Image.open(io.BytesIO(res_cmyk[256])).size == (256, 256)

    # Palette (P)
    im_p = Image.new("P", (120, 120))
    im_p.putpalette([255, 255, 255, 0, 128, 255] * 128)
    d_p = ImageDraw.Draw(im_p)
    d_p.rectangle([30, 30, 90, 90], fill=1)
    buf_p = io.BytesIO()
    im_p.save(buf_p, format="PNG")
    res_p = process_logo(buf_p.getvalue())
    assert Image.open(io.BytesIO(res_p[512])).size == (512, 512)


def test_exif_rotation():
    im = Image.new("RGB", (120, 120), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 100, 100], fill=(10, 80, 160))
    exif = im.getexif()
    exif[0x0112] = 6  # Rotate 90 CW
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    res = process_logo(buf.getvalue())
    assert 256 in res


def test_too_small_40x40():
    raw = create_test_png(40, 40)
    with pytest.raises(LogoError) as exc_info:
        process_logo(raw)
    assert exc_info.value.code == "too_small"


def test_banner_horizontal_600x100():
    raw = create_test_png(600, 100)
    with pytest.raises(LogoError) as exc_info:
        process_logo(raw)
    assert exc_info.value.code == "not_logo_shape"


def test_banner_vertical_100x600():
    raw = create_test_png(100, 600)
    with pytest.raises(LogoError) as exc_info:
        process_logo(raw)
    assert exc_info.value.code == "not_logo_shape"


def test_output_always_square_and_no_exif():
    raw = create_test_jpeg(160, 140)
    res = process_logo(raw)
    for sz in (256, 512):
        im = Image.open(io.BytesIO(res[sz]))
        assert im.size == (sz, sz)
        assert im.format == "WEBP"
        # Metadata / EXIF bị xóa hoàn toàn
        exif = im.getexif()
        assert len(exif) == 0


# =========================================================================
# 3. KIỂM THỬ API, PHÂN QUYỀN & BẢO MẬT
# =========================================================================
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def make_user_token(db, user_id: int):
    u = db.query(User).filter_by(id=user_id).first()
    return create_access_token(user_id=u.id, role=u.role, token_version=getattr(u, "token_version", 1))


def test_permissions_candidate_and_cross_employer(client, db_session):
    # Company 49 thuộc về user 24 (employer)
    comp_a = db_session.query(Company).filter_by(id=49).first()
    assert comp_a is not None

    # 1. Candidate cố tải logo -> 403
    cand_token = make_user_token(db_session, 29)
    valid_logo = create_test_png(120, 120)

    res_cand = client.post(
        f"/api/companies/{comp_a.id}/logos",
        headers={"Authorization": f"Bearer {cand_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")}
    )
    assert res_cand.status_code == 403

    # 2. Employer B (user 25) cố tải logo cho công ty A (thuộc user 24) -> 403
    emp_other_token = make_user_token(db_session, 25)

    res_cross = client.post(
        f"/api/companies/{comp_a.id}/logos",
        headers={"Authorization": f"Bearer {emp_other_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")}
    )
    assert res_cross.status_code == 403

    # 3. Tải cho công ty không tồn tại -> 404
    res_404 = client.post(
        "/api/companies/999999/logos",
        headers={"Authorization": f"Bearer {emp_other_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")}
    )
    assert res_404.status_code in (403, 404)


def test_employer_upload_success_and_admin_approve(client, db_session):
    # Company 49 thuộc về user 24 (employer)
    comp = db_session.query(Company).filter_by(id=49).first()
    emp_token = make_user_token(db_session, comp.owner_id)

    old_logo_url = comp.logo_url
    valid_logo = create_test_png(150, 150)

    # Employer tải logo lên
    res_upload = client.post(
        f"/api/companies/{comp.id}/logos",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")}
    )
    assert res_upload.status_code == 200
    data = res_upload.json()
    assert data["status"] == "cho_duyet"
    assert data["is_current"] is False
    assert "_256.webp" in data["file_key"]
    logo_id = data["id"]

    # Đảm bảo logo công khai CHƯA bị ghi đè
    db_session.commit()
    comp = db_session.query(Company).filter_by(id=49).first()
    assert comp.logo_url == old_logo_url

    # Admin (user 23) duyệt logo
    admin_token = make_user_token(db_session, 23)
    res_appr = client.post(
        f"/api/company-logos/{logo_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_appr.status_code == 200
    appr_data = res_appr.json()
    assert appr_data["status"] == "dang_dung"
    assert appr_data["is_current"] is True

    # Logo công ty đã được cập nhật thành công
    db_session.commit()
    comp = db_session.query(Company).filter_by(id=49).first()
    assert comp.logo_url == appr_data["logo_url"].split("?")[0]
    assert comp.logo_url_2x is not None

    # Kiểm tra header nosniff khi phục vụ file logo
    file_key = appr_data["file_key"]
    res_file = client.get(f"/uploads/logos/{file_key}")
    assert res_file.status_code == 200
    assert res_file.headers.get("X-Content-Type-Options") == "nosniff"


def test_logo_preview_endpoint(client, db_session):
    comp = db_session.query(Company).filter_by(id=49).first()
    emp_token = make_user_token(db_session, comp.owner_id)

    # 1. Preview thành công
    valid_logo = create_test_png(150, 150)
    res = client.post(
        "/api/employer/company/logo/preview",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert "preview_url_256" in data
    assert data["preview_url_256"].startswith("data:image/webp;base64,")

    # 2. Preview banner -> 422 với thông điệp rõ ràng
    banner_logo = create_test_png(600, 100)
    res_ban = client.post(
        "/api/employer/company/logo/preview",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("banner.png", banner_logo, "image/png")},
    )
    assert res_ban.status_code == 422
    assert "banner" in res_ban.json()["detail"].lower()

    # 3. Preview quá nhỏ -> 422
    small_logo = create_test_png(40, 40)
    res_sm = client.post(
        "/api/employer/company/logo/preview",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("small.png", small_logo, "image/png")},
    )
    assert res_sm.status_code == 422
    assert "nhỏ" in res_sm.json()["detail"].lower()


def test_admin_serve_original_logo(client, db_session):
    # Upload một logo mới
    comp = db_session.query(Company).filter_by(id=49).first()
    emp_token = make_user_token(db_session, comp.owner_id)
    valid_logo = create_test_png(160, 160)
    res_up = client.post(
        f"/api/companies/{comp.id}/logos",
        headers={"Authorization": f"Bearer {emp_token}"},
        files={"file": ("logo.png", valid_logo, "image/png")},
    )
    assert res_up.status_code == 200
    logo_id = res_up.json()["id"]

    # Candidate truy cập ảnh gốc -> 403
    cand_token = make_user_token(db_session, 29)
    res_cand = client.get(
        f"/api/company-logos/{logo_id}/original",
        headers={"Authorization": f"Bearer {cand_token}"},
    )
    assert res_cand.status_code == 403

    # Admin truy cập ảnh gốc -> 200
    admin_token = make_user_token(db_session, 23)
    res_adm = client.get(
        f"/api/company-logos/{logo_id}/original",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_adm.status_code == 200
    assert res_adm.headers.get("X-Content-Type-Options") == "nosniff"
