"""ORM models. Importing this package registers all tables on Base.metadata."""

from app.db.models.admin_verdicts import AdminVerdict
from app.db.models.appeal_tracks import AppealTrack
from app.db.models.audit_events import AuditEvent
from app.db.models.case_files import CaseFile
from app.db.models.cms_ingestion_state import CmsIngestionState
from app.db.models.consent_history import ConsentHistory
from app.db.models.conversations import Conversation
from app.db.models.cron_run_log import CronRunLog
from app.db.models.deadlines import Deadline
from app.db.models.messages import Message
from app.db.models.knowledge_gap_log import KnowledgeGapLog
from app.db.models.feedback import (
    FeedbackDeidCandidate,
    FeedbackEvent,
    FeedbackTriageQueue,
)
from app.db.models.findings import Finding
from app.db.models.insurance_cards import InsuranceCard
from app.db.models.insurance_info import InsuranceInfo
from app.db.models.magic_link import MagicLinkConsumed
from app.db.models.plan_library import PlanLibraryEntry
from app.db.models.transparency_rates import TransparencyRate, TransparencyRateStaging
from app.db.models.users import User

__all__ = [
    "User",
    "CaseFile",
    "Finding",
    "Deadline",
    "AppealTrack",
    "AuditEvent",
    "FeedbackEvent",
    "FeedbackTriageQueue",
    "FeedbackDeidCandidate",
    "ConsentHistory",
    "MagicLinkConsumed",
    "CmsIngestionState",
    "AdminVerdict",
    "TransparencyRate",
    "TransparencyRateStaging",
    "KnowledgeGapLog",
    "CronRunLog",
    "Conversation",
    "Message",
    "PlanLibraryEntry",
    "InsuranceInfo",
    "InsuranceCard",
]
