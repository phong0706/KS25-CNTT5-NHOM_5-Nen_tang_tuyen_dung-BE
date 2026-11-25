"""
backend/tests/unit/test_route_uniqueness.py
Kiểm thử tính duy nhất của tất cả các route trong FastAPI app.
Không endpoint nào được phép có 2 handler khác nhau (shadowed routes).
"""
import pytest
from app.main import app

def test_no_duplicate_shadowed_routes():
    seen = {}
    duplicates = []
    
    for r in app.routes:
        if hasattr(r, "methods") and hasattr(r, "path"):
            for m in r.methods:
                key = (m, r.path)
                handler_name = f"{r.endpoint.__module__}.{r.endpoint.__name__}"
                if key in seen:
                    duplicates.append({
                        "method": m,
                        "path": r.path,
                        "first_handler": seen[key],
                        "shadowed_handler": handler_name
                    })
                else:
                    seen[key] = handler_name
                    
    assert len(duplicates) == 0, f"Found {len(duplicates)} shadowed routes: {duplicates}"
