import { APIRequestContext, Page } from "@playwright/test";

const API_BASE_URL = "http://localhost:8000";

/**
 * Cree un compte directement via l'API (pas d'UI, pas de navigation) --
 * plus rapide que registerAndLogin quand le test ne porte pas sur le
 * formulaire d'inscription lui-meme. Retourne le token JWT.
 */
export async function createTestUser(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<{ token: string; userId: string }> {
  const register = await request.post(`${API_BASE_URL}/auth/register`, {
    data: { email, password },
  });
  if (!register.ok()) {
    throw new Error(`createTestUser: register a échoué (${register.status()})`);
  }
  const user = await register.json();

  const login = await request.post(`${API_BASE_URL}/auth/login`, {
    form: { username: email, password, grant_type: "password" },
  });
  if (!login.ok()) {
    throw new Error(`createTestUser: login a échoué (${login.status()})`);
  }
  const { access_token } = await login.json();

  return { token: access_token, userId: user.id };
}

/**
 * Injecte un token deja obtenu (cf createTestUser) dans le localStorage
 * puis navigue -- equivalent d'une connexion UI mais instantane, pour les
 * specs qui ne testent pas le login lui-meme.
 */
export async function loginAs(page: Page, token: string): Promise<void> {
  const me = await page.request.get(`${API_BASE_URL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const user = await me.json();

  await page.addInitScript(
    ({ token, user }: { token: string; user: unknown }) => {
      localStorage.setItem(
        "vector-auth",
        JSON.stringify({
          state: { token, user, isAuthenticated: true },
          version: 0,
        }),
      );
    },
    { token, user },
  );
  await page.goto("/");
  await page.waitForFunction(() => location.pathname === "/", { timeout: 10_000 });
}

/** Supprime definitivement le compte de test (hard delete + cascade, S5 J50). */
export async function deleteTestUser(
  request: APIRequestContext,
  token: string,
  password: string,
): Promise<void> {
  await request.delete(`${API_BASE_URL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { password },
  });
}
