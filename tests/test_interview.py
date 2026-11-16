"""Pytest cho router interview-questions & admin interview-questions.
Tuân thủ techrecruit-rules: kiểm thử quyền hạn 401/403/404, ca rỗng/biên, không chia cho 0.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _login(email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r.json().get("access_token")


def test_public_list_and_filter():
    res = client.get("/api/interview-questions?page=1&page_size=5")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 40
    assert "stats" in data
    assert data["stats"]["total_count"] >= 40
    assert data["stats"]["percentage"] >= 0.0

    # Lọc theo category_id = 1
    cat1_res = client.get("/api/interview-questions?category_id=1")
    assert cat1_res.status_code == 200
    c_data = cat1_res.json()
    assert all(it["category_id"] == 1 for it in c_data["items"])

    # Lọc theo search
    q_res = client.get("/api/interview-questions?q=RESTful")
    assert q_res.status_code == 200
    assert any("RESTful" in it["question"] for it in q_res.json()["items"])


def test_random_question():
    res = client.get("/api/interview-questions/random?category_id=1")
    assert res.status_code == 200
    data = res.json()
    assert data["category_id"] == 1
    assert "question" in data
    assert "answer_hint" in data

    # Bộ lọc không tồn tại -> 404
    bad_res = client.get("/api/interview-questions/random?q=tu_khoa_khong_bao_gio_co_123456")
    assert bad_res.status_code == 404


def test_practice_toggle_auth():
    # 1. Chưa đăng nhập -> 401
    unauth = client.post("/api/interview-questions/1/practice")
    assert unauth.status_code == 401

    # 2. Đăng nhập ứng viên
    token = _login("ungvien1@gmail.com", "ungvien1@")
    assert token is not None
    headers = {"Authorization": f"Bearer {token}"}

    # Đánh dấu đã luyện
    r1 = client.post("/api/interview-questions/1/practice", headers=headers)
    assert r1.status_code == 200
    d1 = r1.json()
    assert "practiced" in d1
    assert "stats" in d1

    # Câu hỏi không tồn tại -> 404
    r_bad = client.post("/api/interview-questions/999999/practice", headers=headers)
    assert r_bad.status_code == 404


def test_admin_crud_permissions():
    # 1. Khách gọi admin -> 401
    assert client.get("/api/admin/interview-questions").status_code == 401

    # 2. Ứng viên gọi admin -> 403
    cand_token = _login("ungvien1@gmail.com", "ungvien1@")
    c_res = client.get("/api/admin/interview-questions", headers={"Authorization": f"Bearer {cand_token}"})
    assert c_res.status_code == 403

    # 3. Admin gọi admin -> 200
    admin_token = _login("admin@tuyendung.com", "admin123@")
    a_headers = {"Authorization": f"Bearer {admin_token}"}
    a_res = client.get("/api/admin/interview-questions", headers=a_headers)
    assert a_res.status_code == 200
    assert a_res.json()["total"] >= 40

    # 4. Admin CRUD
    new_q = {
        "category_id": 2, "level_id": 3,
        "question": "Câu hỏi kiểm thử admin automated test?",
        "answer_hint": "Gợi ý trả lời chi tiết cho kiểm thử.",
        "is_published": True,
    }
    create_res = client.post("/api/admin/interview-questions", json=new_q, headers=a_headers)
    assert create_res.status_code == 201
    qid = create_res.json()["id"]

    # Sửa
    update_res = client.put(f"/api/admin/interview-questions/{qid}", json={"question": "Câu hỏi đã sửa"}, headers=a_headers)
    assert update_res.status_code == 200
    assert update_res.json()["question"] == "Câu hỏi đã sửa"

    # Xóa
    del_res = client.delete(f"/api/admin/interview-questions/{qid}", headers=a_headers)
    assert del_res.status_code == 200
