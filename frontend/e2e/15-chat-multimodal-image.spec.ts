import { test, expect } from "@playwright/test";
import path from "path";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

test.describe("Chat multimodal — image (S5 J52)", () => {
  test("attacher une image, l'envoyer, obtenir une réponse, ouvrir/fermer le lightbox", async ({
    page,
  }) => {
    const email = uniqueEmail("img-flow");
    await registerAndLogin(page, email, PASSWORD);

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    // 1. Attachement via le bouton d'attachement (input file caché).
    const fileInput = page.locator('input[type="file"]').first();
    const imagePath = path.resolve(__dirname, "fixtures/test-image.png");
    await fileInput.setInputFiles(imagePath);

    // 2. Miniature visible avant envoi (apercu base64 en attente).
    const pendingPreview = page.locator('img[src^="data:image"]').first();
    await expect(pendingPreview).toBeVisible({ timeout: 15_000 });

    // 3. Envoi + reponse (mock vision).
    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Quelle est la couleur dominante de cette image ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("assistant-message").first()).toContainText(/bleue?/i, {
      timeout: 5_000,
    });

    // 4. Clic sur l'image dans le fil -> lightbox.
    const messageThumbnail = page.locator('img[src^="data:image"]').first();
    await messageThumbnail.click();
    const lightbox = page.getByTestId("image-lightbox");
    await expect(lightbox).toBeVisible({ timeout: 5_000 });

    // 5. Fermeture via Échap.
    await page.keyboard.press("Escape");
    await expect(lightbox).toHaveCount(0, { timeout: 5_000 });

    if (activeId) await deleteConversationViaApi(page, activeId);
  });

  test("une image minuscule (1x1) ne fait pas planter l'attachement ni l'aperçu", async ({
    page,
  }) => {
    const email = uniqueEmail("img-tiny");
    await registerAndLogin(page, email, PASSWORD);

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const fileInput = page.locator('input[type="file"]').first();
    // Reutilise le meme fixture (deja une image 1x1 minimale) pour verifier
    // qu'aucune erreur JS n'est levee sur un cas limite de taille.
    const imagePath = path.resolve(__dirname, "fixtures/test-image.png");

    const pageErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await fileInput.setInputFiles(imagePath);
    await expect(page.locator('img[src^="data:image"]').first()).toBeVisible({
      timeout: 15_000,
    });

    expect(pageErrors).toEqual([]);

    if (activeId) await deleteConversationViaApi(page, activeId);
  });
});
