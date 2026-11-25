"""Pytest cho router candidate_cv_documents (/api/candidate/cv-documents).
Kiểm thử tuân thủ techrecruit-rules: 401/403/404, kiểm soát xung đột OCC 409, nhân bản, đổi tên, xoá.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _login(email: str, password: str) -> str:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    return res.json().get("access_token")


def test_cv_documents_unauthorized():
    res = client.get("/api/candidate/cv-documents")
    assert res.status_code == 401

    res = client.post("/api/candidate/cv-documents", json={"title": "Test", "content_json": "{}"})
    assert res.status_code == 401


def test_cv_documents_full_crud_and_occ():
    token = _login("ungvien1@gmail.com", "ungvien1@")
    assert token, "Đăng nhập ứng viên thất bại"
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo CV mới
    payload = {
        "title": "CV Kỹ sư Frontend React",
        "template_slug": "simple",
        "content_json": '{"name": "Nguyễn Văn A", "skills": ["React", "TypeScript"]}',
    }
    create_res = client.post("/api/candidate/cv-documents", json=payload, headers=headers)
    assert create_res.status_code == 201
    created_cv = create_res.json()
    cv_id = created_cv["id"]
    assert created_cv["title"] == payload["title"]
    assert created_cv["version"] == 1

    # 2. Lấy danh sách CV
    list_res = client.get("/api/candidate/cv-documents", headers=headers)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert any(doc["id"] == cv_id for doc in docs)

    # 3. Lấy chi tiết CV
    detail_res = client.get(f"/api/candidate/cv-documents/{cv_id}", headers=headers)
    assert detail_res.status_code == 200
    assert detail_res.json()["title"] == payload["title"]

    # 4. Cập nhật thành công với version đúng
    update_payload = {
        "title": "CV Kỹ sư Frontend Senior",
        "template_slug": "professional",
        "content_json": '{"name": "Nguyễn Văn A", "skills": ["React", "Next.js"]}',
        "version": 1,
    }
    update_res = client.put(f"/api/candidate/cv-documents/{cv_id}", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_cv = update_res.json()
    assert updated_cv["version"] == 2
    assert updated_cv["title"] == "CV Kỹ sư Frontend Senior"

    # 5. Cập nhật với version cũ (OCC Conflict 409)
    stale_payload = {
        "title": "CV Kỹ sư Xung đột",
        "template_slug": "simple",
        "content_json": '{"name": "Nguyễn Văn A"}',
        "version": 1,  # Đã lên 2 mà gửi 1 -> phải 409
    }
    conflict_res = client.put(f"/api/candidate/cv-documents/{cv_id}", json=stale_payload, headers=headers)
    assert conflict_res.status_code == 409

    # 6. Đổi tên
    rename_res = client.patch(f"/api/candidate/cv-documents/{cv_id}/rename", json={"title": "CV Frontend 2026"}, headers=headers)
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "CV Frontend 2026"

    # 7. Nhân bản (duplicate)
    dup_res = client.post(f"/api/candidate/cv-documents/{cv_id}/duplicate", headers=headers)
    assert dup_res.status_code == 201
    dup_cv = dup_res.json()
    assert dup_cv["id"] != cv_id
    assert "Bản sao" in dup_cv["title"]
    assert dup_cv["version"] == 1

    # 8. Xoá CV gốc và bản sao
    del_res = client.delete(f"/api/candidate/cv-documents/{cv_id}", headers=headers)
    assert del_res.status_code == 200
    client.delete(f"/api/candidate/cv-documents/{dup_cv['id']}", headers=headers)

    # 9. Đọc lại CV đã xoá -> 404
    not_found_res = client.get(f"/api/candidate/cv-documents/{cv_id}", headers=headers)
    assert not_found_res.status_code == 404
