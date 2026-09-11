"""Tests des endpoints d'authentification."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Un nouvel utilisateur peut s'inscrire."""
    import uuid
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    response = await client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": "secret12345",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == unique_email
    assert "id" in data
    assert "password_hash" not in data  


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Inscription refusée si l'email existe déjà."""
    # On essaie d'inscrire un utilisateur existant
    payload = {"email": "duplicate@example.com", "password": "secret12345"}
    await client.post("/auth/register", json=payload)
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login avec bonnes credentials retourne un token."""
    # D'abord inscrire
    await client.post(
        "/auth/register",
        json={"email": "login_test@example.com", "password": "secret12345"},
    )
    # Puis se logger
    response = await client.post(
        "/auth/login",
        data={"username": "login_test@example.com", "password": "secret12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login refusé si mauvais password."""
    await client.post(
        "/auth/register",
        json={"email": "wrong_pwd@example.com", "password": "secret12345"},
    )
    response = await client.post(
        "/auth/login",
        data={"username": "wrong_pwd@example.com", "password": "mauvaispassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    """/users/me sans token retourne 401."""
    response = await client.get("/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient):
    """/users/me avec token valide retourne l'utilisateur."""
    # Inscription + login
    await client.post(
        "/auth/register",
        json={"email": "me_test@example.com", "password": "secret12345"},
    )
    login_response = await client.post(
        "/auth/login",
        data={"username": "me_test@example.com", "password": "secret12345"},
    )
    token = login_response.json()["access_token"]

    # Appel /me avec le token
    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me_test@example.com"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient, fake):
    """Inscription refusée si le mot de passe fait moins de 8 caractères
    (validation Pydantic UserCreate.password, min_length=8)."""
    response = await client.post(
        "/auth/register",
        json={"email": fake.email(), "password": "weak"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    """/users/me avec un token invalide (mal formé / signature invalide)
    retourne 401, pas une 500 ou une autre erreur silencieuse."""
    response = await client.get(
        "/users/me",
        headers={"Authorization": "Bearer garbage_not_a_real_jwt"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_account_rejected(client: AsyncClient, fake, db_session):
    """Un compte desactive (is_active=False) ne peut pas se connecter (403),
    meme avec le bon mot de passe."""
    from sqlalchemy import select

    from app.db.models.user import User

    email = fake.email()
    password = "secret12345"
    await client.post("/auth/register", json={"email": email, "password": password})

    user = (await db_session.execute(select(User).where(User.email == email))).scalar_one()
    user.is_active = False
    await db_session.commit()

    response = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert response.status_code == 403

# ============================================================
# Regle password renforcee (S5 J50) — cas au-dela du "trop court" deja
# teste dans test_register_weak_password.
# ============================================================

# Test ajoute J53 : couvre specifiquement la branche "assez long mais
# sans chiffre" de validate_password_strength, jamais exercee via l'API
# (seul le cas min_length<8 etait teste).
@pytest.mark.asyncio
async def test_register_password_without_digit_rejected(client: AsyncClient, fake):
    response = await client.post(
        "/auth/register",
        json={"email": fake.email(), "password": "aucunchiffre"},
    )
    assert response.status_code == 422


# Test ajoute J53 : symetrique, branche "assez long mais sans lettre".
@pytest.mark.asyncio
async def test_register_password_without_letter_rejected(client: AsyncClient, fake):
    response = await client.post(
        "/auth/register",
        json={"email": fake.email(), "password": "12345678"},
    )
    assert response.status_code == 422


# ============================================================
# JWT — cas au-dela du "garbage token" deja teste dans
# test_me_with_invalid_token.
# ============================================================

# Test ajoute J53 : un token JWT structurellement valide mais expire doit
# etre rejete au meme titre qu'un token malforme -- decode_access_token
# utilise jose.jwt.decode qui verifie l'expiration automatiquement, mais
# ce chemin precis n'etait jamais exerce.
@pytest.mark.asyncio
async def test_expired_jwt_rejected(client: AsyncClient, fake):
    from datetime import timedelta

    from app.core.security import create_access_token

    email = fake.email()
    register = await client.post(
        "/auth/register", json={"email": email, "password": "secret12345"}
    )
    user_id = register.json()["id"]

    expired_token = create_access_token(subject=user_id, expires_delta=timedelta(seconds=-1))
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


# Test ajoute J53 : un JWT correctement forme mais signe avec une AUTRE cle
# (ex: cle volee/devinee, ou bug de config entre environnements) doit etre
# rejete -- verifie explicitement que decode_access_token valide la
# signature et pas seulement la structure/expiration du token.
@pytest.mark.asyncio
async def test_jwt_wrong_signature_rejected(client: AsyncClient, fake):
    from jose import jwt

    from app.core.config import get_settings

    settings = get_settings()

    email = fake.email()
    register = await client.post(
        "/auth/register", json={"email": email, "password": "secret12345"}
    )
    user_id = register.json()["id"]

    forged_token = jwt.encode(
        {"sub": user_id, "exp": 9999999999},
        "une-cle-secrete-totalement-differente",
        algorithm=settings.ALGORITHM,
    )
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {forged_token}"}
    )
    assert response.status_code == 401


# Test ajoute J53 : apres suppression definitive du compte (S5 J50), une
# tentative de login doit renvoyer EXACTEMENT le meme message generique
# qu'un mauvais mot de passe -- aucune fuite d'info sur le fait que le
# compte a existe puis a ete supprime.
@pytest.mark.asyncio
async def test_login_after_account_deletion_generic_error(client: AsyncClient, fake):
    email = fake.email()
    password = "secret12345"
    register = await client.post(
        "/auth/register", json={"email": email, "password": password}
    )
    login = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    token = login.json()["access_token"]

    delete_resp = await client.request(
        "DELETE",
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": password},
    )
    assert delete_resp.status_code == 204

    relogin = await client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    assert relogin.status_code == 401
    assert relogin.json()["detail"] == "Email ou mot de passe incorrect"
