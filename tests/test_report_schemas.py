from datetime import datetime
import unittest
from pydantic import ValidationError

from app.models.report import Report, ReportStatus
from app.schemas.report_schema import ReportActionIn, ReportCreate, ReportResponse


class ReportSchemaTests(unittest.TestCase):
    def test_report_reason_is_trimmed_and_bounded(self):
        report = ReportCreate(post_id=1, reason="  Sai thông tin công việc  ")
        self.assertEqual(report.reason, "Sai thông tin công việc")

        with self.assertRaises(ValidationError):
            ReportCreate(post_id=1, reason="     ")

        with self.assertRaises(ValidationError):
            ReportCreate(post_id=1, reason="x" * 2001)

    def test_report_action_requires_a_resolution_result(self):
        for status in ("RESOLVED", "REJECTED"):
            with self.subTest(status=status):
                action = ReportActionIn(status=status, resolution_result="  Đã xem xét  ")
                self.assertEqual(action.resolution_result, "Đã xem xét")

                with self.assertRaises(ValidationError):
                    ReportActionIn(status=status, resolution_result="   ")

    def test_report_action_rejects_pending_as_an_admin_decision(self):
        with self.assertRaises(ValidationError):
            ReportActionIn(status="PENDING", resolution_result="Chờ xử lý")

    def test_report_response_accepts_model_datetime(self):
        created_at = datetime(2026, 11, 17, 7, 0)
        report = Report(
            id=1,
            reporter_id=2,
            post_id=3,
            employer_id=4,
            reason="Sai thông tin công việc",
            status=ReportStatus.PENDING,
            created_at=created_at,
        )

        response = ReportResponse.model_validate(report)

        self.assertEqual(response.created_at, created_at)

if __name__ == "__main__":
    unittest.main()
