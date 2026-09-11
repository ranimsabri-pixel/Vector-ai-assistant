"""Schémas Pydantic pour l'authentification."""
from uuid import UUID

from pydantic import BaseModel


class Token(BaseModel):
    """Réponse d'un login ou register : le token JWT."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Contenu décodé d'un JWT."""
    sub: str  # l'id utilisateur (en str car JWT n'aime pas les UUID directement)
    exp: int  # timestamp d'expiration

    @property
    def user_id(self) -> UUID:
        """Retourne le sub converti en UUID."""
        return UUID(self.sub)
