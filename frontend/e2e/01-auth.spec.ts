import { test, expect } from "@playwright/test";
import { registerAndLogin, loginExisting, logout } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Authentification", () => {
  test("un nouvel utilisateur peut se créer un compte et arriver sur le chat", async ({
    page,
  }) => {
    const email = uniqueEmail("new");
    await registerAndLogin(page, email, "SecurePass123!");

    await expect(page).toHaveURL("/");
    await expect(
      page.locator('input[placeholder*="Poser une question" i]'),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("un utilisateur existant peut se reconnecter puis se déconnecter", async ({
    page,
  }) => {
    const email = uniqueEmail("logout");
    const password = "SecurePass123!";
    await registerAndLogin(page, email, password);

    await logout(page);
    await expect(page).toHaveURL(/\/login/);

    // Reconnexion avec le meme compte
    await loginExisting(page, email, password);
    await expect(page).toHaveURL("/");
  });

  test("un token invalide en localStorage redirige vers /login", async ({
    page,
    context,
  }) => {
    await context.addInitScript(() => {
      localStorage.setItem(
        "vector-auth",
        JSON.stringify({
          state: { token: "invalid_token_xyz", user: null, isAuthenticated: true },
          version: 0,
        }),
      );
    });

    await page.goto("/");
    // Toute requete API avec ce faux token echoue en 401 -> l'intercepteur
    // global (lib/api.ts) deconnecte et redirige vers /login.
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});
