import json
import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.db.session import Base
from app.models.company import Company, CompanyStatus
from app.models.job import Job, MetaSkill
from app.services.skill_sync_service import recalculate_all_skill_counts, sync_skills_from_job


class SkillSyncServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

        self.company = Company(
            employer_id=1,
            name="Tech Corp",
            status=CompanyStatus.VERIFIED,
            verification_status="da_xac_minh",
            is_verified=True,
            is_visible=True,
        )
        self.db.add(self.company)
        self.db.commit()
        self.db.refresh(self.company)

    def tearDown(self):
        self.db.close()

    def test_recalculate_all_skill_counts_with_real_jobs(self):
        # 1. Thêm các job với kỹ năng khác nhau
        j1 = Job(
            employer_id=1,
            company_id=self.company.id,
            title="Senior Python Engineer",
            status="published",
            deadline=date.today() + timedelta(days=10),
            skills=["Python", "FastAPI", "Docker"],
        )
        j2 = Job(
            employer_id=1,
            company_id=self.company.id,
            title="Frontend React Developer",
            status="published",
            deadline=date.today() + timedelta(days=10),
            skills=["React", "TypeScript", "Docker"],
        )
        # Job đã hết hạn -> Không được tính
        j_expired = Job(
            employer_id=1,
            company_id=self.company.id,
            title="Expired Python Job",
            status="published",
            deadline=date.today() - timedelta(days=1),
            skills=["Python"],
        )
        # Job nháp (draft) -> Không được tính
        j_draft = Job(
            employer_id=1,
            company_id=self.company.id,
            title="Draft Python Job",
            status="draft",
            deadline=date.today() + timedelta(days=10),
            skills=["Python"],
        )
        self.db.add_all([j1, j2, j_expired, j_draft])
        self.db.commit()

        # 2. Chạy recalculate
        counts = recalculate_all_skill_counts(self.db)

        # 3. Khẳng định số lượng chính xác:
        # Docker: 2 tin (j1, j2)
        # Python: 1 tin (chỉ j1)
        # FastAPI: 1 tin (chỉ j1)
        # React: 1 tin (chỉ j2)
        # TypeScript: 1 tin (chỉ j2)
        self.assertEqual(counts.get("Docker"), 2)
        self.assertEqual(counts.get("Python"), 1)
        self.assertEqual(counts.get("React"), 1)
        self.assertEqual(counts.get("FastAPI"), 1)
        self.assertEqual(counts.get("TypeScript"), 1)

        # 4. Kiểm tra bảng meta_skills đã được tự động thêm và cập nhật
        docker_meta = self.db.query(MetaSkill).filter_by(name="Docker").first()
        self.assertIsNotNone(docker_meta)
        self.assertEqual(docker_meta.usage_count, 2)

    def test_sync_skills_from_job_inserts_new_skills(self):
        sync_skills_from_job(self.db, ["Golang", "Kubernetes", "golang "])
        self.db.commit()

        golang_meta = self.db.query(MetaSkill).filter_by(name="Golang").first()
        k8s_meta = self.db.query(MetaSkill).filter_by(name="Kubernetes").first()
        self.assertIsNotNone(golang_meta)
        self.assertIsNotNone(k8s_meta)
        # Không bị trùng lặp golang
        all_golang = self.db.query(MetaSkill).filter(MetaSkill.name.ilike("Golang")).all()
        self.assertEqual(len(all_golang), 1)

    def test_lifecycle_job_skills_sync_and_recalculate(self):
        # 1. Nhà tuyển dụng tạo tin mới với kỹ năng "Next.js"
        j = Job(
            employer_id=1,
            company_id=self.company.id,
            title="Fullstack Next.js Dev",
            status="published",
            deadline=date.today() + timedelta(days=7),
            skills=["Next.js", "TypeScript"],
        )
        self.db.add(j)
        sync_skills_from_job(self.db, j.skills)
        recalculate_all_skill_counts(self.db)

        nextjs_meta = self.db.query(MetaSkill).filter_by(name="Next.js").first()
        ts_meta = self.db.query(MetaSkill).filter_by(name="TypeScript").first()
        self.assertIsNotNone(nextjs_meta)
        self.assertEqual(nextjs_meta.usage_count, 1)
        self.assertEqual(ts_meta.usage_count, 1)

        # 2. Sửa tin: chuyển từ "Next.js" sang "Vue"
        j.skills = ["Vue", "TypeScript"]
        sync_skills_from_job(self.db, j.skills)
        recalculate_all_skill_counts(self.db)

        self.db.refresh(nextjs_meta)
        self.assertEqual(nextjs_meta.usage_count, 0)  # Next.js không còn tin nào
        vue_meta = self.db.query(MetaSkill).filter_by(name="Vue").first()
        self.assertIsNotNone(vue_meta)
        self.assertEqual(vue_meta.usage_count, 1)

        # 3. Đóng tin hoặc xóa tin
        j.status = "closed"
        recalculate_all_skill_counts(self.db)
        self.db.refresh(vue_meta)
        self.assertEqual(vue_meta.usage_count, 0)  # Vue về 0 vì tin đã đóng



if __name__ == "__main__":
    unittest.main()
