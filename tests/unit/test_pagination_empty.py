"""
backend/tests/unit/test_pagination_empty.py
Kiểm thử phân trang: khi page vượt quá total_pages, phải trả về items rỗng (BUG-S3-07).
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_page_exceeding_total_pages_returns_empty_items():
    res = client.get("/api/jobs?page=999999&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == [], f"Expected empty items array when page exceeds total_pages, got {len(data['items'])} items"
