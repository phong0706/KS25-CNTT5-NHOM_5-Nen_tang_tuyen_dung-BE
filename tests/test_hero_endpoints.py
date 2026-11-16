"""Pytest kiểm thử các endpoint cung cấp dữ liệu cho Hero Workbench.
Bao gồm: /api/jobs, /api/stats/home, /api/companies/featured.
Tuân thủ techrecruit-rules: < 200 dòng, kiểm tra ca rỗng, biên, cấu trúc dữ liệu.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_hero_jobs_live_feed():
    """Kiểm tra endpoint /api/jobs cấp dữ liệu cho Live Feed của Hero."""
    res = client.get("/api/jobs?page_size=3&sort=newest")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 3

    if data["items"]:
        first = data["items"][0]
        assert "id" in first
        assert "title" in first
        assert "company_name" in first
        assert "company_id" in first
        assert "location" in first


def test_hero_jobs_chip_filters():
    """Kiểm tra các bộ lọc chip (q=Go, q=React, q=DevOps, q=Python)."""
    for query in ["Go", "React", "DevOps", "Python"]:
        res = client.get(f"/api/jobs?q={query}&page_size=3&sort=newest")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)


def test_hero_home_stats():
    """Kiểm tra endpoint thống kê /api/stats/home cấp số liệu cho footer của Hero."""
    res = client.get("/api/stats/home")
    assert res.status_code == 200
    data = res.json()
    assert "total_published_jobs" in data
    assert "total_companies" in data
    assert data["total_published_jobs"] >= 0
    assert data["total_companies"] >= 0


def test_hero_featured_companies():
    """Kiểm tra danh sách công ty nổi bật /api/companies/featured."""
    res = client.get("/api/companies/featured?limit=12")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if data:
        comp = data[0]
        assert "id" in comp
        assert "name" in comp
        assert "slug" in comp
