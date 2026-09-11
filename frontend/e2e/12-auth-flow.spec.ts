import { test, expect } from "@playwright/test";
import { registerAndLogin, loginExisting, logout } from "./helpers/auth";
import { createTestUser, deleteTestUser } from "./helpers/api";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

test.describe("Auth flow (S5 J52)", () => {
  test("signup avec email valide crée un compte et redirige vers le chat", async ({
    page,
  }) => {
    const email = uniqueEmail("signup");
    await registerAndLogin(page, email, PASSWORD);

    await expect(page).toHaveURL("/");
    await expect(
      page.locator('input[placeholder*="Poser une question" i]'),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("signup avec un email déjà utilisé affiche une erreur, sans créer de compte", async ({
    page,
    request,
  }) => {
    const email = uniqueEmail("dup");
    const { token } = await createTestUser(request, email, PASSWORD);

    await page.goto("/register");
    await page.fill("#email", email);
    await page.fill("#password", PASSWORD);
    await page.click('button:has-text("Créer mon compte")');

    // getByTestId plutot que getByText(regex) : "email.*utilisé" matchait
    // aussi le label statique "(min 8 caractères)" du champ mot de passe
    // en CI headless (strict mode violation, 2 elements) -- trouve via un
    // run CI reel, jamais reproduit en 3 passes locales. Cf docs/CI_CD.md.
    await expect(page.getByTestId("signup-error-message")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("signup-error-message")).toContainText(
      /existe déjà|already exists|email.*utilisé/i,
    );
    await expect(page).toHaveURL(/\/register/);

    await deleteTestUser(request, token, PASSWORD);
  });

  test("signup avec un mot de passe sans chiffre affiche une erreur", async ({
    page,
  }) => {
    const email = uniqueEmail("weakpwd");

    await page.goto("/register");
    await page.fill("#email", email);
    // 8+ caracteres (passe le minLength HTML5) mais sans chiffre -> 422 backend
    await page.fill("#password", "aucunchiffre");
    await page.click('button:has-text("Créer mon compte")');

    // getByTestId plutot que getByText(regex) : cf commentaire ci-dessus,
    // meme piege ("caractère" matchait le label ET le message d'erreur).
    await expect(page.getByTestId("signup-error-message")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("signup-error-message")).toContainText(
      /chiffre|caractère|invalide/i,
    );
    await expect(page).toHaveURL(/\/register/);
  });

  test("login avec identifiants valides mène au chat", async ({
    page,
    request,
  }) => {
    const email = uniqueEmail("loginok");
    const { token } = await createTestUser(request, email, PASSWORD);

    await loginExisting(page, email, PASSWORD);
    await expect(page).toHaveURL("/");

    await deleteTestUser(request, token, PASSWORD);
  });

  test("login avec identifiants invalides affiche un message générique", async ({
    page,
    request,
  }) => {
    const email = uniqueEmail("badlogin");
    const { token } = await createTestUser(request, email, PASSWORD);

    await page.goto("/login");
    await page.fill("#email", email);
    await page.fill("#password", "MauvaisMotDePasse1");
    await page.click('button:has-text("Se connecter")');

    const errorLocator = page.getByTestId("login-error-message");
    await expect(errorLocator).toBeVisible({ timeout: 10_000 });
    await expect(errorLocator).toContainText(/email ou mot de passe incorrect/i);
    await expect(page).toHaveURL(/\/login/);

    // Meme message pour un email qui n'existe pas du tout (pas de leak
    // d'info sur l'existence du compte).
    await page.fill("#email", uniqueEmail("doesnotexist"));
    await page.fill("#password", "PeuImporte123");
    await page.click('button:has-text("Se connecter")');
    await expect(errorLocator).toBeVisible({ timeout: 10_000 });

    await deleteTestUser(request, token, PASSWORD);
  });

  test("déconnexion depuis le UserMenu efface le token et redirige vers /login", async ({
    page,
  }) => {
    const email = uniqueEmail("logout");
    await registerAndLogin(page, email, PASSWORD);

    await logout(page);
    await expect(page).toHaveURL(/\/login/);

    const token = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-auth");
      return raw ? JSON.parse(raw).state.token : null;
    });
    expect(token).toBeNull();
  });

  test("un JWT falsifié en cours de session redirige vers /login", async ({
    page,
  }) => {
    const email = uniqueEmail("tamper");
    await registerAndLogin(page, email, PASSWORD);
    await expect(page).toHaveURL("/");

    // Falsifie le token d'une session par ailleurs valide, puis force un
    // appel API (reload -> chargement des conversations) qui doit echouer
    // en 401 et declencher la redirection globale (lib/api.ts).
    await page.evaluate(() => {
      const raw = localStorage.getItem("vector-auth");
      if (!raw) return;
      const parsed = JSON.parse(raw);
      parsed.state.token = parsed.state.token.slice(0, -5) + "xxxxx";
      localStorage.setItem("vector-auth", JSON.stringify(parsed));
    });
    await page.reload({ waitUntil: "domcontentloaded" });

    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });
});
