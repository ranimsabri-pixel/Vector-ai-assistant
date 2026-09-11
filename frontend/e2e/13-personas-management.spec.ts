import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

test.describe("Gestion des personas (S5 J52)", () => {
  test("le persona système « Vector » est présent par défaut et non modifiable", async ({
    page,
  }) => {
    const email = uniqueEmail("persona-sys");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/personas");
    const systemCard = page.getByTestId("persona-card").filter({ hasText: "Vector" });
    await expect(systemCard).toBeVisible({ timeout: 10_000 });
    await expect(systemCard.getByText("Système")).toBeVisible();

    // Pas de boutons editer/supprimer sur la carte systeme.
    await expect(systemCard.getByTestId("persona-edit-button")).toHaveCount(0);
    await expect(systemCard.getByTestId("persona-delete-button")).toHaveCount(0);
  });

  test("création d'un persona custom avec tous les champs, apparaît en liste", async ({
    page,
  }) => {
    const email = uniqueEmail("persona-create");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/personas");
    await page.getByRole("button", { name: "Créer un persona" }).click();

    await page.getByPlaceholder("ex: Vector Finance").fill("Analyste E2E");
    await page.getByPlaceholder("À quoi sert ce persona ?").fill("Persona de test Playwright");
    await page
      .getByPlaceholder(/analyste financier/i)
      .fill("Tu es un analyste financier de test. Réponds toujours avec des chiffres.");
    await page.getByRole("button", { name: "Créer le persona" }).click();

    const card = page.getByTestId("persona-card").filter({ hasText: "Analyste E2E" });
    await expect(card).toBeVisible({ timeout: 10_000 });
  });

  test("édition du nom et du prompt système, persistée après reload", async ({ page }) => {
    const email = uniqueEmail("persona-edit");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/personas");
    await page.getByRole("button", { name: "Créer un persona" }).click();
    await page.getByPlaceholder("ex: Vector Finance").fill("Avant édition");
    await page
      .getByPlaceholder(/analyste financier/i)
      .fill("Prompt système initial pour ce persona de test.");
    await page.getByRole("button", { name: "Créer le persona" }).click();
    await expect(
      page.getByTestId("persona-card").filter({ hasText: "Avant édition" }),
    ).toBeVisible({ timeout: 10_000 });

    await page
      .getByTestId("persona-card")
      .filter({ hasText: "Avant édition" })
      .getByTestId("persona-edit-button")
      .click();
    const nameInput = page.getByPlaceholder("ex: Vector Finance");
    await nameInput.fill("");
    await nameInput.fill("Après édition");
    const promptInput = page.getByPlaceholder(/analyste financier/i);
    await promptInput.fill("");
    await promptInput.fill("Prompt système modifié pour ce persona de test.");
    await page.getByRole("button", { name: "Enregistrer" }).click();

    await expect(
      page.getByTestId("persona-card").filter({ hasText: "Après édition" }),
    ).toBeVisible({ timeout: 10_000 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(
      page.getByTestId("persona-card").filter({ hasText: "Après édition" }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Avant édition")).toHaveCount(0);
  });

  test("suppression d'un persona custom, disparaît après confirmation", async ({
    page,
  }) => {
    const email = uniqueEmail("persona-delete");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/personas");
    await page.getByRole("button", { name: "Créer un persona" }).click();
    await page.getByPlaceholder("ex: Vector Finance").fill("À supprimer");
    await page
      .getByPlaceholder(/analyste financier/i)
      .fill("Persona destiné à être supprimé dans ce test.");
    await page.getByRole("button", { name: "Créer le persona" }).click();

    const card = page.getByTestId("persona-card").filter({ hasText: "À supprimer" });
    await expect(card).toBeVisible({ timeout: 10_000 });

    await card.getByTestId("persona-delete-button").click();
    await page.getByTestId("confirm-dialog-confirm").click();

    await expect(card).toHaveCount(0, { timeout: 5_000 });
  });

  test("sélection dans le chat affiche le badge, verrouillé après le premier message", async ({
    page,
  }) => {
    const email = uniqueEmail("persona-chat");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/personas");
    await page.getByRole("button", { name: "Créer un persona" }).click();
    await page.getByPlaceholder("ex: Vector Finance").fill("Persona Chat E2E");
    await page
      .getByPlaceholder(/analyste financier/i)
      .fill("Persona utilisé pour vérifier le verrouillage après premier message.");
    await page.getByRole("button", { name: "Créer le persona" }).click();
    await expect(
      page.getByTestId("persona-card").filter({ hasText: "Persona Chat E2E" }),
    ).toBeVisible({ timeout: 10_000 });

    await page.goto("/");
    const badge = page.getByTestId("persona-selector-badge");
    await expect(badge).toBeVisible({ timeout: 10_000 });
    await expect(badge).toHaveAttribute("data-locked", "false");

    await badge.click();
    await page.getByTestId("persona-option").filter({ hasText: "Persona Chat E2E" }).click();
    await expect(badge).toContainText("Persona Chat E2E");

    // Premier message -> verrouillage (mock LLM, reponse deterministe).
    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Bonjour");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 15_000,
    });
    await expect(badge).toHaveAttribute("data-locked", "true", { timeout: 5_000 });
  });
});
