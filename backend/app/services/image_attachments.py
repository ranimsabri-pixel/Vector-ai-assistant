"""Service de pieces jointes image dans le chat (S5 J41+ Feature 3).

Flux :
- L'original est sauvegarde en pleine resolution sur disque
  (uploads/attachments/{user_id}/{conversation_id}/{uuid}.ext) — relu plus
  tard pour construire le bloc vision envoye au LLM.
- Une version redimensionnee (<=512px cote le plus long) est encodee en
  base64 et stockee directement dans Message.attachments (JSONB), pour un
  affichage inline instantane sans endpoint de service dedie.
"""
import base64
import io
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image

ALLOWED_MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
PREVIEW_MAX_SIDE = 512

UPLOADS_ROOT = Path("uploads")
ATTACHMENTS_ROOT = UPLOADS_ROOT / "attachments"


async def save_image_attachment(
    file: UploadFile, user_id: UUID, conversation_id: UUID
) -> dict:
    """Valide, sauvegarde et miniaturise une image uploadee dans le chat.

    Leve HTTPException(400) si le mime type est refuse, si le fichier
    depasse MAX_IMAGE_SIZE, ou si le contenu n'est pas une image valide.
    """
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TO_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Type d'image non supporté : {content_type}. "
                "Formats acceptés : PNG, JPEG, WebP, GIF."
            ),
        )

    raw = await file.read()
    if len(raw) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image trop volumineuse ({len(raw) / 1024 / 1024:.1f} MB, max 10 MB).",
        )

    try:
        Image.open(io.BytesIO(raw)).verify()
        img = Image.open(io.BytesIO(raw))  # verify() consomme le buffer, on rouvre
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fichier image invalide ou corrompu.",
        ) from None

    width, height = img.size
    ext = ALLOWED_MIME_TO_EXT[content_type]
    attachment_id = uuid4()

    # 1. Sauvegarde l'original sur disque (relu plus tard pour la vision LLM)
    conv_dir = ATTACHMENTS_ROOT / str(user_id) / str(conversation_id)
    conv_dir.mkdir(parents=True, exist_ok=True)
    file_path = conv_dir / f"{attachment_id}{ext}"
    file_path.write_bytes(raw)
    storage_path = str(file_path.relative_to(UPLOADS_ROOT))

    # 2. Genere une version d'affichage (<=512px cote le plus long) en base64
    preview_img = img.copy()
    preview_img.thumbnail((PREVIEW_MAX_SIDE, PREVIEW_MAX_SIDE))
    preview_format = "PNG" if content_type in ("image/png", "image/gif") else "JPEG"
    if preview_format == "JPEG" and preview_img.mode in ("RGBA", "P"):
        preview_img = preview_img.convert("RGB")
    buf = io.BytesIO()
    preview_img.save(buf, format=preview_format)
    preview_mime = "image/png" if preview_format == "PNG" else "image/jpeg"
    preview_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "type": "image",
        "attachment_id": str(attachment_id),
        "file_name": file.filename or "image",
        "mime_type": content_type,
        "file_size": len(raw),
        "width": width,
        "height": height,
        "storage_path": storage_path,
        "preview_base64": f"data:{preview_mime};base64,{preview_b64}",
    }


def build_vision_content_block(attachment: dict) -> dict:
    """Construit le bloc image_url (format multimodal OpenAI) depuis
    l'original sauvegarde sur disque — jamais depuis le preview redimensionne
    (qui perd en qualite et n'est destine qu'a l'affichage UI)."""
    full_path = UPLOADS_ROOT / attachment["storage_path"]
    raw = full_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    mime = attachment.get("mime_type", "image/png")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "auto"},
    }
