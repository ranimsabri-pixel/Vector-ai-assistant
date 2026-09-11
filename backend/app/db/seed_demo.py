"""Seed du compte de démo publique (S5 J55) — Render.

Insère le contenu figé dans app/data/demo/fixture.json (dataset IBM Sales
Pipeline profilé, corpus IBM embeddé, persona, conversations d'exemple),
généré une fois pour toutes par scripts/generate_demo_fixture.py (avec de
vrais appels OpenAI). AUCUN appel OpenAI ici — insertion pure, coût nul et
déterministe à chaque démarrage de conteneur.

Deux couches d'idempotence bien distinctes, avec des durées de vie
différentes sur Render free tier :
- Lignes BDD (Neon) : idempotent par existence du compte démo -- créées
  UNE fois, persistent ensuite entre redéploiements.
- Fichiers physiques (uploads/, disque éphémère) : perdus à CHAQUE
  redéploiement/restart. Restaurés depuis app/data/demo/source_files/
  (embarqué dans l'image Docker) à CHAQUE démarrage, indépendamment de
  l'état des lignes BDD -- sinon ils ne sont jamais recréés après le
  tout premier déploiement (bug corrigé ici, cf incident 410 sur
  /documents/{id}/download).
"""
import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.agent import Agent
from app.db.models.conversation import Conversation, Message
from app.db.models.corpus import Corpus, CorpusDocument
from app.db.models.dataset import Dataset, DatasetColumn
from app.db.models.document import Chunk, Document
from app.db.models.persona import Persona, PersonaCorpus
from app.db.models.user import User
from app.db.session import AsyncSessionLocal
from app.services.storage import FileStorage

logger = logging.getLogger(__name__)

DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"
FIXTURE_PATH = DEMO_DATA_DIR / "fixture.json"
SOURCE_FILES_DIR = DEMO_DATA_DIR / "source_files"


async def seed_demo_account() -> None:
    settings = get_settings()

    if not FIXTURE_PATH.exists():
        logger.warning(
            "Fixture démo introuvable (%s) — seed ignoré. "
            "Génère-la avec scripts/generate_demo_fixture.py.",
            FIXTURE_PATH,
        )
        return

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == settings.DEMO_ACCOUNT_EMAIL))
        demo_user_exists = result.scalar_one_or_none() is not None

        if demo_user_exists:
            logger.info(
                "Compte démo déjà présent (%s), lignes BDD conservées "
                "(fichiers physiques restaurés quand même, cf plus bas)",
                settings.DEMO_ACCOUNT_EMAIL,
            )
        else:
            await _insert_demo_rows(db, fixture, settings)

    # Fichiers physiques (uploads/ éphémère) : restaurés à CHAQUE démarrage,
    # que les lignes BDD ci-dessus existaient déjà ou non -- Neon persiste
    # entre redéploiements, le disque non. Idempotent par fichier (skip si
    # déjà présent).
    restore_demo_files(fixture)


