import { Page, expect } from "@playwright/test";

const API_BASE_URL = "http://localhost:8000";

/**
 * Inscrit un nouvel utilisateur puis attend l'atterrissage sur "/".
 * Par defaut, court-circuite l'onboarding (WelcomeScreen + tour guide) via
 * l'API pour ne pas polluer les tests qui ne portent pas sur l'onboarding
 * lui-meme (voir e2e/11-tour-guide.spec.ts / 12-dataset-example.spec.ts pour
 * les tests qui veulent explicitement voir l'onboarding : skipOnboarding: false).
 */
export async function registerAndLogin(
  page: Page,
  email: string,
  password: string,
  options: { skipOnboarding?: boolean } = {},
): Promise<void> {
  const { skipOnboarding = true } = options;

  await page.goto("/register", { waitUntil: "networkidle" });
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button:has-text("Créer mon compte")');
  // Timeout genereux : en mode dev Next.js compile "/" a la volee au premier
  // hit, ce qui peut prendre 10-20s en plus de l'appel register+login+me.
  await page.waitForFunction(() => !location.pathname.includes("/register"), {
    timeout: 45_000,
  });

  if (skipOnboarding) {
    const token = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-auth");
      return raw ? JSON.parse(raw).state.token : null;
    });
    if (token) {
      await page.evaluate(
        async ({ token, apiBase }: { token: string; apiBase: string }) => {
          await fetch(`${apiBase}/users/me/onboarding-complete`, {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` },
          });
        },
        { token, apiBase: API_BASE_URL },
      );
      await page.reload({ waitUntil: "domcontentloaded" });
    }
  }

  // Laisse le temps a useAgentChat() de charger les conversations depuis le
  // backend (loadFromBackend, declenche par un useEffect apres le mount) et
  // a J41.A de creer la conversation "Nouvelle discussion" du login.
  await page.waitForTimeout(1500);
}

/** Connexion avec un compte deja existant. */
export async function loginExisting(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", password);
  await page.click('button:has-text("Se connecter")');
  await page.waitForFunction(() => !location.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

/** Deconnexion via le UserMenu (avatar -> dropdown -> "Se deconnecter",
 * depuis S5 J50 -- avant, le bouton avatar deconnectait directement). */
export async function logout(page: Page): Promise<void> {
  await page.getByTestId("user-menu-trigger").click();
  await page.getByRole("menuitem", { name: /se déconnecter/i }).click();
  await expect(page).toHaveURL(/\/login/, { timeout: 5_000 });
}

/**
 * Ferme le WelcomeScreen ("Explorer par moi-meme") puis le tour guide qui
 * s'enchaine automatiquement, si presents. A utiliser quand skipOnboarding
 * (registerAndLogin) n'a pas ete utilise, ou par securite en debut de test.
 */
export async function dismissOnboardingIfPresent(page: Page): Promise<void> {
  const exploreButton = page.getByRole("button", { name: /explorer par moi-même/i });
  if (await exploreButton.isVisible().catch(() => false)) {
    await exploreButton.click();
  }
  const skipTourButton = page.getByRole("button", { name: /passer le tour/i });
  if (await skipTourButton.isVisible().catch(() => false)) {
    await skipTourButton.click();
  }
}

/** Recupere le token JWT courant depuis le localStorage (pour appels API directs). */
export async function getAuthToken(page: Page): Promise<string | null> {
  return page.evaluate(() => {
    const raw = localStorage.getItem("vector-auth");
    return raw ? JSON.parse(raw).state.token : null;
  });
}

/** Poste un message directement via l'API (pas d'UI, pas de vrai appel LLM —
 * utile pour peupler une conversation de test sans dependre d'OpenAI).
 * attachments : shape brute Message.attachments (voir image_attachments.py),
 * optionnelle — pour tester le rendu d'images sans upload reel ni vision LLM. */
export async function postMessageViaApi(
  page: Page,
  conversationId: string,
  role: string,
  content: string,
  attachments?: Record<string, unknown>[],
): Promise<void> {
  const token = await getAuthToken(page);
  if (!token) return;
  await page.evaluate(
    async (
      { id, role, content, attachments, token, apiBase }:
        {
          id: string; role: string; content: string;
          attachments: Record<string, unknown>[] | undefined;
          token: string; apiBase: string;
        },
    ) => {
      await fetch(`${apiBase}/conversations/${id}/messages`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          role,
          message_kind: role === "user" ? "user" : "agent",
          content,
          attachments: attachments ?? null,
        }),
      });
    },
    { id: conversationId, role, content, attachments, token, apiBase: API_BASE_URL },
  );
}

/** Nettoyage : supprime une conversation via l'API directement (pas d'UI). */
export async function deleteConversationViaApi(
  page: Page,
  conversationId: string,
): Promise<void> {
  const token = await getAuthToken(page);
  if (!token) return;
  await page.evaluate(
    async ({ id, token, apiBase }: { id: string; token: string; apiBase: string }) => {
      await fetch(`${apiBase}/conversations/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
    },
    { id: conversationId, token, apiBase: API_BASE_URL },
  );
}

/** Nettoyage : supprime un dataset via l'API directement (pas d'UI). */
export async function deleteDatasetViaApi(page: Page, datasetId: string): Promise<void> {
  const token = await getAuthToken(page);
  if (!token) return;
  await page.evaluate(
    async ({ id, token, apiBase }: { id: string; token: string; apiBase: string }) => {
      await fetch(`${apiBase}/datasets/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
    },
    { id: datasetId, token, apiBase: API_BASE_URL },
  );
}
