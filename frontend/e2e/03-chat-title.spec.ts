import { test, expect } from "@playwright/test";
import { registerAndLogin, getAuthToken, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const API_BASE_URL = "http://localhost:8000";

test.describe("Chat basique et titre auto-généré", () => {
  test("une question complète reçoit une réponse, un compteur de tokens et un titre auto", async ({
    page,
  }) => {
    test.slow(); // depend d'un vrai streaming OpenAI, peut prendre 15-20s

    const email = uniqueEmail("chat");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Compare les ventes de smartphones par région");
    await chatInput.press("Enter");

    // Attend la reponse complete (streaming SSE)
    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    // Attend la fin du texte + persistance (le compteur de tokens n'apparait
    // qu'une fois le message assistant persiste en base avec son usage).
    await expect(page.getByText(/\d+\s*tokens?\s*·/i).first()).toBeVisible({
      timeout: 20_000,
    });

    // Le titre auto est genere en fire-and-forget apres la persistance :
    // on verifie via l'API plutot que le DOM (plus fiable, pas de flakiness
    // sur la re-render de la sidebar).
    const token = await getAuthToken(page);
    await expect(async () => {
      const conv = await page.evaluate(
        async ({ id, token, apiBase }) => {
          const res = await fetch(`${apiBase}/conversations/${id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          return res.json();
        },
        { id: activeId, token, apiBase: API_BASE_URL },
      );
      expect(conv.title).not.toBe("Nouvelle discussion");
    }).toPass({ timeout: 15_000, intervals: [1000] });

    await deleteConversationViaApi(page, activeId);
  });
});
