import { test, expect } from "@playwright/test";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Recherche web via Tavily", () => {
  test("le toggle Web active la recherche et affiche des sources web", async ({ page }) => {
    test.slow(); // recherche Tavily + reponse LLM en streaming reel

    const email = uniqueEmail("web");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const webToggle = page.locator('button[aria-pressed]', { hasText: "Web" });
    await webToggle.click();
    await expect(page.getByText(/recherche web activée/i)).toBeVisible({
      timeout: 3_000,
    });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Quelle est la capitale du Japon ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/🌐 Sources web \(/i).first()).toBeVisible({
      timeout: 15_000,
    });

    await deleteConversationViaApi(page, activeId);
  });
});
