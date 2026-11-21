"""Kiểm thử API nhà tuyển dụng trên database riêng do tests/conftest.py cấu hình."""
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationStatusHistory, Interview
from app.models.candidate import CandidateProfile
from app.models.company import Company
from app.models.job import Job
from app.models.notification import Notification
from app.models.user import User
from app.routers import employer_applications
from app.services.notification import NotificationType


APPLICATIONS_URL = "/api/employer/applications"


@dataclass(frozen=True)
class ReviewData:
    recruiter_id: int
    candidate_id: int
    legacy_candidate_id: int
    job_id: int
    other_job_id: int
    foreign_job_id: int
    application_id: int
    legacy_application_id: int
    foreign_application_id: int

    @property
    def headers(self) -> dict[str, str]:
        return auth_headers(self.recruiter_id, "employer")


def auth_headers(user_id: int, role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def review_data():
    tag = uuid4().hex
    with SessionLocal.begin() as db:
        roles = ("employer", "employer", "candidate", "candidate")
        users = [
            User(
                email=f"review-{tag}-{i}@example.com", password="unused",
                full_name=f"Review test {i}", role=role,
            )
            for i, role in enumerate(roles)
        ]
        db.add_all(users)
        db.flush()
        user_ids = [user.id for user in users]
        recruiter_id, other_recruiter_id, candidate_id, legacy_candidate_id = user_ids

        company = Company(employer_id=recruiter_id, name=f"Review company {tag}")
        foreign_company = Company(employer_id=other_recruiter_id, name=f"Foreign company {tag}")
        profile = CandidateProfile(user_id=candidate_id)
        db.add_all([company, foreign_company, profile])
        db.flush()

        # Company ownership governs access even when the job creator differs.
        job = Job(employer_id=other_recruiter_id, company_id=company.id, title="Backend Engineer")
        other_job = Job(employer_id=recruiter_id, company_id=company.id, title="Data Engineer")
        foreign_job = Job(employer_id=recruiter_id, company_id=foreign_company.id, title="Foreign job")
        db.add_all([job, other_job, foreign_job])
        db.flush()

        application = Application(job_id=job.id, candidate_profile_id=profile.id, status="SUBMITTED")
        legacy_application = Application(
            job_id=job.id, candidate_id=legacy_candidate_id, cv_name_snapshot="CV.pdf", status="screening",
        )
        other_application = Application(job_id=other_job.id, candidate_profile_id=profile.id, status="SUBMITTED")
        foreign_application = Application(job_id=foreign_job.id, candidate_profile_id=profile.id, status="SUBMITTED")
        db.add_all([application, legacy_application, other_application, foreign_application])
        db.flush()
        data = ReviewData(
            recruiter_id, candidate_id, legacy_candidate_id, job.id, other_job.id, foreign_job.id,
            application.id, legacy_application.id, foreign_application.id,
        )

    try:
        yield data
    finally:
        with SessionLocal.begin() as db:
            db.execute(delete(User).where(User.id.in_(user_ids)))


def status_url(application_id: int) -> str:
    return f"{APPLICATIONS_URL}/{application_id}/status"


def history(db, application_id: int):
    return db.scalars(
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.id)
    ).all()


def notifications(db, application_id: int):
    return db.scalars(
        select(Notification)
        .where(Notification.entity_type == "application", Notification.entity_id == application_id)
        .order_by(Notification.id)
    ).all()


