"""Pytest cho API Công ty công khai (/api/companies*), bảo mật URL, facets & chống N+1."""
from contextlib import contextmanager
from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import engine
from app.main import app
from app.services import public_company_service as pcs
from app.services.public_company_rules import (
    normalize_search_text, validate_company_media_url, validate_company_website,
)

client = TestClient(app)
FORBIDDEN_PII_KEYS = ("email", "phone", "employer_id", "user_id", "owner_id")


@contextmanager
def count_sql_queries():
    queries: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", listener)
    try:
        yield queries
    finally:
        event.remove(engine, "before_cursor_execute", listener)


@pytest.mark.parametrize("bad_url", [
    "javascript:alert(1)", "JAVASCRIPT:void(0)", "data:text/html,<svg>", "data:image/png;base64,abc", "file:///etc/passwd", "ftp://a.vn",
])
def test_validate_website_and_media_reject_unsafe_urls(bad_url):
    with pytest.raises(ValueError):
        validate_company_website(bad_url)
    with pytest.raises(ValueError):
        validate_company_media_url(bad_url)


def test_validate_valid_website_and_media_urls():
    assert normalize_search_text("  Đại Dương   ĐÔNG Á ") == "dai duong dong a"
    assert validate_company_website(None) is None
    assert validate_company_website("https://daiduonglabs.example.vn") == "https://daiduonglabs.example.vn"
    assert validate_company_media_url("https://cdn.example.vn/logo.png") == "https://cdn.example.vn/logo.png"
    assert validate_company_media_url("/uploads/logos/a.webp") == "/uploads/logos/a.webp"
    with pytest.raises(ValueError):
        validate_company_media_url("/uploads/../etc/passwd")


@pytest.mark.parametrize("q", [
    "ngan hang", "NGÂN HÀNG", "  ngan   hang  ", "dong a", "Đông Á", "  DONG   A ", "dai duong", "Đại Dương",
])
def test_search_normalization_finds_target_company(q):
    r = client.get("/api/companies", params={"q": q, "hiring": 0})
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "public, max-age=60"
    assert "dai-duong-digital-labs" in [x["slug"] for x in r.json()["items"]]


@pytest.mark.parametrize("payload", ["%", "_", "%_%", "' OR 1=1 --"])
def test_search_sql_wildcard_and_injection_safe(payload):
    r = client.get("/api/companies", params={"q": payload, "hiring": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0 and body["items"] == []


@pytest.mark.parametrize("params", [{"page": 0}, {"page": -1}, {"page": -5}, {"page_size": 49}, {"page_size": 0}])
def test_pagination_invalid_params_return_422(params):
    assert client.get("/api/companies", params=params).status_code == 422


def test_pagination_overflow_hiring_facets_and_no_pii():
    r_over = client.get("/api/companies", params={"page": 999, "hiring": 0})
    assert r_over.status_code == 200 and r_over.json()["items"] == []

    r_hiring = client.get("/api/companies", params={"hiring": 1, "page_size": 48}).json()
    hiring_slugs = [c["slug"] for c in r_hiring["items"]]
    assert "phan-mem-nhung-hai-dang" not in hiring_slugs
    assert "cong-ty-noi-bo-an" not in hiring_slugs

    r_all = client.get("/api/companies", params={"hiring": 0, "page_size": 48, "sort": "recent"}).json()
    assert "phan-mem-nhung-hai-dang" in [c["slug"] for c in r_all["items"]]
    assert r_all["items"][-1]["open_jobs"] == 0

    for item in r_all["items"]:
        for key in FORBIDDEN_PII_KEYS:
            assert key not in item

    for facet_list in r_all["facets"].values():
        assert all(f["count"] >= 0 for f in facet_list)
    assert sum(f["count"] for f in r_all["facets"]["industry"]) == r_all["total"]


@pytest.mark.parametrize("suffix", ["", "/jobs"])
def test_hidden_and_missing_company_identical_404(suffix):
    r_hidden = client.get(f"/api/companies/cong-ty-noi-bo-an{suffix}")
    r_missing = client.get(f"/api/companies/khong-ton-tai-xyz-999{suffix}")
    assert r_hidden.status_code == 404 and r_missing.status_code == 404
    assert r_hidden.text == r_missing.text
    assert r_hidden.json() == r_missing.json()


def test_salary_range_top_skills_similar_and_no_pii_detail():
    r0 = client.get("/api/companies/an-ninh-mang-lam-son").json()
    assert r0["salary_range"] is None and r0["open_jobs"] >= 2

    r1 = client.get("/api/companies/tu-dong-hoa-kiem-thu-anh-duong").json()
    assert r1["salary_range"] is None and r1["open_jobs"] == 2

    r2 = client.get("/api/companies/dai-duong-digital-labs")
    assert r2.status_code == 200 and r2.headers.get("cache-control") == "public, max-age=60"
    d2 = r2.json()
    assert d2["salary_range"] is not None and d2["salary_range"]["sample_size"] >= 2
    sim_slugs = [s["slug"] for s in d2["similar"]]
    assert d2["slug"] not in sim_slugs
    assert "cong-ty-noi-bo-an" not in sim_slugs
    for key in FORBIDDEN_PII_KEYS:
        assert key not in d2

    r2_again = client.get("/api/companies/dai-duong-digital-labs").json()
    assert d2["top_skills"] == r2_again["top_skills"]
    assert len(d2["top_skills"]) <= 8

    rj = client.get("/api/companies/dai-duong-digital-labs/jobs", params={"sort": "salary"})
    assert rj.status_code == 200 and rj.headers.get("cache-control") == "public, max-age=60"
    assert rj.json()["total"] == d2["open_jobs"]


def test_sql_query_count_no_n_plus_1():
    pcs._SKILL_MAP_CACHE = None
    with count_sql_queries() as q_list_12:
        r_list_12 = client.get("/api/companies", params={"page_size": 12, "hiring": 0})
    assert r_list_12.status_code == 200
    assert len(q_list_12) <= 6, f"Expected <=6 SQL queries for list, got {len(q_list_12)}: {q_list_12}"

    with count_sql_queries() as q_list_3:
        r_list_3 = client.get("/api/companies", params={"page_size": 3, "hiring": 0})
    assert r_list_3.status_code == 200
    assert len(q_list_3) <= 6 and len(q_list_3) <= len(q_list_12)

    pcs._SKILL_MAP_CACHE = None
    with count_sql_queries() as q_detail:
        r_detail = client.get("/api/companies/dai-duong-digital-labs")
    assert r_detail.status_code == 200
    assert len(q_detail) <= 8, f"Expected <=8 SQL queries for detail, got {len(q_detail)}: {q_detail}"
