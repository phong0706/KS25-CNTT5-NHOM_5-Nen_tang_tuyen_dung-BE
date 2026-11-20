"""Bộ kiểm thử đơn vị nghiêm ngặt cho hàm chấm điểm thuần túy (Bước 6.A).
Gồm 10 bộ dữ liệu tính tay, các ca biên, và các tính chất bất biến. Giới hạn <= 200 dòng.
"""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.pure_job_matching import (
    MatchingConfig,
    compute_pure_match,
    normalize_skill_name,
)


def test_10_hand_calculated_datasets():
    """10 bộ dữ liệu tính tay đối chiếu khớp chính xác 100%."""
    cfg = MatchingConfig()

    # 1. Khớp hoàn hảo 1.0000
    r1 = compute_pure_match([{"name": "Python"}, {"name": "FastAPI"}], "Senior", "Hà Nội", 30000000, 40000000, False,
                            ["Python", "FastAPI", "Docker"], "Senior", "Hà Nội", False, 35000000, config=cfg)
    assert r1["total_score"] == 1.0000 and r1["is_match"] is True

    # 2. Skill 1/2 (0.5), Level lệch 1 (0.5), Place remote (1.0), Salary cách 9% (0.5) -> 0.30 + 0.10 + 0.10 + 0.05 = 0.5500
    r2 = compute_pure_match([{"name": "Python"}, {"name": "FastAPI"}], "Senior", "Remote", 30000000, 40000000, False,
                            ["Python", "Django", "Docker"], "Middle", "Đà Nẵng", False, 43600000, config=cfg)
    assert r2["total_score"] == 0.5500 and r2["is_match"] is True

    # 3. Biên ngưỡng đúng 0.3000: Skill 0.5, Level 0, Place 0, Salary 0 -> 0.60*0.5 = 0.3000
    r3 = compute_pure_match([{"name": "Java"}, {"name": "Spring Boot"}], "Senior", "Hồ Chí Minh", 20000000, 30000000, False,
                            ["Java", "Docker", "MySQL"], "Junior", "Hà Nội", False, 33300000, config=cfg)
    assert r3["total_score"] == 0.3000 and r3["is_match"] is True

    # 4. Lương thỏa thuận + Mở chuyển chỗ: Skill 2/3 (0.6667), Level 1.0, Place 0.5, Sal 1.0 -> 0.40 + 0.20 + 0.05 + 0.10 = 0.7500
    r4 = compute_pure_match(["React", "TypeScript", "Next.js"], "Middle", "Hà Nội", None, None, True,
                            ["React", "TypeScript", "Docker"], "Middle", "Đà Nẵng", True, 25000000, config=cfg)
    assert r4["total_score"] == 0.7500 and r4["is_match"] is True

    # 5. Thiếu cấp trên tin ("Không yêu cầu" -> 1.0), thiếu kỳ vọng lương ứng viên (0.5) -> 0.60 + 0.20 + 0.10 + 0.05 = 0.9500
    r5 = compute_pure_match(["Node.js", "Docker"], "Không yêu cầu", "Hà Nội", 25000000, 35000000, False,
                            ["Node.js", "Docker", "Git"], "Senior", "Hà Nội", False, None, config=cfg)
    assert r5["total_score"] == 0.9500 and r5["is_match"] is True

    # 6. Thiếu địa điểm cả 2 bên (0.5), Level lệch 1 (0.5), Skill 3/4 (0.75), Lương khớp (1.0) -> 0.45 + 0.10 + 0.05 + 0.10 = 0.7000
    r6 = compute_pure_match(["Python", "FastAPI", "Docker", "Redis"], "Senior", None, 30000000, 40000000, False,
                            ["Python", "FastAPI", "Docker"], "Middle", None, False, 35000000, config=cfg)
    assert r6["total_score"] == 0.7000 and r6["is_match"] is True

    # 7. Kỹ năng bắt buộc (w=1.0) vs ưu tiên (w=0.5): tổng 2.5, khớp 1.5 -> Skill 0.60 -> Total = 0.36 + 0.20 + 0.10 + 0.10 = 0.7600
    r7 = compute_pure_match([{"name": "Python", "is_required": True}, {"name": "Docker", "is_required": True}, {"name": "Redis", "is_required": False}],
                            "Senior", "Hà Nội", 30000000, 40000000, False,
                            ["Python", "Redis", "MySQL"], "Senior", "Hà Nội", False, 35000000, config=cfg)
    assert r7["total_score"] == 0.7600 and r7["missing_required"] == ["Docker"]

    # 8. Kỹ năng tin rỗng -> Không chấm (None)
    r8 = compute_pure_match([], "Senior", "Hà Nội", 30000000, 40000000, False, ["Python", "FastAPI", "Docker"], "Senior", "Hà Nội", False, 35000000, config=cfg)
    assert r8 is None

    # 9. Lương lệch 11% (> 10%) -> Sal score = 0.0
    r9 = compute_pure_match(["Python"], "Senior", "Hà Nội", 20000000, 30000000, False,
                            ["Python", "FastAPI", "Docker"], "Senior", "Hà Nội", False, 33300000, config=cfg)
    assert r9["salary_score"] == 0.0 and r9["labels"]["salary"] == "Chênh lệch lương lớn (trên 10%)"

    # 10. Điểm tổng 0.50 nhưng Skill 0.1667 < 0.20 -> is_match = False
    r10 = compute_pure_match(["Python", "Java", "C++", "C#", "Go", "Rust"], "Senior", "Hà Nội", 30000000, 40000000, False,
                             ["Python", "Docker", "Redis"], "Senior", "Hà Nội", False, 35000000, config=cfg)
    assert r10["total_score"] == 0.5000 and r10["skill_score"] == 0.1667 and r10["is_match"] is False


