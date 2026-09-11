import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

async function openDeleteModal(page: import("@playwright/test").Page) {
  await page.goto("/settings");
  await page.getByRole("button", { name: "Compte" }).click();
  await page.getByRole("button", { name: "Supprimer mon compte" }).click();
  await expect(page.getByText("Supprimer définitivement mon compte")).toBeVisible({
    timeout: 5_000,
  });
}

test.describe("Settings > Compte — suppression définitive (S5 J52)", () => {
  test("le bouton de confirmation reste désactivé tant que password + SUPPRIMER ne sont pas conformes", async ({
    page,
  }) => {
    const email = uniqueEmail("del-disabled");
    await registerAndLogin(page, email, PASSWORD);
    await openDeleteModal(page);

    const confirmBtn = page.getByTestId("delete-account-confirm");
    await expect(confirmBtn).toBeDisabled();

    // Password rempli, mais "supprimer" en minuscules -> toujours désactivé.
    await page.locator("#delete-password").fill(PASSWORD);
    await page.locator("#delete-confirm").fill("supprimer");
    await expect(confirmBtn).toBeDisabled();

    // "SUPPRIMER" correct, mais password vide -> toujours désactivé.
    await page.locator("#delete-password").fill("");
    await page.locator("#delete-confirm").fill("SUPPRIMER");
    await expect(confirmBtn).toBeDisabled();

    // Les deux corrects -> actif.
    await page.locator("#delete-password").fill(PASSWORD);
    await expect(confirmBtn).toBeEnabled();
  });

  test("un mauvais mot de passe renvoie 401 et laisse la modale ouverte", async ({
    page,
  }) => {
    const email = uniqueEmail("del-wrongpwd");
    await registerAndLogin(page, email, PASSWORD);
    await openDeleteModal(page);

    await page.locator("#delete-password").fill("MauvaisMotDePasse1");
    await page.locator("#delete-confirm").fill("SUPPRIMER");
    await page.getByTestId("delete-account-confirm").click();

    await expect(page.getByText("Mot de passe incorrect")).toBeVisible({ timeout: 10_000 });
    // La modale est toujours ouverte (le titre reste visible).
    await expect(page.getByText("Supprimer définitivement mon compte")).toBeVisible();

    // Le compte existe toujours : re-login possible.
    await page.goto("/login");
    await page.fill("#email", email);
    await page.fill("#password", PASSWORD);
    await page.click('button:has-text("Se connecter")');
    await expect(page).toHaveURL("/");
  });

  test("suppression effective : peuplement, confirmation, redirection, ancien login impossible", async ({
    page,
  }) => {
    test.slow();

    const email = uniqueEmail("del-full");
    await registerAndLogin(page, email, PASSWORD);

    // Peuple le compte avant suppression (dataset + persona) pour verifier
    // que le flux de suppression fonctionne meme avec des ressources
    // liees -- la verification exhaustive du cascade DB (toutes les
    // tables) est deja couverte cote pytest (S5 J50, test_delete_me_*).
    const token = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-auth");
      return raw ? JSON.parse(raw).state.token : null;
    });
    await page.request.post("http://localhost:8000/personas", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        name: "Persona à supprimer",
        system_prompt: "Persona de test pour verifier la suppression de compte.",
        icon: "Bot",
        color: "#3B82F6",
      },
    });
    await page.request.post("http://localhost:8000/datasets/upload", {
      headers: { Authorization: `Bearer ${token}` },
      multipart: {
        file: {
          name: "dataset-a-supprimer.csv",
          mimeType: "text/csv",
          buffer: Buffer.from("name,value\nA,1\nB,2\n"),
        },
        name: "Dataset à supprimer",
      },
    });

    await openDeleteModal(page);
    await page.locator("#delete-password").fill(PASSWORD);
    await page.locator("#delete-confirm").fill("SUPPRIMER");
    await page.getByTestId("delete-account-confirm").click();

    // Redirection vers /login avec confirmation (le message vient d'un
    // flag sessionStorage, plus fiable qu'un query param -- cf commentaire
    // dans settings-account.tsx sur la course avec le hard-redirect 401).
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
    // getByTestId (S5 J54) plutot que getByText(regex) : prevention
    // proactive du meme piege de collision trouve sur signup/login (cf
    // 12-auth-flow.spec.ts).
    await expect(page.getByTestId("account-deleted-message")).toBeVisible({
      timeout: 5_000,
    });

    // Le compte n'existe plus : re-login avec l'ancien email echoue.
    await page.fill("#email", email);
    await page.fill("#password", PASSWORD);
    await page.click('button:has-text("Se connecter")');
    await expect(page.getByTestId("login-error-message")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("login-error-message")).toContainText(
      /email ou mot de passe incorrect/i,
    );
    await expect(page).toHaveURL(/\/login/);
  });
});
