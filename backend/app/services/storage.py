"""
Service de stockage de fichiers (filesystem local).
Conçu pour être remplacé par S3 / GCS plus tard sans changer le reste du code.
"""
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

# Dossier racine de tous les uploads (relatif au backend/)
UPLOADS_ROOT = Path("uploads")


class FileStorage:
    """Stockage de fichiers sur le filesystem local."""

    def __init__(self, base_dir: Path = UPLOADS_ROOT):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: UUID) -> Path:
        """Retourne le dossier d'un user, le crée si besoin."""
        d = self.base_dir / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def save_upload(
        self, file: UploadFile, user_id: UUID, max_size: int
    ) -> tuple[str, int]:
        """
        Sauvegarde un fichier uploadé par chunks (pas de pic mémoire).
        Retourne (relative_path, size_bytes).
        Lève ValueError si la taille dépasse max_size.
        """
        ext = Path(file.filename or "unknown").suffix.lower()
        dataset_id = uuid4()
        filename = f"{dataset_id}{ext}"
        user_dir = self._user_dir(user_id)
        file_path = user_dir / filename

        size = 0
        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                size += len(chunk)
                if size > max_size:
                    f.close()
                    file_path.unlink(missing_ok=True)
                    raise ValueError(
                        f"Fichier trop volumineux ({size / 1024 / 1024:.1f} MB)"
                    )
                f.write(chunk)

        relative = file_path.relative_to(self.base_dir)
        return str(relative), size

    def copy_local_file(self, source: Path, user_id: UUID) -> tuple[str, int]:
        """Copie un fichier deja present sur disque (ex: dataset d'exemple)
        dans l'espace de l'utilisateur. Retourne (relative_path, size_bytes)."""
        ext = source.suffix.lower()
        filename = f"{uuid4()}{ext}"
        user_dir = self._user_dir(user_id)
        file_path = user_dir / filename
        shutil.copy(source, file_path)

        relative = file_path.relative_to(self.base_dir)
        return str(relative), file_path.stat().st_size

    def get_full_path(self, relative_path: str) -> Path:
        """Reconstruit le chemin absolu depuis le relatif stocké en BDD."""
        return self.base_dir / relative_path

    def delete(self, relative_path: str) -> None:
        """Supprime un fichier (ignore si absent)."""
        full = self.get_full_path(relative_path)
        full.unlink(missing_ok=True)


def get_storage() -> FileStorage:
    """Dependency FastAPI."""
    return FileStorage()
