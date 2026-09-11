"""Tous les modèles SQLAlchemy — utilisé par Alembic pour autogenerate."""
from app.db.models.agent import Agent
from app.db.models.analysis import Analysis
from app.db.models.conversation import Conversation, Message
from app.db.models.conversation_share import ConversationShare
from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.dashboard import Dashboard
from app.db.models.dataset import Dataset, DatasetColumn
from app.db.models.document import Chunk, Document
from app.db.models.kpi import KPI, KPIValue
from app.db.models.persona import Persona, PersonaCorpus, PersonaDocument
from app.db.models.saved_dashboard import DashboardWidget, SavedDashboard
from app.db.models.user import User

__all__ = [
    "Agent",
    "Analysis",
    "Chunk",
    "Conversation",
    "ConversationShare",
    "Corpus",
    "CorpusDocument",
    "Dashboard",
    "DashboardWidget",
    "Dataset",
    "DatasetColumn",
    "Document",
    "KPI",
    "KPIValue",
    "Message",
    "Persona",
    "PersonaCorpus",
    "PersonaDocument",
    "SavedDashboard",
    "User",
]
