"""Service métier pour les datasets : upload, parsing, listing."""
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pandas as pd
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.providers.openai import OpenAIProvider
from app.db.models.dataset import Dataset, DatasetColumn
from app.db.models.user import User
from app.services.auto_kpi_generator import generate_kpis
from app.services.business_patterns import detect_applicable_patterns
from app.services.kpi_calculator import KPIResult, KPISpec, calculate_kpi
from app.services.kpi_translator import translate_all_suggestions
from app.services.profiler import profile_dataframe
from app.services.semantic_detector import analyze_dataset
from app.services.storage import FileStorage

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
SAMPLE_ROWS = 5

# NEW J44 Bloc A — regles anti-hallucination chiffree, ajoutees au bloc de
# contexte CSV (build_chat_context_block ci-dessous). Corrige le bug observe
# en J42 : le LLM calcule juste dans son raisonnement affiche ("Chaise = 320")
# mais conclut sur une autre valeur ("Lampe" avec 300) — pas un bug de code,
# une limite de raisonnement LLM sur les agregations, attaquee ici par prompt
# engineering (Option C).
NUMERIC_REASONING_RULES = """
RÈGLES DE CALCUL STRICTES (obligatoires pour toute question chiffrée) :

1. Pour toute question impliquant un calcul (somme, moyenne, médiane, min,
   max, comptage, comparaison, top N, agrégation par groupe, corrélation)
   sur les données tabulaires ci-dessus, tu DOIS utiliser l'outil
   compute_from_dataset. Ne fais JAMAIS de calcul mental à partir de
   l'extrait affiché, même si le résultat te semble évident.

2. N'invente JAMAIS un chiffre. Si compute_from_dataset échoue ou ne
   couvre pas la question posée, dis-le explicitement plutôt que
   d'estimer une valeur.

3. Une fois le résultat de l'outil obtenu, formule ta réponse finale en
   langage naturel à partir de son "summary" — ne renvoie jamais le JSON
   brut du résultat à l'utilisateur.
"""

# Dataset d'exemple propose aux nouveaux utilisateurs (S5 J40)
EXAMPLE_DATASET_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "example_datasets" / "ecommerce_sample.csv"
)
EXAMPLE_DATASET_NAME = "Exemple e-commerce (500 lignes)"