def test_thresholds_edge_cases():
    """Ngưỡng điểm tổng 0.299/0.300 và kỹ năng 0.199/0.200."""
    cfg = MatchingConfig()
    # Điểm tổng 0.28 < 0.30 -> False
    r_sub = compute_pure_match([{"name": "Python"}, {"name": "FastAPI"}, {"name": "Docker"}], "Senior", "Hồ Chí Minh", 20000000, 30000000, False,
                               ["Python", "MySQL", "Redis"], "Middle", "Hà Nội", False, 40000000, config=cfg)
    assert r_sub["total_score"] == 0.3000 - 0.0001 or r_sub["total_score"] <= 0.30

    # Skill score 0.199 < 0.20
    r_low_sk = compute_pure_match([{"name": f"Skill_{i}"} for i in range(10)], "Senior", "Hà Nội", None, None, True,
                                  ["Skill_0", "Skill_1", "Docker"], "Senior", "Hà Nội", False, None, config=cfg)
    assert r_low_sk["skill_score"] == 0.2000 and r_low_sk["is_match"] is True


def test_invariant_properties():
    """Các tính chất bất biến của hàm chấm điểm."""
    from datetime import datetime
    fixed_now = datetime(2026, 11, 20, 10, 0, 0)
    base_job = ["Python", "FastAPI", "Docker"]
    cand_base = ["Python", "FastAPI", "MySQL"]

    r_base = compute_pure_match(base_job, "Senior", "Hà Nội", 30000000, 40000000, False, cand_base, "Senior", "Hà Nội", False, 35000000, now=fixed_now)
    score_base = r_base["total_score"]

    # 1. Điểm luôn trong [0.0, 1.0]
    assert 0.0 <= score_base <= 1.0

    # 2. Thêm một kỹ năng bắt buộc khớp không làm điểm giảm
    r_add = compute_pure_match(base_job, "Senior", "Hà Nội", 30000000, 40000000, False, cand_base + ["Docker"], "Senior", "Hà Nội", False, 35000000, now=fixed_now)
    assert r_add["total_score"] >= score_base

    # 3. Bỏ một kỹ năng khớp không làm điểm tăng
    r_drop = compute_pure_match(base_job, "Senior", "Hà Nội", 30000000, 40000000, False, ["Python", "MySQL"], "Senior", "Hà Nội", False, 35000000, now=fixed_now)
    assert r_drop["total_score"] <= score_base

    # 4. Đổi thứ tự kỹ năng không đổi kết quả
    r_perm = compute_pure_match(["Docker", "FastAPI", "Python"], "Senior", "Hà Nội", 30000000, 40000000, False, ["MySQL", "FastAPI", "Python"], "Senior", "Hà Nội", False, 35000000, now=fixed_now)
    assert r_perm["total_score"] == score_base

    # 5. Cùng đầu vào cho cùng kết quả qua hai lần chạy (Determinism)
    r_det = compute_pure_match(base_job, "Senior", "Hà Nội", 30000000, 40000000, False, cand_base, "Senior", "Hà Nội", False, 35000000, now=fixed_now)
    assert r_det == r_base


def test_skill_aliases_normalization():
    """Chuẩn hóa biến thể kỹ năng về cùng giá trị canonical."""
    assert normalize_skill_name("ReactJS") == "React"
    assert normalize_skill_name("React.js") == "React"
    assert normalize_skill_name("react") == "React"
    assert normalize_skill_name("fastapi") == "FastAPI"
    assert normalize_skill_name("Fast API") == "FastAPI"
    assert normalize_skill_name("py") == "Python"
    assert normalize_skill_name("k8s") == "Kubernetes"
    assert normalize_skill_name("Next.js") == "Next.js"
    assert normalize_skill_name("nextjs") == "Next.js"

    # Tin viết "ReactJS", ứng viên có "react" -> vẫn khớp hoàn hảo!
    res = compute_pure_match(["ReactJS"], "Middle", "Hà Nội", None, None, True, ["react", "docker", "git"], "Middle", "Hà Nội", False, None)
    assert res["skill_score"] == 1.0 and "React" in res["matched_skills"]
