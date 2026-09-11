import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Nouvelle conversation à la connexion", () => {
  test("une nouvelle discussion vierge est créée automatiquement", async ({ page }) => {
    const email = uniqueEmail("newconv");
    await registerAndLogin(page, email, "SecurePass123!");

    await expect(page.getByTestId("discussion-row").first()).toContainText(
      "Nouvelle discussion",
      { timeout: 15_000 },
    );

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await expect(chatInput).toBeVisible();
    await expect(chatInput).toBeEnabled();
  });

  test("un refresh (F5) ne recrée PAS de nouvelle conversation", async ({ page }) => {
    const email = uniqueEmail("refresh");
    await registerAndLogin(page, email, "SecurePass123!");

    await expect(page.getByTestId("discussion-row").first()).toBeVisible({
      timeout: 15_000,
    });
    const activeIdBefore = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    const countBefore = await page.getByTestId("discussion-row").count();

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const activeIdAfter = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    const countAfter = await page.getByTestId("discussion-row").count();

    expect(activeIdAfter).toBe(activeIdBefore);
    expect(countAfter).toBe(countBefore);
  });
});