async def _insert_demo_rows(db: AsyncSession, fixture: dict, settings: Settings) -> None:
    """Insère les lignes BDD du compte démo (dataset, corpus, persona,
    conversations). Appelé une seule fois -- cf idempotence par existence
    du compte démo dans seed_demo_account()."""
    result = await db.execute(select(Agent).where(Agent.slug == "vector"))
    vector_agent = result.scalar_one_or_none()
    if not vector_agent:
        logger.warning("Agent 'vector' introuvable — lance d'abord app.db.seed. Seed démo ignoré.")
        return

    # --- Utilisateur démo (mot de passe hashé depuis settings, pas
    # depuis le fixture -- reste modifiable via DEMO_ACCOUNT_PASSWORD
    # sans avoir à régénérer le fixture) ---
    from app.core.security import hash_password

    demo_user = User(
        id=UUID(fixture["demo_user"]["id"]),
        email=settings.DEMO_ACCOUNT_EMAIL,
        password_hash=hash_password(settings.DEMO_ACCOUNT_PASSWORD),
        full_name=fixture["demo_user"]["full_name"],
        is_active=True,
        has_seen_welcome=True,
    )
    db.add(demo_user)

    # --- Dataset + colonnes ---
    ds = fixture["dataset"]
    dataset = Dataset(
        id=UUID(ds["id"]),
        user_id=demo_user.id,
        name=ds["name"],
        description=ds["description"],
        original_filename=ds["original_filename"],
        file_path=ds["file_path"],
        file_size_bytes=ds["file_size_bytes"],
        row_count=ds["row_count"],
        column_count=ds["column_count"],
        quality_score=ds["quality_score"],
        quality_issues=ds["quality_issues"],
        status=ds["status"],
        raw_data_sample=ds["raw_data_sample"],
        semantic_analysis=ds["semantic_analysis"],
        auto_kpis=ds["auto_kpis"],
    )
    db.add(dataset)
    await db.flush()

    for col in fixture["dataset_columns"]:
        db.add(
            DatasetColumn(
                id=UUID(col["id"]),
                dataset_id=UUID(col["dataset_id"]),
                name=col["name"],
                dtype=col["dtype"],
                is_nullable=col["is_nullable"],
                is_date_main=col["is_date_main"],
                unique_count=col["unique_count"],
                null_count=col["null_count"],
                sample_values=col["sample_values"],
                numeric_stats=col["numeric_stats"],
                categorical_stats=col["categorical_stats"],
                date_stats=col["date_stats"],
            )
        )

    # --- Documents + chunks (avec embeddings figés) ---
    for doc in fixture["documents"]:
        db.add(
            Document(
                id=UUID(doc["id"]),
                user_id=demo_user.id,
                name=doc["name"],
                original_filename=doc["original_filename"],
                file_path=doc["file_path"],
                file_size_bytes=doc["file_size_bytes"],
                file_type=doc["file_type"],
                status=doc["status"],
                chunk_count=doc["chunk_count"],
                page_count=doc["page_count"],
                doc_metadata=doc["doc_metadata"],
            )
        )
    await db.flush()

    for chunk in fixture["chunks"]:
        db.add(
            Chunk(
                id=UUID(chunk["id"]),
                document_id=UUID(chunk["document_id"]),
                chunk_index=chunk["chunk_index"],
                page_number=chunk["page_number"],
                content=chunk["content"],
                token_count=chunk["token_count"],
                embedding=chunk["embedding"],
            )
        )

    # --- Corpus ---
    corpus = fixture["corpus"]
    db.add(
        Corpus(
            id=UUID(corpus["id"]),
            user_id=demo_user.id,
            name=corpus["name"],
            description=corpus["description"],
        )
    )
    await db.flush()
    for doc in fixture["documents"]:
        db.add(CorpusDocument(corpus_id=UUID(corpus["id"]), document_id=UUID(doc["id"])))
    await db.flush()

    # --- Persona ---
    persona = fixture["persona"]
    db.add(
        Persona(
            id=UUID(persona["id"]),
            user_id=demo_user.id,
            name=persona["name"],
            description=persona["description"],
            system_prompt=persona["system_prompt"],
            icon=persona["icon"],
            color=persona["color"],
            is_system=persona["is_system"],
            is_active=persona["is_active"],
        )
    )
    await db.flush()
    db.add(PersonaCorpus(persona_id=UUID(persona["id"]), corpus_id=UUID(corpus["id"])))
    await db.flush()

    # --- Conversations + messages ---
    for conv in fixture["conversations"]:
        db.add(
            Conversation(
                id=UUID(conv["id"]),
                user_id=demo_user.id,
                agent_id=vector_agent.id,
                persona_id=UUID(conv["persona_id"]),
                title=conv["title"],
            )
        )
    for msg in fixture["messages"]:
        db.add(
            Message(
                id=UUID(msg["id"]),
                conversation_id=UUID(msg["conversation_id"]),
                role=msg["role"],
                message_kind=msg["message_kind"],
                content=msg["content"],
                sources=msg["sources"],
            )
        )

    await db.commit()
    logger.info(
        "Compte démo créé : %s (dataset, corpus, persona, %d conversations)",
        settings.DEMO_ACCOUNT_EMAIL,
        len(fixture["conversations"]),
    )


# Note : cette fonction restaure les fichiers physiques indépendamment
# de l'état de la base. Si fixture.json est modifié après un premier
# seed, les fichiers seront ré-écrits (idempotents sur le path) mais les
# rows DB (créées par _insert_demo_rows lors du 1er boot) resteront
# celles de la version originale du fixture. Pour resynchroniser, wipe
# le demo user en DB, le prochain boot recréera cohérent.
def restore_demo_files(fixture: dict) -> None:
    """Restaure les fichiers physiques du compte démo (CSV/PDF/DOCX) sur
    le disque éphémère, depuis les fichiers embarqués dans l'image Docker.

    Appelé à CHAQUE démarrage de conteneur, indépendamment de l'état des
    lignes BDD (cf docstring du module) -- idempotent par fichier (skip
    si déjà présent sur disque, pas de re-écriture inutile).
    """
    storage = FileStorage()
    name_by_ext = {
        ".csv": SOURCE_FILES_DIR / "ibm_sales_pipeline_2025.csv",
        ".pdf": SOURCE_FILES_DIR / "ibm_strategy_report_2025.pdf",
        ".docx": SOURCE_FILES_DIR / "ibm_technology_whitepaper.docx",
    }
    file_paths = [
        fixture["dataset"]["file_path"],
        *[d["file_path"] for d in fixture["documents"]],
    ]

    restored = 0
    for file_path in file_paths:
        dest = storage.get_full_path(file_path)
        if dest.exists():
            continue
        ext = Path(file_path).suffix.lower()
        source = name_by_ext[ext]
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
        restored += 1

    if restored:
        logger.info(
            "Fichiers démo restaurés sur disque : %d/%d", restored, len(file_paths)
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_demo_account())
