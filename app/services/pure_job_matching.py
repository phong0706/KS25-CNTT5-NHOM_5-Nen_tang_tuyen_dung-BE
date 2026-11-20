"""Module thuần chấm điểm phù hợp việc làm (Matching Engine Pure).
Quy tắc: thuần túy không truy cập DB/I/O, <= 200 dòng, không chia cho 0, điểm 0-1.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

LEVEL_RANKS: dict[str, int] = {
    "intern": 1, "thực tập": 1, "thực tập sinh": 1,
    "fresher": 2, "mới tốt nghiệp": 2,
    "junior": 3, "sơ cấp": 3,
    "middle": 4, "mid": 4, "chuyên viên": 4,
    "senior": 5, "cao cấp": 5,
    "lead": 6, "trưởng nhóm": 6, "manager": 6, "quản lý": 6, "director": 6, "giám đốc": 6,
}

COMPREHENSIVE_ALIASES: dict[str, str] = {
    "py": "Python", "python": "Python", "python3": "Python", "fastapi": "FastAPI", "fast api": "FastAPI",
    "django": "Django", "drf": "Django", "flask": "Flask", "js": "JavaScript", "javascript": "JavaScript", "es6": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript", "react": "React", "reactjs": "React", "react.js": "React",
    "next": "Next.js", "nextjs": "Next.js", "next.js": "Next.js", "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js", "nest": "NestJS", "nestjs": "NestJS", "nest.js": "NestJS",
    "java": "Java", "spring": "Spring Boot", "springboot": "Spring Boot", "spring boot": "Spring Boot",
    "docker": "Docker", "k8s": "Kubernetes", "kubernetes": "Kubernetes", "mysql": "MySQL", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "redis": "Redis", "mongodb": "MongoDB", "mongo": "MongoDB", "aws": "AWS", "gcp": "Google Cloud", "azure": "Azure",
    "git": "Git", "cicd": "CI/CD", "ci/cd": "CI/CD", "go": "Golang", "golang": "Golang", "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#", ".net": ".NET", "dotnet": ".NET", "php": "PHP", "laravel": "Laravel", "flutter": "Flutter",
    "react native": "React Native", "reactnative": "React Native", "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS", "tailwind css": "Tailwind CSS",
    "graphql": "GraphQL", "redux": "Redux", "linux": "Linux",
}


@dataclass(frozen=True)
class MatchingConfig:
    version: str = "v1.0"
    w_skill: float = 0.60
    w_level: float = 0.20
    w_place: float = 0.10
    w_salary: float = 0.10
    min_total_score: float = 0.30
    min_skill_score: float = 0.20
    min_candidate_skills: int = 3
    salary_tolerance_pct: float = 0.10


DEFAULT_CONFIG = MatchingConfig()


def normalize_skill_name(raw: str, alias_map: dict[str, str] | None = None) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    k = s.lower()
    if alias_map and k in alias_map:
        return alias_map[k]
    if k in COMPREHENSIVE_ALIASES:
        return COMPREHENSIVE_ALIASES[k]
    return s


def parse_job_skills_input(raw_skills: Any, alias_map: dict[str, str] | None = None) -> list[tuple[str, bool]]:
    if not raw_skills:
        return []
    items: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for item in raw_skills:
        name = ""
        is_req = True
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("skill_name") or "")
            is_req = bool(item.get("is_required", True))
        elif isinstance(item, str):
            name = item
        norm = normalize_skill_name(name, alias_map)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            items.append((norm, is_req))
    return items


def compute_skill_component(job_skills_parsed: list[tuple[str, bool]], cand_skills_norm: set[str]) -> tuple[float, list[str], list[str]]:
    if not job_skills_parsed:
        return 0.0, [], []
    total_w = 0.0
    matched_w = 0.0
    matched: list[str] = []
    missing_req: list[str] = []

    for name, is_req in job_skills_parsed:
        w = 1.0 if is_req else 0.5
        total_w += w
        if name.lower() in cand_skills_norm:
            matched_w += w
            matched.append(name)
        elif is_req:
            missing_req.append(name)

    score = round(matched_w / total_w, 4) if total_w > 0 else 0.0
    return min(1.0, max(0.0, score)), matched, missing_req[:3]


def compute_level_component(job_level: str | None, cand_level: str | None) -> tuple[float, str]:
    if not job_level or job_level.strip().lower() in ("tất cả", "all", "không yêu cầu", "không giới hạn"):
        return 1.0, "Phù hợp mọi cấp bậc"
    if not cand_level:
        return 0.5, "Chưa xác định cấp bậc"
    j_rank = next((v for k, v in LEVEL_RANKS.items() if k in job_level.lower()), None)
    c_rank = next((v for k, v in LEVEL_RANKS.items() if k in cand_level.lower()), None)
    if j_rank is None or c_rank is None:
        return 0.5, "Chưa xác định cấp bậc"
    diff = abs(c_rank - j_rank)
    if diff == 0:
        return 1.0, "Đúng cấp bậc"
    if diff == 1:
        return 0.5, "Lệch 1 cấp bậc"
    return 0.0, "Không khớp cấp bậc"


def compute_place_component(job_loc: str | None, cand_loc: str | None, open_to_relocate: bool) -> tuple[float, str]:
    if not job_loc and not cand_loc:
        return 0.5, "Chưa xác định địa điểm"
    if job_loc and any(k in job_loc.lower() for k in ("toàn quốc", "remote", "từ xa")):
        return 1.0, "Làm việc từ xa / Toàn quốc"
    if not job_loc or not cand_loc:
        return 0.5, "Chưa xác định địa điểm"
    jl = job_loc.lower().strip()
    cl = cand_loc.lower().strip()
    if cl in jl or jl in cl or any(w in jl for w in cl.split()):
        return 1.0, "Cùng địa điểm"
    if open_to_relocate:
        return 0.5, "Sẵn sàng chuyển chỗ"
    return 0.0, "Khác địa điểm"


def compute_salary_component(s_min: int | None, s_max: int | None, is_nego: bool, expected: int | None, tol_pct: float) -> tuple[float, str]:
    if is_nego or (not s_min and not s_max):
        return 1.0, "Lương thỏa thuận"
    if expected is None or expected <= 0:
        return 0.5, "Chưa đặt kỳ vọng lương"
    low = s_min or 0
    high = s_max or float("inf")
    if low <= expected <= high:
        return 1.0, "Mức lương phù hợp"
    diff_pct = ((low - expected) / low) if expected < low else ((expected - high) / high)
    if diff_pct <= tol_pct:
        return 0.5, "Chênh lệch lương nhỏ (dưới 10%)"
    return 0.0, "Chênh lệch lương lớn (trên 10%)"


def compute_pure_match(
    job_skills: list[Any],
    job_level: str | None,
    job_location: str | None,
    job_salary_min: int | None,
    job_salary_max: int | None,
    job_is_negotiable: bool,
    cand_skills: list[str],
    cand_level: str | None,
    cand_location: str | None,
    cand_open_to_relocate: bool,
    cand_expected_salary: int | None,
    *,
    config: MatchingConfig = DEFAULT_CONFIG,
    alias_map: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    parsed_js = parse_job_skills_input(job_skills, alias_map)
    if not parsed_js:
        return None  # Kỹ năng tin rỗng: không chấm

    cand_set = {normalize_skill_name(s, alias_map).lower() for s in cand_skills if s and s.strip()}
    s_skill, matched, missing_req = compute_skill_component(parsed_js, cand_set)
    s_level, l_label = compute_level_component(job_level, cand_level)
    s_place, p_label = compute_place_component(job_location, cand_location, cand_open_to_relocate)
    s_salary, sal_label = compute_salary_component(job_salary_min, job_salary_max, job_is_negotiable, cand_expected_salary, config.salary_tolerance_pct)

    total = round(
        config.w_skill * s_skill + config.w_level * s_level + config.w_place * s_place + config.w_salary * s_salary, 4
    )
    total_clamped = min(1.0, max(0.0, total))
    is_match = (total_clamped >= config.min_total_score) and (s_skill >= config.min_skill_score)

    return {
        "total_score": total_clamped,
        "is_match": is_match,
        "skill_score": s_skill,
        "level_score": s_level,
        "place_score": s_place,
        "salary_score": s_salary,
        "matched_skills": matched,
        "missing_required": missing_req,
        "labels": {
            "level": l_label,
            "place": p_label,
            "salary": sal_label,
            "summary": f"Khớp {len(matched)}/{len(parsed_js)} kỹ năng",
        },
        "formula_version": config.version,
        "computed_at": (now or datetime.now()).isoformat(),
    }
