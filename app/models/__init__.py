# Import mọi model ở đây để Base.metadata.create_all() nhận diện bảng.
from app.models.item import Item
from app.models.candidate_profile import CandidateProfile
from app.models.company import Company
from app.models.industry import Industry
from app.models.location import Location
from app.models.skill import Skill
from app.models.job import Job
from app.models.job_skill import JobSkill
from app.models.saved_job import SavedJob