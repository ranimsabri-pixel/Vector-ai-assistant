"""ONE-OFF script (S5 J55) — génère le contenu de démo (dataset IBM
profilé, corpus IBM embeddé, persona, conversations) via de VRAIS appels
OpenAI, et fige le résultat dans app/data/demo/fixture.json.

Ce script ne tourne JAMAIS en production. app/db/seed_demo.py (chargé au
démarrage du conteneur Render) se contente d'insérer ce JSON figé — aucun
appel OpenAI au boot, coût nul et déterministe à chaque redéploiement.

Les IDs (dataset, documents, corpus, persona, conversations, y compris le
compte démo lui-même) NE SONT PAS fixés à l'avance : on laisse SQLAlchemy
générer des UUID normaux pendant cette exécution unique, et on fige les
valeurs obtenues dans le fixture. seed_demo.py réutilise ensuite ces MÊMES
valeurs (lues depuis le JSON) à chaque démarrage de conteneur — la
déterminisme vient du fichier figé committé, pas d'un schéma d'ID custom.

Prérequis : Postgres local up (docker compose up -d db), migrations
appliquées (alembic upgrade head), OPENAI_API_KEY valide dans backend/.env,
et le agent système "vector" déjà seedé (python -m app.db.seed).

Usage :
    python scripts/generate_demo_fixture.py
"""
import asyncio
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models.agent import Agent
from app.db.models.conversation import Conversation, Message
from app.db.models.corpus import Corpus
from app.db.models.dataset import Dataset, DatasetColumn
from app.db.models.document import Chunk, Document
from app.db.models.persona import Persona, PersonaCorpus
from app.db.models.user import User
from app.db.session import AsyncSessionLocal
from app.services.corpus import CorpusService
from app.services.datasets import DatasetService
from app.services.documents import DocumentService
from app.services.ingestion import ingest_document
from app.services.storage import FileStorage

SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "references" / "test_ibm_data"
DEMO_DATA_DIR = Path(__file__).resolve().parent.parent / "app" / "data" / "demo"
FIXTURE_PATH = DEMO_DATA_DIR / "fixture.json"
SOURCE_FILES_DIR = DEMO_DATA_DIR / "source_files"

CSV_NAME = "ibm_sales_pipeline_2025.csv"
PDF_NAME = "ibm_strategy_report_2025.pdf"
DOCX_NAME = "ibm_technology_whitepaper.docx"

# Conversations pré-écrites (S5 J55) — pas d'appel LLM, contenu rédigé à la
# main sur la base du corpus/dataset IBM réels (cf docs/DEPLOYMENT_RENDER.md
# décision G, question ouverte 6c : rédaction autorisée en Phase 2).
EXAMPLE_CONVERSATIONS = [
    {
        "title": "Pipeline commercial EMEA — état des lieux",
        "messages": [
            {
                "role": "user",
                "message_kind": "user",
                "content": "Peux-tu me faire un résumé du pipeline commercial pour la région EMEA ?",
            },
            {
                "role": "assistant",
                "message_kind": "agent",
                "content": (
                    "Voici un résumé du pipeline **EMEA** à partir du dataset *IBM Sales "
                    "Pipeline 2025* :\n\n"
                    "- Plusieurs opportunités actives sur les lignes **IBM watsonx** et "
                    "**IBM Cloud Pak**, avec des montants allant de quelques centaines de "
                    "milliers à plus d'un million de dollars.\n"
                    "- Les stades varient de *Discovery* à *Negotiation*, avec une "
                    "concurrence fréquente de Microsoft Azure et SAP sur les gros comptes.\n"
                    "- Le `customer_health_score` est un bon indicateur avancé : les comptes "
                    "sous 50 méritent un suivi rapproché avant la clôture.\n\n"
                    "**Recommandations**\n"
                    "1. **(Haute)** Prioriser les deals en *Negotiation* avec un score de "
                    "santé client élevé — probabilité de closing la plus forte.\n"
                    "2. **(Moyenne)** Renforcer le suivi des comptes disputés face à "
                    "Microsoft Azure, concurrent le plus présent sur la région.\n"
                    "3. **(Basse)** Analyser les renouvellements en retard pour anticiper "
                    "le churn."
                ),
            },
        ],
    },
    {
        "title": "Comparaison des lignes de produits",
        "messages": [
            {
                "role": "user",
                "message_kind": "user",
                "content": "Quelle ligne de produit génère le plus d'opportunités : watsonx ou Cloud Pak ?",
            },
            {
                "role": "assistant",
                "message_kind": "agent",
                "content": (
                    "D'après le profilage du dataset, **IBM watsonx** et **IBM Cloud Pak** "
                    "sont les deux lignes de produit dominantes du pipeline 2025, réparties "
                    "sur l'ensemble des régions (Americas, EMEA, Asia Pacific).\n\n"
                    "Pour une comparaison précise (nombre de deals, montant total, taux de "
                    "closing par ligne), ouvre le **dashboard** généré sur ce dataset — les "
                    "KPIs auto-calculés incluent la répartition par `product_line` et par "
                    "`deal_stage`, avec les montants agrégés en `opportunity_amount_usd`."
                ),
            },
        ],
    },
    {
        "title": "Stratégie IBM 2025 — question sur le corpus",
        "messages": [
            {
                "role": "user",
                "message_kind": "user",
                "content": "D'après le rapport stratégique 2025, quels sont les grands axes technologiques d'IBM ?",
            },
            {
                "role": "assistant",
                "message_kind": "agent",
                "content": (
                    "D'après le **Rapport Stratégique IBM 2025** et le **Livre Blanc "
                    "Technologique**, les grands axes portent sur l'IA d'entreprise "
                    "(watsonx), le cloud hybride (Cloud Pak) et l'accompagnement des "
                    "grands comptes dans leur transformation.\n\n"
                    "Consulte les sources ci-dessous pour les passages exacts du corpus."
                ),
                "sources": [
                    {
                        "document_name": PDF_NAME,
                        "page_number": 1,
                        "content_preview": "Extrait du rapport stratégique IBM 2025...",
                    }
                ],
            },
        ],
    },
]


