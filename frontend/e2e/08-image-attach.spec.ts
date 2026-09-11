import { test, expect } from "@playwright/test";
import path from "path";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Upload image + vision GPT-4o", () => {
  test("une image jointe est décrite correctement par Vector", async ({ page }) => {
    test.slow(); // upload + reponse LLM vision reelle

    const email = uniqueEmail("img");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const fileInput = page.locator('input[type="file"]').first();
    const imagePath = path.resolve(__dirname, "fixtures/test-image.png");
    await fileInput.setInputFiles(imagePath);

    // Attend la miniature en attente d'envoi (apercu base64)
    await expect(page.locator('img[src^="data:image"]').first()).toBeVisible({
      timeout: 15_000,
    });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Quelle est la couleur dominante de cette image ? Réponds en un mot.");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("assistant-message").first()).toContainText(/bleu/i, {
      timeout: 15_000,
    });

    await deleteConversationViaApi(page, activeId);
  });
});
