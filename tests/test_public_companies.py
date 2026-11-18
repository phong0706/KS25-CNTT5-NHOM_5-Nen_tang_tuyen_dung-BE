"""Pytest cho API Công ty công khai (/api/companies*), bảo mật URL, chuẩn hóa tìm kiếm & facets."""
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app
from app.services.public_company_rules import (
    normalize_search_text, validate_company_media_url, validate_company_website,
)

client = TestClient(app)


def test_normalize_search_and_website_media_validation():
    assert normalize_search_text("  Ngân   Hàng ĐÔNG Á ") == "ngan hang dong a"
    assert validate_company_website("https://techrecruit.vn/jobs") == "https://techrecruit.vn/jobs"
    assert validate_company_website(None) is None
    for bad in ("javascript:alert(1)", "JAVASCRIPT:void(0)", "data:text/html,<svg>", "file:///etc/passwd", "ftp://a.vn"):
        with pytest.raises(ValueError):
            validate_company_website(bad)
    for bad_img in ("http://insecure.vn/a.png", "javascript:alert(1)", "data:image/png;base64,abc", "/uploads/../etc/passwd"):
        with pytest.raises(ValueError):
            validate_company_media_url(bad_img)
    assert validate_company_media_url("https://cdn.example.vn/logo.png") == "https://cdn.example.vn/logo.png"
    assert validate_company_media_url("/uploads/logos/a.webp") == "/uploads/logos/a.webp"


def test_search_normalization_and_sql_wildcard_safety():
    for q in ("ngan hang", "  DONG   A ", "Đông Á"):
        r = client.get("/api/companies", params={"q": q, "hiring": 0})
        assert r.status_code == 200
        assert r.headers.get("cache-control") == "public, max-age=60"
        slugs = [x["slug"] for x in r.json()["items"]]
        assert "ngan-hang-so-dong-a" in slugs

    for payload in ("%", "_", "%_%", "' OR 1=1 --"):
        r = client.get("/api/companies", params={"q": payload, "hiring": 0})
        assert r.status_code == 200
        assert r.json()["total"] == 0 and r.json()["items"] == []


def test_pagination_limits_hiring_filter_and_no_pii():
    assert client.get("/api/companies", params={"page": 0}).status_code == 422
    assert client.get("/api/companies", params={"page": -2}).status_code == 422
    assert client.get("/api/companies", params={"page_size": 49}).status_code == 422

    r_over = client.get("/api/companies", params={"page": 999, "hiring": 0})
    assert r_over.status_code == 200 and r_over.json()["items"] == []

    r_hiring = client.get("/api/companies", params={"hiring": 1, "page_size": 48}).json()
    hiring_slugs = [c["slug"] for c in r_hiring["items"]]
    assert "phan-mem-nhung-hai-dang" not in hiring_slugs
    assert "cong-ty-noi-bo-an" not in hiring_slugs

    r_all = client.get("/api/companies", params={"hiring": 0, "page_size": 48, "sort": "recent"}).json()
    all_slugs = [c["slug"] for c in r_all["items"]]
    assert "phan-mem-nhung-hai-dang" in all_slugs
    assert r_all["items"][-1]["open_jobs"] == 0

    for item in r_all["items"]:
        for forbidden in ("email", "phone", "employer_id", "user_id", "owner_id"):
            assert forbidden not in item

    for facet_list in r_all["facets"].values():
        assert all(f["count"] >= 0 for f in facet_list)
    assert sum(f["count"] for f in r_all["facets"]["industry"]) == r_all["total"]


def test_hidden_and_missing_company_identical_404():
    r_hidden = client.get("/api/companies/cong-ty-noi-bo-an")
    r_missing = client.get("/api/companies/khong-ton-tai-xyz-999")
    assert r_hidden.status_code == 404 and r_missing.status_code == 404
    assert r_hidden.json() == r_missing.json()

    rj_hidden = client.get("/api/companies/cong-ty-noi-bo-an/jobs")
    rj_missing = client.get("/api/companies/khong-ton-tai-xyz-999/jobs")
    assert rj_hidden.status_code == 404 and rj_missing.status_code == 404
    assert rj_hidden.json() == rj_missing.json()


def test_salary_range_thresholds_top_skills_and_similar():
    # 0 tin khai lương (chỉ lương thỏa thuận) -> salary_range=None
    r0 = client.get("/api/companies/an-ninh-mang-lam-son").json()
    assert r0["salary_range"] is None and r0["open_jobs"] >= 2

    # 1 tin khai lương + 1 tin thỏa thuận -> salary_range=None (cần >= 2 tin khai lương)
    r1 = client.get("/api/companies/tu-dong-hoa-kiem-thu-anh-duong").json()
    assert r1["salary_range"] is None and r1["open_jobs"] == 2

    # >= 2 tin khai lương -> có salary_range chính xác, similar không chứa chính nó
    r2 = client.get("/api/companies/ngan-hang-so-dong-a")
    assert r2.status_code == 200 and r2.headers.get("cache-control") == "public, max-age=60"
    d2 = r2.json()
    assert d2["salary_range"] is not None and d2["salary_range"]["sample_size"] >= 2
    assert d2["slug"] not in [s["slug"] for s in d2["similar"]]
    for forbidden in ("email", "phone", "employer_id", "user_id", "owner_id"):
        assert forbidden not in d2

    # Thứ tự top_skills ổn định giữa hai lần gọi khi hòa điểm
    r2_again = client.get("/api/companies/ngan-hang-so-dong-a").json()
    assert d2["top_skills"] == r2_again["top_skills"]
    assert len(d2["top_skills"]) <= 8

    # Endpoint /jobs của công ty
    rj = client.get("/api/companies/ngan-hang-so-dong-a/jobs", params={"sort": "salary"})
    assert rj.status_code == 200 and rj.headers.get("cache-control") == "public, max-age=60"
    assert rj.json()["total"] == d2["open_jobs"]
    assert len(rj.json()["facets"]["location"]) >= 1