def ser(value):
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def row_to_dict(row, columns):
    result = {c: ser(getattr(row, c)) for c in columns}
    # file_path est écrit par pathlib avec le séparateur natif de l'OS qui
    # génère le fixture (Windows -> \) -- le conteneur Render est Linux,
    # qui traiterait un \ comme un caractère de nom de fichier littéral,
    # pas un séparateur. Normalisé en '/' , valide sur les deux OS.
    if "file_path" in result and result["file_path"]:
        result["file_path"] = result["file_path"].replace("\\", "/")
    return result


async def main() -> None:
    storage = FileStorage()
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Agent).where(Agent.slug == "vector"))
        vector_agent = result.scalar_one_or_none()
        if not vector_agent:
            raise RuntimeError(
                "Agent 'vector' introuvable — lance `python -m app.db.seed` avant ce script."
            )

        # --- Utilisateur démo ---
        result = await db.execute(select(User).where(User.email == settings.DEMO_ACCOUNT_EMAIL))
        demo_user = result.scalar_one_or_none()
        if not demo_user:
            demo_user = User(
                email=settings.DEMO_ACCOUNT_EMAIL,
                password_hash=hash_password(settings.DEMO_ACCOUNT_PASSWORD),
                full_name="Compte de démonstration",
                is_active=True,
                has_seen_welcome=True,
            )
            db.add(demo_user)
            await db.commit()
            await db.refresh(demo_user)
        print(f"✓ Utilisateur démo (id={demo_user.id})")

        # ============================================================
        # Dataset — IBM Sales Pipeline 2025
        # ============================================================
        dataset_service = DatasetService(db, storage)

        result = await db.execute(
            select(Dataset).where(Dataset.user_id == demo_user.id, Dataset.name == "IBM Sales Pipeline")
        )
        dataset = result.scalar_one_or_none()
        if dataset:
            print(f"✓ Dataset déjà présent, réutilisé (id={dataset.id}) — pas de nouvel appel LLM")
        else:
            with open(SOURCE_DIR / CSV_NAME, "rb") as f:
                upload = UploadFile(file=f, filename=CSV_NAME)
                dataset = await dataset_service.upload(
                    demo_user,
                    upload,
                    name="IBM Sales Pipeline",
                    description="Pipeline commercial IBM 2025 (comptes, montants, stades, régions).",
                )
            print(f"✓ Dataset uploadé (id={dataset.id})")

            dataset = await dataset_service.profile(demo_user, dataset.id)
            print("✓ Dataset profilé")
            dataset = await dataset_service.analyze(demo_user, dataset.id)
            print("✓ Analyse sémantique terminée (appel LLM)")
            dataset = await dataset_service.generate_auto_kpis(demo_user, dataset.id)
            print("✓ Auto-KPIs générés")
            dataset = await dataset_service.generate_advanced_kpis(demo_user, dataset.id)
            print("✓ KPIs avancés générés")
            await dataset_service.calculate_all_auto_kpis(demo_user, dataset.id)
            print("✓ KPIs calculés")

        result = await db.execute(select(Dataset).where(Dataset.id == dataset.id))
        dataset = result.scalar_one()
        result = await db.execute(
            select(DatasetColumn).where(DatasetColumn.dataset_id == dataset.id)
        )
        dataset_columns = result.scalars().all()

        # ============================================================
        # Corpus — Documentation Stratégique IBM 2025 (PDF + DOCX)
        # ============================================================
        document_service = DocumentService(db, storage)
        documents = []

        for filename in (PDF_NAME, DOCX_NAME):
            result = await db.execute(
                select(Document).where(
                    Document.user_id == demo_user.id, Document.original_filename == filename
                )
            )
            doc = result.scalar_one_or_none()
            if doc:
                print(f"✓ Document déjà présent, réutilisé : {filename} — pas de nouvel embedding")
            else:
                with open(SOURCE_DIR / filename, "rb") as f:
                    upload = UploadFile(file=f, filename=filename)
                    doc = await document_service.upload(demo_user, upload, name=filename)

                absolute_path = str(storage.get_full_path(doc.file_path))
                await ingest_document(doc.id, absolute_path, db)
                print(f"✓ Document ingéré (embeddings) : {filename}")

            result = await db.execute(select(Document).where(Document.id == doc.id))
            documents.append(result.scalar_one())

        result = await db.execute(
            select(Corpus).where(
                Corpus.user_id == demo_user.id, Corpus.name == "Documentation Stratégique IBM 2025"
            )
        )
        corpus = result.scalar_one_or_none()
        if corpus:
            print(f"✓ Corpus déjà présent, réutilisé (id={corpus.id})")
        else:
            corpus_service = CorpusService(db)
            corpus = await corpus_service.create_corpus(
                demo_user,
                name="Documentation Stratégique IBM 2025",
                description="Rapport stratégique et livre blanc technologique IBM 2025.",
            )
            await corpus_service.add_documents(demo_user, corpus.id, [d.id for d in documents])
            print(f"✓ Corpus créé (id={corpus.id})")

        # ============================================================
        # Persona — Vector Analyste Finance IBM
        # ============================================================
        result = await db.execute(
            select(Persona).where(
                Persona.user_id == demo_user.id, Persona.name == "Vector Analyste Finance IBM"
            )
        )
        persona = result.scalar_one_or_none()
        if persona:
            print(f"✓ Persona déjà présent, réutilisé (id={persona.id})")
        else:
            persona = Persona(
                user_id=demo_user.id,
                name="Vector Analyste Finance IBM",
                description="Assistant spécialisé sur les données commerciales et stratégiques IBM.",
                system_prompt=(
                    "Tu es Vector, agissant comme analyste financier et commercial spécialisé "
                    "sur les données IBM (pipeline commercial, rapports stratégiques). Réponds "
                    "en français, avec précision, en citant les chiffres du dataset et les "
                    "passages du corpus quand c'est pertinent."
                ),
                icon="Briefcase",
                color="#0F62FE",
                is_system=False,
                is_active=True,
            )
            db.add(persona)
            await db.flush()
            # Lien direct via la table de jointure -- persona.corpora.append(...)
            # declenche un lazy-load synchrone hors contexte awaitable
            # (MissingGreenlet) en session async SQLAlchemy.
            db.add(PersonaCorpus(persona_id=persona.id, corpus_id=corpus.id))
            await db.commit()
            print(f"✓ Persona créé (id={persona.id})")
        corpus_row = corpus

        # ============================================================
        # Conversations d'exemple (pas d'appel LLM, contenu pré-écrit)
        # ============================================================
        result = await db.execute(
            select(Conversation).where(
                Conversation.user_id == demo_user.id, Conversation.persona_id == persona.id
            )
        )
        existing_convs = result.scalars().all()

        if existing_convs:
            conversation_ids = [c.id for c in existing_convs]
            print(f"✓ {len(conversation_ids)} conversations déjà présentes, réutilisées")
        else:
            conversation_ids = []
            for conv_spec in EXAMPLE_CONVERSATIONS:
                conversation = Conversation(
                    user_id=demo_user.id,
                    agent_id=vector_agent.id,
                    persona_id=persona.id,
                    title=conv_spec["title"],
                )
                db.add(conversation)
                await db.flush()
                conversation_ids.append(conversation.id)

                for msg_spec in conv_spec["messages"]:
                    message = Message(
                        conversation_id=conversation.id,
                        role=msg_spec["role"],
                        message_kind=msg_spec["message_kind"],
                        content=msg_spec["content"],
                        sources=msg_spec.get("sources"),
                    )
                    db.add(message)
                await db.commit()
            print(f"✓ {len(EXAMPLE_CONVERSATIONS)} conversations d'exemple créées")

        # ============================================================
        # Dump fixture JSON
        # ============================================================
        result = await db.execute(
            select(Message)
            .join(Conversation)
            .where(Conversation.id.in_(conversation_ids))
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        result = await db.execute(
            select(Chunk).where(Chunk.document_id.in_([d.id for d in documents]))
        )
        chunks = result.scalars().all()

        fixture = {
            "generated_at": datetime.now(UTC).isoformat(),
            "demo_user": row_to_dict(
                demo_user, ["id", "email", "password_hash", "full_name", "is_active", "has_seen_welcome"]
            ),
            "dataset": row_to_dict(
                dataset,
                [
                    "id", "user_id", "name", "description", "original_filename", "file_path",
                    "file_size_bytes", "row_count", "column_count", "quality_score",
                    "quality_issues", "status", "raw_data_sample", "semantic_analysis",
                    "auto_kpis",
                ],
            ),
            "dataset_columns": [
                row_to_dict(
                    c,
                    [
                        "id", "dataset_id", "name", "dtype", "is_nullable", "is_date_main",
                        "unique_count", "null_count", "sample_values", "numeric_stats",
                        "categorical_stats", "date_stats",
                    ],
                )
                for c in dataset_columns
            ],
            "documents": [
                row_to_dict(
                    d,
                    [
                        "id", "user_id", "name", "original_filename", "file_path", "file_size_bytes",
                        "file_type", "status", "chunk_count", "page_count", "doc_metadata",
                    ],
                )
                for d in documents
            ],
            "chunks": [
                {
                    **row_to_dict(
                        c,
                        ["id", "document_id", "chunk_index", "page_number", "content", "token_count"],
                    ),
                    "embedding": [float(x) for x in c.embedding] if c.embedding is not None else None,
                }
                for c in chunks
            ],
            "corpus": row_to_dict(corpus_row, ["id", "user_id", "name", "description"]),
            "persona": row_to_dict(
                persona,
                ["id", "user_id", "name", "description", "system_prompt", "icon", "color", "is_system", "is_active"],
            ),
            "conversations": [
                {"id": str(conv_id), "title": spec["title"], "agent_id": str(vector_agent.id), "persona_id": str(persona.id)}
                for spec, conv_id in zip(EXAMPLE_CONVERSATIONS, conversation_ids, strict=True)
            ],
            "messages": [
                row_to_dict(
                    m,
                    ["id", "conversation_id", "role", "message_kind", "content", "sources"],
                )
                for m in messages
            ],
        }

        def json_default(o):
            # Filet de sécurité pour les types numpy (int64/float32/bool_...)
            # qui se glissent dans les JSONB profilés par pandas (quality_issues,
            # numeric_stats...) et que json.dumps ne sait pas sérialiser nativement.
            if hasattr(o, "item"):
                return o.item()
            raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

        DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True)
        FIXTURE_PATH.write_text(
            json.dumps(fixture, indent=2, ensure_ascii=False, default=json_default), encoding="utf-8"
        )
        print(f"✓ Fixture écrite : {FIXTURE_PATH}")

        SOURCE_FILES_DIR.mkdir(parents=True, exist_ok=True)
        for name in (CSV_NAME, PDF_NAME, DOCX_NAME):
            shutil.copy(SOURCE_DIR / name, SOURCE_FILES_DIR / name)
        print(f"✓ Fichiers source copiés dans {SOURCE_FILES_DIR}")
        print(
            "Note : dataset['file_path'] / documents[*]['file_path'] pointent vers "
            "uploads/<demo_user_id>/... généré pendant CETTE exécution -- seed_demo.py "
            "recopie les fichiers source vers ces MÊMES chemins relatifs à chaque "
            "démarrage de conteneur (uploads/ est éphémère sur Render)."
        )


if __name__ == "__main__":
    asyncio.run(main())
