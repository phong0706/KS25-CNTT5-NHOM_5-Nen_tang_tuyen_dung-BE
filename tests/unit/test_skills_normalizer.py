"""test_skills_normalizer.py
Unit tests cho hàm normalize_skills theo yêu cầu:
- str tách theo [,;|]
- list chuẩn hóa
- None, chuỗi rỗng
- trùng lặp (dedup)
- quá dài (cắt tối đa 8 skills, cắt ký tự)
- ký tự lạ
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from app.services.skills_normalizer import normalize_skills


def test_normalize_skills_none_and_empty():
    assert normalize_skills(None) == []
    assert normalize_skills("") == []
    assert normalize_skills("   ") == []
    assert normalize_skills([]) == []
    assert normalize_skills(False) == []


def test_normalize_skills_from_string():
    # Chuỗi dấu phẩy
    assert normalize_skills("Python, Kubernetes, Docker, Rust") == ["Python", "Kubernetes", "Docker", "Rust"]
    # Chuỗi dấu chấm phẩy và pipe
    assert normalize_skills("Java; Spring Boot | PostgreSQL / Kafka") == ["Java", "Spring Boot", "PostgreSQL", "Kafka"]
    # Xuống dòng và tab
    assert normalize_skills("React\nTypeScript\tNode.js\rGraphQL") == ["React", "TypeScript", "Node.js", "GraphQL"]


def test_normalize_skills_deduplication():
    # Trùng lặp hoa thường
    assert normalize_skills("Python, python, PYTHON, Rust, rust") == ["Python", "Rust"]
    assert normalize_skills(["Java", "java", "Go", "GO", "go"]) == ["Java", "Go"]


def test_normalize_skills_max_eight():
    # Quá 8 kỹ năng -> chỉ lấy tối đa 8 kỹ năng đầu
    long_list = ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5", "Skill6", "Skill7", "Skill8", "Skill9", "Skill10"]
    result = normalize_skills(long_list)
    assert len(result) == 8
    assert result == ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5", "Skill6", "Skill7", "Skill8"]


def test_normalize_skills_strip_strange_characters():
    # Ký tự lạ quanh từ
    raw = " • Python , #Kubernetes* , 'Docker' , \"Figma\" , `Rust` "
    assert normalize_skills(raw) == ["Python", "Kubernetes", "Docker", "Figma", "Rust"]


def test_normalize_skills_list_with_strings_and_inner_delimiters():
    # Danh sách có phần tử chứa dấu phân cách
    raw = ["Python, Docker", "Kubernetes; AWS", "React"]
    assert normalize_skills(raw) == ["Python", "Docker", "Kubernetes", "AWS", "React"]