def test_list_by_company_job_and_status(client, review_data):
    data = review_data
    response = client.get(APPLICATIONS_URL, params={"job_id": data.job_id}, headers=data.headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {data.application_id, data.legacy_application_id}
    assert {job["id"] for job in body["jobs"]} == {data.job_id, data.other_job_id}

    for status, expected_id, expected_candidate in (
        ("SUBMITTED", data.application_id, data.candidate_id),
        ("REVIEWING", data.legacy_application_id, data.legacy_candidate_id),
        ("screening", data.legacy_application_id, data.legacy_candidate_id),
    ):
        response = client.get(
            APPLICATIONS_URL, params={"job_id": data.job_id, "status": status}, headers=data.headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 1
        [application] = response.json()["items"]
        assert application["id"] == expected_id
        assert application["candidate"]["id"] == expected_candidate


def test_foreign_company_cannot_list_or_update(client, review_data):
    data = review_data
    response = client.get(APPLICATIONS_URL, params={"job_id": data.foreign_job_id}, headers=data.headers)
    assert response.status_code == 404
    response = client.get(f"{APPLICATIONS_URL}/{data.foreign_application_id}", headers=data.headers)
    assert response.status_code == 404
    response = client.patch(
        status_url(data.foreign_application_id), json={"status": "REVIEWING", "note": "Unauthorized"},
        headers=data.headers,
    )
    assert response.status_code == 404
    with SessionLocal() as db:
        application = db.get(Application, data.foreign_application_id)
        assert application.status == "SUBMITTED"
        assert application.employer_notes is None
        assert not history(db, application.id)
        assert not notifications(db, application.id)


@pytest.mark.parametrize("role, expected_code", [(None, 401), ("candidate", 403)])
def test_both_endpoints_require_recruiter_role(client, review_data, role, expected_code):
    data = review_data
    headers = auth_headers(data.candidate_id, role) if role else {}
    listing = client.get(APPLICATIONS_URL, params={"job_id": data.job_id}, headers=headers)
    update = client.patch(status_url(data.application_id), json={"status": "REVIEWING"}, headers=headers)
    assert listing.status_code == expected_code
    assert update.status_code == expected_code


def test_rejects_note_longer_than_history_column(client, review_data):
    data = review_data
    response = client.patch(
        status_url(data.application_id), json={"status": "REVIEWING", "note": "a" * 501}, headers=data.headers,
    )
    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == "SUBMITTED"
        assert application.employer_notes is None
        assert not history(db, application.id)
        assert not notifications(db, application.id)


def test_scheduling_interview_requires_review_and_notifies_candidate(client, review_data):
    data = review_data
    url = f"{APPLICATIONS_URL}/{data.application_id}/interview"
    payload = {"scheduled_at": "2030-01-01T09:00:00+07:00"}

    response = client.post(url, json=payload, headers=data.headers)
    assert response.status_code == 409, response.text
    with SessionLocal.begin() as db:
        application = db.get(Application, data.application_id)
        assert application.status == "SUBMITTED"
        application.status = "REVIEWING"

    response = client.post(url, json=payload, headers=data.headers)
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == "INTERVIEW"
        interview = db.get(Interview, response.json()["interview_id"])
        assert interview.application_id == application.id
        [entry] = history(db, application.id)
        assert (entry.old_status, entry.new_status) == ("REVIEWING", "INTERVIEW")
        [message] = notifications(db, application.id)
        assert message.user_id == data.candidate_id
        assert message.type == NotificationType.INTERVIEW_SCHEDULED


@pytest.mark.parametrize("terminal_status", ["OFFERED", "REJECTED"])
def test_review_flow_persists_note_history_and_candidate_notification(client, review_data, terminal_status):
    data = review_data
    transitions = ["SUBMITTED", "REVIEWING", "INTERVIEW", terminal_status]
    notes = ["Review complete", "Interview recommended", "Interview decision"]
    url = status_url(data.application_id)
    for status, note in zip(transitions[1:], notes, strict=True):
        response = client.patch(url, json={"status": status, "note": note}, headers=data.headers)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    replay = client.patch(url, json={"status": terminal_status, "note": "Repeated update"}, headers=data.headers)
    assert replay.status_code == 409
    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == terminal_status
        assert application.employer_notes == notes[-1]
        assert [
            (item.old_status, item.new_status, item.note, item.changed_by_user_id)
            for item in history(db, application.id)
        ] == [
            (old, new, note, data.recruiter_id)
            for old, new, note in zip(transitions[:-1], transitions[1:], notes, strict=True)
        ]
        messages = notifications(db, application.id)
        assert [message.user_id for message in messages] == [data.candidate_id] * len(notes)
        assert all(message.type == NotificationType.APPLICATION_STATUS_CHANGED for message in messages)
        assert [json.loads(message.payload_json)["status"] for message in messages] == transitions[1:]


def test_legacy_application_progresses_and_notifies_user(client, review_data):
    data = review_data
    response = client.patch(
        status_url(data.legacy_application_id), json={"status": "interview", "note": "Schedule an interview"},
        headers=data.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "interview"
    with SessionLocal() as db:
        assert db.get(Application, data.legacy_application_id).status == "interview"
        [message] = notifications(db, data.legacy_application_id)
        assert message.user_id == data.legacy_candidate_id


@pytest.mark.parametrize(
    "old_status, allowed",
    [
        ("SUBMITTED", {"REVIEWING"}), ("REVIEWING", {"INTERVIEW"}),
        ("INTERVIEW", {"OFFERED", "REJECTED"}), ("OFFERED", set()),
        ("REJECTED", set()), ("WITHDRAWN", set()),
    ],
)
def test_invalid_transitions_have_no_side_effects(client, review_data, old_status, allowed):
    data = review_data
    with SessionLocal.begin() as db:
        db.get(Application, data.application_id).status = old_status

    statuses = {"SUBMITTED", "REVIEWING", "INTERVIEW", "OFFERED", "REJECTED", "WITHDRAWN"}
    for status in sorted(statuses - allowed):
        response = client.patch(
            status_url(data.application_id), json={"status": status, "note": "Invalid transition"},
            headers=data.headers,
        )
        assert response.status_code == 409, (old_status, status, response.text)

    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == old_status
        assert application.employer_notes is None
        assert not history(db, application.id)
        assert not notifications(db, application.id)


def test_simultaneous_decisions_record_only_one_transition(review_data):
    data = review_data
    with SessionLocal.begin() as db:
        db.get(Application, data.application_id).status = "INTERVIEW"

    start = Barrier(2, timeout=10)

    def decide(status):
        client = TestClient(app)
        start.wait()
        return client.patch(
            status_url(data.application_id), json={"status": status, "note": status}, headers=data.headers,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(decide, ("OFFERED", "REJECTED")))

    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json()["status"] for response in responses if response.status_code == 200)
    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == winner
        assert application.employer_notes == winner
        [entry] = history(db, application.id)
        assert entry.new_status == winner
        [message] = notifications(db, application.id)
        assert json.loads(message.payload_json)["status"] == winner


def test_notification_failure_rolls_back_status_note_and_history(client, review_data, monkeypatch):
    data = review_data
    monkeypatch.setattr(employer_applications, "notify_application_status_changed", lambda *args, **kwargs: None)
    response = client.patch(
        status_url(data.application_id), json={"status": "REVIEWING", "note": "Rollback this note"},
        headers=data.headers,
    )
    assert response.status_code == 500, response.text
    with SessionLocal() as db:
        application = db.get(Application, data.application_id)
        assert application.status == "SUBMITTED"
        assert application.employer_notes is None
        assert not history(db, application.id)
        assert not notifications(db, application.id)
