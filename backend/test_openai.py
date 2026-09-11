"""Test temporaire — vrai appel OpenAI pour vérifier que tout marche."""
import asyncio
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.base import Message


async def main():
    provider = OpenAIProvider()

    print("\n=== Test 1 : chat() non-streaming ===")
    response = await provider.chat(
        messages=[
            Message("system", "Tu es un assistant concis."),
            Message("user", "Réponds en une seule phrase : qu'est-ce qu'une API ?"),
        ]
    )
    print(f"Réponse : {response}")

    print("\n=== Test 2 : chat_stream() streaming ===")
    print("Réponse : ", end="", flush=True)
    async for token in provider.chat_stream(
        messages=[
            Message("system", "Tu es un assistant concis."),
            Message("user", "Compte de 1 à 5 en français."),
        ]
    ):
        print(token, end="", flush=True)
    print()

    print("\n=== Test 3 : embed() ===")
    embeddings = await provider.embed(["Bonjour le monde", "Hello world"])
    print(f"Nombre d'embeddings : {len(embeddings)}")
    print(f"Dimension : {len(embeddings[0])}")
    print(f"Premiers floats : {embeddings[0][:5]}")

    print("\n=== Test 4 : structured_output() ===")
    result = await provider.structured_output(
        messages=[Message("user", "Donne-moi 3 fruits avec leur couleur.")],
        json_schema={
            "name": "fruits_list",
            "schema": {
                "type": "object",
                "properties": {
                    "fruits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "color": {"type": "string"},
                            },
                            "required": ["name", "color"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["fruits"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    )
    print(f"Résultat : {result}")


if __name__ == "__main__":
    asyncio.run(main())