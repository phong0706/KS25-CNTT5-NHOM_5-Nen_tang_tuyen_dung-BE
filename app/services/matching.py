"""Module thuần tính điểm phù hợp việc làm (Matching Engine).
Tuân thủ techrecruit-rules: thuần túy không phụ thuộc framework, < 200 dòng, không chia cho 0, điểm 0-100.
"""
import re

LEVEL_RANKS = {
    "intern": 1, "thực tập": 1, "thực tập sinh": 1,
    "fresher": 2, "junior": 2, "mới đi làm": 2,
    "middle": 3, "mid": 3, "chuyên viên": 3,
    "senior": 4, "cao cấp": 4,
    "lead": 5, "trưởng nhóm": 5, "manager": 5, "quản lý": 5, "director": 5,
}

BUILTIN_ALIASES = {
    "py": "Python", "python": "Python", "python3": "Python",
    "fastapi": "FastAPI", "fast api": "FastAPI",
    "django": "Django", "drf": "Django",
    "flask": "Flask",
    "js": "JavaScript", "javascript": "JavaScript", "es6": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "react": "React", "reactjs": "React", "react.js": "React",
    "vue": "Vue", "vuejs": "Vue", "vue.js": "Vue",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "java": "Java", "spring": "Spring Boot", "springboot": "Spring Boot",
    "docker": "Docker", "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "mysql": "MySQL", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "redis": "Redis", "aws": "AWS", "git": "Git", "cicd": "CI/CD", "ci/cd": "CI/CD",
    "go": "Golang", "golang": "Golang", "c++": "C++", "cpp": "C++",
    "c#": "C#", "csharp": "C#", ".net": ".NET", "dotnet": ".NET",
    "php": "PHP", "laravel": "Laravel", "flutter": "Flutter",
    "kotlin": "Kotlin", "swift": "Swift", "html": "HTML/CSS", "css": "HTML/CSS",
    "html/css": "HTML/CSS", "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "graphql": "GraphQL", "mongo": "MongoDB", "mongodb": "MongoDB",
    "kafka": "Kafka", "linux": "Linux",
}


def normalize_skill(skill: str, alias_map: dict[str, str] | None = None) -> str:
    s = (skill or "").strip()
    if not s:
        return ""
    key = s.lower()
    if alias_map and key in alias_map:
        return alias_map[key]
    if key in BUILTIN_ALIASES:
        return BUILTIN_ALIASES[key]
    return s.title() if len(s) > 3 and s.islower() else s


def normalize_skill_list(skills: list[str] | set[str] | None, alias_map: dict[str, str] | None = None) -> list[str]:
    if not skills:
        return []
    res: list[str] = []
    seen: set[str] = set()
    for s in skills:
        norm = normalize_skill(s, alias_map)
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            res.append(norm)
    return res


def compute_level_score(cand_level: str | None, job_level: str | None) -> int:
    if not cand_level or not job_level:
        return 8
    cl, jl = cand_level.strip().lower(), job_level.strip().lower()
    if jl in ("tất cả", "all", "không yêu cầu") or cl == jl:
        return 15
    crank = next((v for k, v in LEVEL_RANKS.items() if k in cl), None)
    jrank = next((v for k, v in LEVEL_RANKS.items() if k in jl), None)
    if crank is None or jrank is None:
        return 8
    diff = abs(crank - jrank)
    if diff == 0:
        return 15
    if diff == 1:
        return 10
    return 0


def compute_location_worktype_score(cand_loc: str | None, cand_wt: str | None, job_loc: str | None, job_wt: str | None) -> int:
    loc_score = 5
    if job_loc:
        jl = job_loc.lower()
        if any(kw in jl for kw in ("toàn quốc", "remote", "từ xa")) or (job_wt and "remote" in job_wt.lower()):
            loc_score = 10
        elif cand_loc:
            cl = cand_loc.lower()
            loc_score = 10 if (cl in jl or jl in cl or any(p in jl for p in cl.split())) else 0

    wt_score = 3
    if job_wt:
        jw = job_wt.lower()
        if any(kw in jw for kw in ("linh hoạt", "hybrid", "tất cả")):
            wt_score = 5
        elif cand_wt:
            cw = cand_wt.lower()
            wt_score = 5 if (cw in jw or jw in cw) else 0

    return loc_score + wt_score


def compute_salary_score(expected_salary: int | None, salary_min: int | None, salary_max: int | None, is_negotiable: bool = False) -> int:
    if is_negotiable or expected_salary is None or expected_salary <= 0 or (not salary_min and not salary_max):
        return 10
    if salary_max and salary_max > 0:
        if expected_salary <= salary_max:
            return 10
        if expected_salary <= salary_max * 1.2:
            return 5
        return 0
    if salary_min and salary_min > 0:
        return 10 if expected_salary >= salary_min * 0.8 else 5
    return 10


def compute_job_match(candidate: dict, job: dict, alias_map: dict[str, str] | None = None) -> dict:
    cand_skills = normalize_skill_list(candidate.get("skills", []), alias_map)
    job_skills = normalize_skill_list(job.get("skills", []), alias_map)

    cand_set = {s.lower(): s for s in cand_skills}
    matched: list[str] = []
    missing: list[str] = []

    for js in job_skills:
        if js.lower() in cand_set:
            matched.append(js)
        else:
            missing.append(js)

    if not job_skills:
        skills_score = 60
        reason = "Tin không yêu cầu kỹ năng cụ thể"
    else:
        ratio = len(matched) / len(job_skills)
        skills_score = int(round(ratio * 60))
        reason = f"Khớp {len(matched)}/{len(job_skills)} kỹ năng"

    cand_level = candidate.get("level")
    if not cand_level and candidate.get("headline"):
        hl = candidate["headline"].lower()
        cand_level = next((k for k in LEVEL_RANKS if k in hl), None)

    level_score = compute_level_score(cand_level, job.get("level"))
    loc_wt_score = compute_location_worktype_score(
        candidate.get("location"), candidate.get("work_type"),
        job.get("location"), job.get("work_type")
    )
    sal_score = compute_salary_score(
        candidate.get("expected_salary"),
        job.get("salary_min"), job.get("salary_max"),
        bool(job.get("is_salary_negotiable"))
    )

    total_score = min(100, max(0, skills_score + level_score + loc_wt_score + sal_score))
    return {
        "match_score": total_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "reason": reason,
        "skills_score": skills_score,
        "level_score": level_score,
        "location_score": loc_wt_score,
        "salary_score": sal_score,
    }
