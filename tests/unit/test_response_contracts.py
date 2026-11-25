"""
backend/tests/unit/test_response_contracts.py
Kiểm thử tính đầy đủ của Response Contracts (BUG-S3-06).
- GET /api/jobs/{id} phải chứa 'status'
- GET /api/companies items phải chứa 'id'
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_job_detail_has_status():
    # Lấy job public đầu tiên
    res_list = client.get("/api/jobs?limit=1")
    assert res_list.status_code == 200
    items = res_list.json().get("items", [])
    if items:
        job_id = items[0]["id"]
        res_detail = client.get(f"/api/jobs/{job_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert "status" in detail, "Public job detail MUST contain 'status' field!"

def test_company_list_item_has_id():
    res = client.get("/api/companies?page_size=5")
    assert res.status_code == 200
    items = res.json().get("items", [])
    if items:
        assert "id" in items[0], "Company list card MUST contain 'id' field!"
