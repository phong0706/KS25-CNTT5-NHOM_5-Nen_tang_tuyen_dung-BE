import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_role_orientation_jobs_facets():
    res = client.get("/api/jobs?page=1&page_size=20")
    assert res.status_code == 200
    data = res.json()
    assert "facets" in data
    assert "category" in data["facets"]
    cats = data["facets"]["category"]
    assert len(cats) >= 5
    for c in cats:
        assert "value" in c
        assert "label" in c
        assert "count" in c
        assert c["count"] >= 0

def test_role_orientation_category_jobs():
    res = client.get("/api/jobs?category=frontend&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0
    for j in data["items"]:
        assert j["category_slug"] == "frontend"
        assert isinstance(j["skills"], list)
        assert not any(bad in j["title"].lower() for bad in ["mmmmmm", "valid engineer", "pending engineer"])
