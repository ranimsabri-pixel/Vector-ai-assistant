import { test, expect } from "@playwright/test";
import { registerAndLogin, loginExisting } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

test.describe("Settings > Compte — profil et mot de passe (S5 J52)", () => {
  test("modification du nom valide, persistée après reload", async ({ page }) => {
    const email = uniqueEmail("acct-name");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Compte" }).click();

    const nameInput = page.locator("#full-name");
    await nameInput.fill("");
    await nameInput.fill("Nom E2E Modifié");
    await nameInput.blur();
    await expect(page.getByText("Nom mis à jour")).toBeVisible({ timeout: 10_000 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Compte" }).click();
    await expect(page.locator("#full-name")).toHaveValue("Nom E2E Modifié", {
      timeout: 10_000,
    });
  });

  test("le champ nom bloque la saisie au-delà de 60 caractères", async ({ page }) => {
    const email = uniqueEmail("acct-name-long");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Compte" }).click();

    const nameInput = page.locator("#full-name");
    await nameInput.fill("x".repeat(70));
    await expect(nameInput).toHaveValue("x".repeat(60));
  });

  test("changement de mot de passe valide, reconnexion possible avec le nouveau", async ({
    page,
  }) => {
    const email = uniqueEmail("acct-pwd-ok");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Compte" }).click();

    await page.locator("#old-password").fill(PASSWORD);
    await page.locator("#new-password").fill("NouveauMotDePasse1");
    await page.locator("#confirm-password").fill("NouveauMotDePasse1");
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();

    await expect(page.getByText("Mot de passe mis à jour")).toBeVisible({
      timeout: 10_000,
    });

    // Reconnexion avec le nouveau mot de passe.
    await page.goto("/login");
    await loginExisting(page, email, "NouveauMotDePasse1");
    await expect(page).toHaveURL("/");
  });

  test("changement avec l'ancien mot de passe incorrect affiche un message générique", async ({
    page,
  }) => {
    const email = uniqueEmail("acct-pwd-wrong");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Compte" }).click();

    await page.locator("#old-password").fill("MauvaisMotDePasse1");
    await page.locator("#new-password").fill("NouveauMotDePasse1");
    await page.locator("#confirm-password").fill("NouveauMotDePasse1");
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();

    await expect(page.getByText(/mot de passe actuel incorrect/i)).toBeVisible({
      timeout: 10_000,
    });
  });

  test("un nouveau mot de passe trop faible est refusé avec un message clair", async ({
    page,
  }) => {
    const email = uniqueEmail("acct-pwd-weak");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Compte" }).click();

    await page.locator("#old-password").fill(PASSWORD);
    await page.locator("#new-password").fill("aucunchiffre");
    await page.locator("#confirm-password").fill("aucunchiffre");
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();

    await expect(page.getByText("Au moins un chiffre")).toBeVisible({ timeout: 5_000 });
  });
});
