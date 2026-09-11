import { test, expect } from "@playwright/test";
import { registerAndLogin } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

async function htmlThemeClass(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => document.documentElement.className);
}

test.describe("Apparence / thème (S5 J52)", () => {
  test("le toggle header cycle correctement light → dark → system", async ({ page }) => {
    const email = uniqueEmail("theme-cycle");
    await registerAndLogin(page, email, PASSWORD);

    const toggle = page.getByTestId("theme-toggle");
    await expect(toggle).toHaveAttribute("data-theme-current", "system");

    await toggle.click();
    await expect(toggle).toHaveAttribute("data-theme-current", "light");
    expect(await htmlThemeClass(page)).toContain("light");

    await toggle.click();
    await expect(toggle).toHaveAttribute("data-theme-current", "dark");
    expect(await htmlThemeClass(page)).toContain("dark");

    await toggle.click();
    await expect(toggle).toHaveAttribute("data-theme-current", "system");
  });

  test("le thème Light persiste après un reload", async ({ page }) => {
    const email = uniqueEmail("theme-persist");
    await registerAndLogin(page, email, PASSWORD);

    const toggle = page.getByTestId("theme-toggle");
    await toggle.click(); // system -> light
    await expect(toggle).toHaveAttribute("data-theme-current", "light");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("theme-toggle")).toHaveAttribute(
      "data-theme-current",
      "light",
      { timeout: 10_000 },
    );
    expect(await htmlThemeClass(page)).toContain("light");
  });

  test("/settings > Apparence reflète le thème courant et se synchronise avec le header", async ({
    page,
  }) => {
    const email = uniqueEmail("theme-settings");
    await registerAndLogin(page, email, PASSWORD);

    // Passe en dark via le header avant d'aller sur /settings.
    await page.getByTestId("theme-toggle").click(); // system -> light
    await page.getByTestId("theme-toggle").click(); // light -> dark
    await expect(page.getByTestId("theme-toggle")).toHaveAttribute(
      "data-theme-current",
      "dark",
    );

    await page.goto("/settings");
    const darkRadio = page.getByRole("radio", { name: "Sombre" });
    await expect(darkRadio).toHaveAttribute("aria-checked", "true", { timeout: 10_000 });

    // Changement via la radio Settings -> le toggle header suit.
    const lightRadio = page.getByRole("radio", { name: "Clair" });
    await lightRadio.click();
    await expect(lightRadio).toHaveAttribute("aria-checked", "true");

    await page.goto("/");
    await expect(page.getByTestId("theme-toggle")).toHaveAttribute(
      "data-theme-current",
      "light",
      { timeout: 5_000 },
    );
  });

  test("le contenu reste lisible dans les deux modes (fond et texte changent bien)", async ({
    page,
  }) => {
    const email = uniqueEmail("theme-readable");
    await registerAndLogin(page, email, PASSWORD);

    const toggle = page.getByTestId("theme-toggle");

    await toggle.click(); // -> light
    const lightBg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    const lightFg = await page.evaluate(() => getComputedStyle(document.body).color);

    await toggle.click(); // -> dark
    const darkBg = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    const darkFg = await page.evaluate(() => getComputedStyle(document.body).color);

    // Le fond ET le texte doivent effectivement changer entre les 2 modes
    // (sinon on aurait exactement le risque "fond noir sur fond noir").
    expect(lightBg).not.toBe(darkBg);
    expect(lightFg).not.toBe(darkFg);
    // Le fond clair ne doit pas etre (quasi) noir.
    expect(lightBg).not.toBe("rgb(0, 0, 0)");
  });
});