async def reprofile_in_background(dataset_id: UUID, user_id: UUID) -> None:
    """Tache de fond (S5 J39) : reprofile un dataset avec sa propre session
    DB, independante de la requete HTTP qui l'a declenchee (celle-ci est
    deja fermee au moment ou BackgroundTasks execute ceci)."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        storage = FileStorage()
        service = DatasetService(session, storage)
        user = await session.get(User, user_id)
        if user is None:
            return
        try:
            await service.profile(user, dataset_id)
        except Exception:
            pass  # profile() met deja status="error" + error_message sur echec


class DatasetService:
    def __init__(self, db: AsyncSession, storage: FileStorage):
        self.db = db
        self.storage = storage

    # ============================================================
    # Upload
    # ============================================================

    async def upload(
        self,
        user: User,
        file: UploadFile,
        name: str | None = None,
        description: str | None = None,
        column_overrides: list[dict[str, Any]] | None = None,
    ) -> Dataset:
        """Upload un fichier, valide, parse, crée le record BDD."""

        # Validation extension
        if not file.filename:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Nom de fichier manquant"
            )

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Extension non supportée. Acceptées : {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # Sauvegarde sur disque + check taille
        try:
            relative_path, size = await self.storage.save_upload(
                file, user.id, max_size=MAX_FILE_SIZE
            )
        except ValueError as e:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(e)
            ) from e

        # Parsing minimal pour métadonnées
        full_path = self.storage.get_full_path(relative_path)
        try:
            row_count, column_count, sample = self._parse_summary(full_path, ext)
        except Exception as e:
            self.storage.delete(relative_path)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Fichier illisible ({type(e).__name__}) : vérifie le format",
            ) from e

        # Création du record BDD
        dataset_name = name or Path(file.filename).stem

        dataset = Dataset(
            user_id=user.id,
            name=dataset_name,
            description=description,
            original_filename=file.filename,
            file_path=relative_path,
            file_size_bytes=size,
            row_count=row_count,
            column_count=column_count,
            status="uploaded",
            raw_data_sample=sample,
            pending_column_overrides=column_overrides,
        )
        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def load_example_dataset(self, user: User) -> Dataset:
        """Copie le dataset d'exemple e-commerce dans l'espace de l'utilisateur
        et cree l'entree Dataset correspondante (S5 J40, onboarding)."""
        if not EXAMPLE_DATASET_PATH.exists():
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Dataset d'exemple introuvable côté serveur",
            )

        relative_path, size = self.storage.copy_local_file(
            EXAMPLE_DATASET_PATH, user.id
        )
        full_path = self.storage.get_full_path(relative_path)
        row_count, column_count, sample = self._parse_summary(full_path, ".csv")

        dataset = Dataset(
            user_id=user.id,
            name=EXAMPLE_DATASET_NAME,
            description="Dataset de démonstration généré automatiquement pour découvrir Vector.",
            original_filename="ecommerce_sample.csv",
            file_path=relative_path,
            file_size_bytes=size,
            row_count=row_count,
            column_count=column_count,
            status="uploaded",
            raw_data_sample=sample,
        )
        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    # ============================================================
    # Corrections colonnes utilisateur (S5 J38)
    # ============================================================

    _BOOLEAN_TRUE = {"true", "1", "yes", "oui"}
    _BOOLEAN_FALSE = {"false", "0", "no", "non"}

    @staticmethod
    def _coerce_boolean(series: pd.Series) -> pd.Series:
        normalized = series.astype(str).str.strip().str.lower()

        def _map(v: str) -> bool | None:
            if v in DatasetService._BOOLEAN_TRUE:
                return True
            if v in DatasetService._BOOLEAN_FALSE:
                return False
            return None

        return normalized.map(_map)

    @staticmethod
    def _apply_column_overrides(
        df: pd.DataFrame, overrides: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Applique les corrections colonnes soumises a l'upload (renommer /
        supprimer / forcer un type), avant le profilage automatique."""

        # 1. Supprimer les colonnes marquees deleted
        deleted_cols = [
            o["original_name"] for o in overrides
            if o.get("deleted") and o.get("original_name") in df.columns
        ]
        if deleted_cols:
            df = df.drop(columns=deleted_cols)

        # 2. Renommer les colonnes restantes
        rename_map = {
            o["original_name"]: o["new_name"]
            for o in overrides
            if o.get("new_name")
            and o["new_name"] != o["original_name"]
            and not o.get("deleted")
            and o.get("original_name") in df.columns
        }
        if rename_map:
            df = df.rename(columns=rename_map)

        # 3. Forcer les types (sur le nom final de la colonne)
        for o in overrides:
            if o.get("deleted") or not o.get("type"):
                continue
            col_name = rename_map.get(o["original_name"], o["original_name"])
            if col_name not in df.columns:
                continue
            forced_type = o["type"]
            if forced_type == "numeric":
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
            elif forced_type == "datetime":
                df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
            elif forced_type == "boolean":
                df[col_name] = DatasetService._coerce_boolean(df[col_name])
            elif forced_type in ("categorical", "text"):
                # Repasse en chaine pour empecher infer_dtype de re-detecter
                # la colonne comme numerique (ex: codes postaux).
                df[col_name] = df[col_name].astype(str)

        return df

    @staticmethod
    def _forced_types_by_final_name(
        overrides: list[dict[str, Any]],
    ) -> dict[str, str]:
        """Map nom-final-de-colonne -> dtype force, pour ecraser le resultat
        de infer_dtype apres coup (garantit que le choix explicite de
        l'utilisateur l'emporte toujours, meme si l'heuristique backend
        aurait detecte autre chose)."""
        rename_map = {
            o["original_name"]: o["new_name"]
            for o in overrides
            if o.get("new_name")
            and o["new_name"] != o["original_name"]
            and not o.get("deleted")
        }
        return {
            rename_map.get(o["original_name"], o["original_name"]): o["type"]
            for o in overrides
            if o.get("type") and not o.get("deleted")
        }

    # ============================================================
    # Parsing
    # ============================================================

    def _parse_summary(
        self, path: Path, ext: str
    ) -> tuple[int, int, dict[str, Any]]:
        """Parse rapide : nombre de lignes, colonnes, 5 premières lignes."""
        if ext == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path)

        row_count = int(len(df))
        column_count = int(len(df.columns))

        head = df.head(SAMPLE_ROWS).fillna("").astype(str)
        sample = {
            "columns": [str(c) for c in df.columns],
            "rows": head.values.tolist(),
        }
        return row_count, column_count, sample

    # ============================================================
    # Listing / Get / Delete
    # ============================================================

    async def list_user_datasets(self, user: User) -> list[dict[str, Any]]:
        """Liste les datasets de l'utilisateur, enrichis du matching d'actions (J20).

        Eager loading des colonnes via selectinload pour éviter le N+1.
        Le champ matches_for_action permet au frontend d'afficher un badge ✓
        sur les datasets adaptés à chaque action rapide.
        """
        from app.ai.vector_tools import _detect_matching_actions

        result = await self.db.execute(
            select(Dataset)
            .where(Dataset.user_id == user.id)
            .options(selectinload(Dataset.columns))
            .order_by(Dataset.created_at.desc())
        )
        datasets = result.scalars().all()

        # Construit les dicts enrichis (matches_for_action calculé à la volée)
        enriched: list[dict[str, Any]] = []
        for d in datasets:
            column_names = [c.name for c in d.columns] if d.columns else []
            matches = _detect_matching_actions(column_names)

            enriched.append({
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "original_filename": d.original_filename,
                "file_size_bytes": d.file_size_bytes,
                "row_count": d.row_count,
                "column_count": d.column_count,
                "status": d.status,
                "quality_score": d.quality_score,
                "semantic_analysis": d.semantic_analysis,
                "auto_kpis": d.auto_kpis,
                "created_at": d.created_at,
                "matches_for_action": matches,
            })

        return enriched

    async def get_dataset(self, user: User, dataset_id: UUID) -> Dataset:
        result = await self.db.execute(
            select(Dataset).where(
                Dataset.id == dataset_id, Dataset.user_id == user.id
            )
        )
        dataset = result.scalar_one_or_none()
        if dataset is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Dataset introuvable"
            )
        return dataset

    async def build_chat_context_block(
        self, user: User, dataset_id: UUID
    ) -> str | None:
        """Bloc de contexte texte (metadonnees + extrait de lignes) injecte
        dans le prompt LLM quand un dataset est joint a un message de chat
        (S5 J41+ Feature 4). None si le dataset n'existe pas / n'appartient
        pas a l'user / n'est pas encore pret."""
        try:
            dataset = await self.get_dataset(user, dataset_id)
        except HTTPException:
            return None
        if dataset.status != "ready":
            return None

        full_path = self.storage.get_full_path(dataset.file_path)
        ext = Path(dataset.original_filename).suffix.lower()
        try:
            df = pd.read_csv(full_path) if ext == ".csv" else pd.read_excel(full_path)
        except Exception:
            return None

        extract = df.head(20).to_csv(index=False)
        # Limite de taille : evite d'exploser le prompt sur un CSV a tres nombreuses colonnes
        if len(extract) > 6000:
            extract = extract[:6000] + "\n... (extrait tronque)"

        return (
            "### Dataset joint a ce message — INSTRUCTION PRIORITAIRE\n"
            "Un fichier de donnees est joint au message de l'utilisateur (extrait "
            "ci-dessous, pour contexte visuel uniquement). Pour toute question NON "
            "chiffree (quelles colonnes existent, a quoi ressemblent les donnees...), "
            "reponds directement a partir de cet extrait. Pour toute question "
            "chiffree, utilise OBLIGATOIREMENT l'outil compute_from_dataset avec "
            "dataset_id ci-dessous (voir regles de calcul plus bas) — ne calcule "
            "JAMAIS a partir de l'extrait. N'appelle list_user_datasets, "
            "get_dataset_summary ou generate_dashboard que si l'utilisateur demande "
            "explicitement un dashboard ou une analyse visuelle.\n\n"
            f"Dataset : « {dataset.name} » (dataset_id : {dataset.id}) — "
            f"{dataset.row_count} lignes, {dataset.column_count} colonnes.\n"
            f"Colonnes : {', '.join(str(c) for c in df.columns)}.\n"
            f"Extrait des 20 premieres lignes (format CSV, contexte visuel "
            f"seulement) :\n{extract}\n"
            f"{NUMERIC_REASONING_RULES}"
        )

    async def delete_dataset(self, user: User, dataset_id: UUID) -> None:
        dataset = await self.get_dataset(user, dataset_id)
        self.storage.delete(dataset.file_path)
        await self.db.delete(dataset)
        await self.db.commit()

    # ============================================================
    # Profilage : Profile un dataset : analyse chaque colonne, calcule la qualité,
    # et met à jour les tables `datasets` et `dataset_columns`.
    # ============================================================

    async def profile(self, user: User, dataset_id: UUID) -> Dataset:

        dataset = await self.get_dataset(user, dataset_id)

        # Marquer en cours
        dataset.status = "profiling"
        dataset.error_message = None
        await self.db.commit()

        try:
            # Charger le fichier depuis le disque
            full_path = self.storage.get_full_path(dataset.file_path)
            ext = Path(dataset.original_filename).suffix.lower()
            if ext == ".csv":
                df = pd.read_csv(full_path)
            else:
                df = pd.read_excel(full_path)

            # Applique les corrections colonnes soumises a l'upload (S5 J38),
            # si presentes. Consommees une fois appliquees (voir plus bas).
            forced_types: dict[str, str] = {}
            if dataset.pending_column_overrides:
                df = self._apply_column_overrides(
                    df, dataset.pending_column_overrides
                )
                forced_types = self._forced_types_by_final_name(
                    dataset.pending_column_overrides
                )

            # Lancer le profilage
            result = profile_dataframe(df)

            # Supprimer les anciennes colonnes profilées (au cas où on re-profile)
            await self.db.execute(
                delete(DatasetColumn).where(
                    DatasetColumn.dataset_id == dataset.id
                )
            )

            # Insérer les nouvelles colonnes
            for col_data in result["columns"]:
                # Le type force par l'utilisateur l'emporte toujours sur ce
                # que infer_dtype a detecte (ex: code postal en "text").
                dtype = forced_types.get(col_data["name"], col_data["dtype"])
                column = DatasetColumn(
                    dataset_id=dataset.id,
                    name=col_data["name"],
                    dtype=dtype,
                    is_nullable=col_data["is_nullable"],
                    null_count=col_data["null_count"],
                    unique_count=col_data["unique_count"],
                    sample_values=col_data["sample_values"],
                    is_date_main=col_data["is_date_main"],
                    numeric_stats=col_data.get("numeric_stats"),
                    categorical_stats=col_data.get("categorical_stats"),
                    date_stats=col_data.get("date_stats"),
                )
                self.db.add(column)

            # Mettre à jour le dataset
            dataset.quality_score = result["quality_score"]
            dataset.quality_issues = result["quality_issues"]
            dataset.status = "ready"
            dataset.error_message = None
            dataset.row_count = int(len(df))
            dataset.column_count = int(len(df.columns))
            # On NE vide plus pending_column_overrides : il represente
            # desormais l'ensemble cumule des corrections effectivement
            # appliquees (garde en memoire pour composer les corrections
            # posterieures, voir update_column_overrides).

            await self.db.commit()
            await self.db.refresh(dataset)
            return dataset

        except Exception as e:
            dataset.status = "error"
            dataset.error_message = f"{type(e).__name__}: {str(e)[:200]}"
            await self.db.commit()
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Erreur de profilage : {type(e).__name__}",
            ) from e

    async def update_column_overrides(
        self, user: User, dataset_id: UUID, overrides: list[dict[str, Any]]
    ) -> Dataset:
        """Corrige les colonnes d'un dataset deja profile (S5 J38.E) :
        renommer / supprimer / forcer un type apres coup, puis relance
        automatiquement le profilage.

        Les `original_name` recus ici sont les noms COURANTS affiches a
        l'utilisateur sur la page dataset - donc potentiellement deja issus
        d'une correction precedente. On les retraduit vers les noms du
        fichier brut (via les overrides deja appliques) avant de fusionner,
        puisque le profilage relit toujours le fichier d'origine depuis le
        disque."""
        dataset = await self.get_dataset(user, dataset_id)

        if dataset.status not in ("ready", "error"):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Le dataset doit être prêt (ou en erreur) avant de corriger ses colonnes",
            )

        existing: list[dict[str, Any]] = dataset.pending_column_overrides or []

        # nom-final -> nom-brut, d'apres les corrections deja appliquees
        rename_map = {
            o["original_name"]: o["new_name"]
            for o in existing
            if o.get("new_name")
            and o["new_name"] != o["original_name"]
            and not o.get("deleted")
        }
        final_to_raw = {v: k for k, v in rename_map.items()}

        merged: dict[str, dict[str, Any]] = {
            o["original_name"]: dict(o) for o in existing
        }

        for new_o in overrides:
            current_name = new_o["original_name"]
            raw_name = final_to_raw.get(current_name, current_name)
            entry = merged.setdefault(raw_name, {"original_name": raw_name})
            if new_o.get("new_name"):
                entry["new_name"] = new_o["new_name"]
            if new_o.get("type"):
                entry["type"] = new_o["type"]
            if new_o.get("deleted") is not None:
                entry["deleted"] = new_o["deleted"]
            merged[raw_name] = entry

        dataset.pending_column_overrides = list(merged.values())
        dataset.status = "profiling"
        await self.db.commit()

        return await self.profile(user, dataset_id)

    async def mark_for_reprofile(self, user: User, dataset_id: UUID) -> Dataset:
        """Repasse un dataset en statut 'profiling', pour que le reprofilage
        complet (avec les stats enrichies J39) soit ensuite lance en tache
        de fond par l'appelant (voir reprofile_in_background)."""
        dataset = await self.get_dataset(user, dataset_id)
        dataset.status = "profiling"
        dataset.error_message = None
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def get_dataset_columns(
        self, user: User, dataset_id: UUID
    ) -> list[DatasetColumn]:
        """Récupère les colonnes profilées d'un dataset."""
        await self.get_dataset(user, dataset_id)  # vérifie ownership
        result = await self.db.execute(
            select(DatasetColumn)
            .where(DatasetColumn.dataset_id == dataset_id)
            .order_by(DatasetColumn.id)
        )
        return list(result.scalars().all())

    async def get_column_values(
        self, user: User, dataset_id: UUID, column_name: str, limit: int = 200
    ) -> list:
        """Valeurs uniques d'une colonne (pour les filtres categoriels des dashboards).

        Charge le fichier source et retourne les valeurs distinctes triees,
        plafonnees a `limit` pour eviter de renvoyer une colonne quasi-libre.
        """
        dataset = await self.get_dataset(user, dataset_id)

        full_path = self.storage.get_full_path(dataset.file_path)
        ext = Path(dataset.original_filename).suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(full_path)
        else:
            df = pd.read_excel(full_path)

        if column_name not in df.columns:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Colonne '{column_name}' introuvable"
            )

        values = df[column_name].dropna().unique().tolist()
        try:
            values = sorted(values)
        except TypeError:
            values = sorted(values, key=str)

        def _jsonable(v):
            if isinstance(v, pd.Timestamp):
                return v.strftime("%Y-%m-%d")
            if hasattr(v, "item"):
                return v.item()
            return v

        return [_jsonable(v) for v in values[:limit]]


    # ============================================================
    # Analyse sémantique
    # ============================================================

    async def analyze(self, user: User, dataset_id: UUID) -> Dataset:
        """
        Lance l'analyse sémantique business du dataset.
        Le dataset doit avoir été profilé au préalable (status='ready').
        """
        dataset = await self.get_dataset(user, dataset_id)

        if dataset.status != "ready":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Le dataset doit être profilé avant l'analyse sémantique",
            )

        # Récupère les colonnes profilées
        columns = await self.get_dataset_columns(user, dataset_id)
        if not columns:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Aucune colonne profilée trouvée pour ce dataset",
            )

        # Appelle le service de détection sémantique
        try:
            provider = OpenAIProvider()
            result = await analyze_dataset(dataset, columns, provider)
            result["analyzed_at"] = datetime.now(UTC).isoformat()

            dataset.semantic_analysis = result
            await self.db.commit()
            await self.db.refresh(dataset)
            return dataset

        except Exception as e:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Erreur d'analyse sémantique : {type(e).__name__}",
            ) from e

        # ============================================================
    # KPIs : génération auto + calcul
    # ============================================================

    async def generate_auto_kpis(self, user: User, dataset_id: UUID) -> Dataset:
        """
        Génère la liste des KPIs auto-calculables pour le dataset.
        Le dataset doit être profilé (status='ready').
        Stocke la liste dans le champ auto_kpis.
        """
        dataset = await self.get_dataset(user, dataset_id)

        if dataset.status != "ready":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Le dataset doit être profilé avant la génération des KPIs",
            )

        columns = await self.get_dataset_columns(user, dataset_id)
        if not columns:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Aucune colonne profilée trouvée pour ce dataset",
            )

        total_rows = dataset.row_count or 0
        specs = generate_kpis(columns, total_rows)

        # Stocke la liste de specs dans auto_kpis (JSONB)
        dataset.auto_kpis = {
            "specs": [s.to_dict() for s in specs],
            "generated_count": len(specs),
        }
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def calculate_auto_kpi(
        self, user: User, dataset_id: UUID, spec_id: str
    ) -> KPIResult:
        """
        Calcule la valeur d'un KPI auto-généré spécifique.
        Charge le fichier en pandas, exécute le calcul, retourne le résultat.
        """
        dataset = await self.get_dataset(user, dataset_id)

        if not dataset.auto_kpis or "specs" not in dataset.auto_kpis:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Aucun KPI auto-généré pour ce dataset. Lance d'abord generate.",
            )

        # Retrouve le spec demandé
        spec_dict = next(
            (s for s in dataset.auto_kpis["specs"] if s["id"] == spec_id),
            None,
        )
        if spec_dict is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"KPI '{spec_id}' introuvable pour ce dataset",
            )

        # Reconstruit l'objet KPISpec depuis le dict stocké
        spec = KPISpec(**spec_dict)

        # Charge le fichier
        full_path = self.storage.get_full_path(dataset.file_path)
        ext = Path(dataset.original_filename).suffix.lower()
        try:
            if ext == ".csv":
                df = pd.read_csv(full_path)
            else:
                df = pd.read_excel(full_path)
        except Exception as e:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Impossible de charger le fichier : {type(e).__name__}",
            ) from e

        # Exécute le calcul
        try:
            result = calculate_kpi(df, spec)
        except ValueError as e:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Erreur de calcul : {str(e)}",
            ) from e

        return result

    async def calculate_all_auto_kpis(
        self, user: User, dataset_id: UUID
    ) -> list[KPIResult]:
        """
        Calcule TOUS les KPIs auto-générés en une seule passe.
        Pratique pour rafraîchir un dashboard d'un coup.
        Le fichier est lu une seule fois, c'est l'avantage du batch.
        """
        dataset = await self.get_dataset(user, dataset_id)

        if not dataset.auto_kpis or "specs" not in dataset.auto_kpis:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Aucun KPI auto-généré. Lance d'abord generate.",
            )

        # Charge le fichier UNE SEULE FOIS
        full_path = self.storage.get_full_path(dataset.file_path)
        ext = Path(dataset.original_filename).suffix.lower()
        try:
            if ext == ".csv":
                df = pd.read_csv(full_path)
            else:
                df = pd.read_excel(full_path)
        except Exception as e:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                f"Impossible de charger le fichier : {type(e).__name__}",
            ) from e

        # Calcule chaque KPI (les erreurs individuelles ne stoppent pas le batch)
        results: list[KPIResult] = []
        for spec_dict in dataset.auto_kpis["specs"]:
            try:
                spec = KPISpec(**spec_dict)
                result = calculate_kpi(df, spec)
                results.append(result)
            except Exception as e:
                # On loggue mais on continue
                import logging
                logging.warning(
                    "KPI %s calculation failed: %s", spec_dict.get("id"), e
                )

        return results
    # ============================================================
    # KPIs avancés (J12) : patterns business + traduction LLM
    # ============================================================

    async def generate_advanced_kpis(
        self, user: User, dataset_id: UUID
    ) -> Dataset:
        """
        Génère des KPIs avancés à partir de 2 sources :
        1. Patterns business prédéfinis (déterministe, instantané)
        2. Traduction LLM des suggested_kpis générés en J9 (si présents)

        Ces KPIs avancés s'ajoutent aux auto_kpis simples de J11.
        """
        dataset = await self.get_dataset(user, dataset_id)

        if dataset.status != "ready":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Le dataset doit être profilé avant la génération des KPIs avancés",
            )

        columns = await self.get_dataset_columns(user, dataset_id)
        if not columns:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Aucune colonne profilée trouvée",
            )

        # 1. Patterns business prédéfinis
        pattern_specs = detect_applicable_patterns(columns)

        # 2. Traduction des suggested_kpis (J9) si disponibles
        translated_specs = []
        semantic = dataset.semantic_analysis
        if semantic and "llm_analysis" in semantic:
            suggestions = semantic["llm_analysis"].get("suggested_kpis", [])
            if suggestions:
                from app.ai.providers.openai import OpenAIProvider
                provider = OpenAIProvider()
                translated_specs = await translate_all_suggestions(
                    suggestions, columns, provider
                )

        # Fusion : on garde tout (patterns + traductions)
        all_specs = pattern_specs + translated_specs

        # Stocke dans le champ auto_kpis (en plus des simples si déjà générés)
        existing = dataset.auto_kpis or {"specs": []}
        existing_specs = existing.get("specs", [])

        # Évite les doublons par id
        existing_ids = {s["id"] for s in existing_specs}
        new_specs = [s.to_dict() for s in all_specs if s.id not in existing_ids]

        dataset.auto_kpis = {
            "specs": existing_specs + new_specs,
            "generated_count": len(existing_specs) + len(new_specs),
        }
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset
