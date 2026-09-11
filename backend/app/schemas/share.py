"""Schemas Pydantic pour le partage public de conversations (S5 J48).

PublicConversationShare / PublicMessage / PublicRagSource sont la surface
EXACTE exposée par le endpoint public GET /share/{token} (pas d'auth) —
filtrage strict : jamais de tokens_used, cost_usd, model_used, tool_calls,
email utilisateur, ni chunk_id/document_id des sources RAG.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ShareCreate(BaseModel):
    """Payload de POST /conversations/{id}/share — opt-in explicite (défaut
    False partout : sécurité par défaut, NEW J49)."""
    include_attachments: bool = False


class ShareResponse(BaseModel):
    """Réponse de POST /conversations/{id}/share."""
    share_token: str
    share_url: str
    include_attachments: bool = False


class PublicRagSource(BaseModel):
    """Source RAG filtrée pour affichage public — jamais chunk_id/document_id."""
    document_name: str | None = None
    page_number: int | None = None
    content_preview: str | None = None


class PublicAttachment(BaseModel):
    """Pièce jointe image filtrée pour affichage public (NEW J49) — jamais
    storage_path (chemin disque interne), attachment_id, file_size, width,
    height : seuls file_name/mime_type/preview_base64 sont nécessaires au
    rendu, la miniature ≤512px déjà calculée (même donnée que la vue privée,
    jamais l'original pleine résolution — celui-ci n'est d'ailleurs exposé
    au frontend nulle part, même pour le propriétaire authentifié)."""
    type: str = "image"
    file_name: str
    mime_type: str
    preview_base64: str


class PublicMessage(BaseModel):
    """Message filtré pour affichage public — jamais tokens/coût/tool_calls."""
    role: str
    message_kind: str
    content: str
    sources: list[PublicRagSource] | None = None
    attachments: list[PublicAttachment] | None = None
    # True si ce message a une image jointe MAIS que include_attachments=False
    # sur ce share — permet au frontend d'afficher un placeholder discret
    # ("Image non partagée", jamais le nom de fichier) plutôt que de laisser
    # croire que le message était uniquement textuel. Toujours False quand
    # attachments est renseigné (pas besoin de placeholder si l'image y est).
    has_hidden_attachments: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicConversationShare(BaseModel):
    """Réponse de GET /share/{token} — endpoint PUBLIC, filtrage strict."""
    title: str
    shared_by: str
    messages: list[PublicMessage]
