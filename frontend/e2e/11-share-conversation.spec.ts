import { test, expect } from "@playwright/test";
import { registerAndLogin, postMessageViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Partage public d'une conversation", () => {
  test("partager, consulter en anonyme, puis révoquer", async ({ page, browser }) => {
    const email = uniqueEmail("share");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    expect(activeId).toBeTruthy();

    // Peuple la conversation sans dependre d'un vrai appel LLM.
    await postMessageViaApi(page, activeId, "user", "Quelle est la capitale de la France ?");
    await postMessageViaApi(page, activeId, "assistant", "La capitale de la France est Paris.");
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);

    // Ouvre la modal de partage et recupere le lien.
    await page.getByRole("button", { name: "Partager" }).click();
    const linkInput = page.locator('input[readonly]');
    await expect(linkInput).toBeVisible({ timeout: 10_000 });
    const shareUrl = await linkInput.inputValue();
    // S5 J55 : /share/[token] -> /share?token=... (export statique, cf
    // docs/DEPLOYMENT_RENDER.md decision F).
    expect(shareUrl).toMatch(/\/share\?token=.+/);

    // Consultation en contexte totalement anonyme (nouveau contexte
    // navigateur = pas de cookies/localStorage partages, equivalent incognito).
    const anonContext = await browser.newContext();
    const sharePage = await anonContext.newPage();
    await sharePage.goto(shareUrl);

    await expect(sharePage.getByText(/a été partagée par/i)).toBeVisible({ timeout: 10_000 });
    await expect(sharePage.getByText("Quelle est la capitale de la France ?")).toBeVisible();
    await expect(sharePage.getByText("La capitale de la France est Paris.")).toBeVisible();
    await expect(sharePage.getByRole("link", { name: /créer un compte/i })).toBeVisible();

    // Lecture seule : aucun bouton d'action de chat (regenerer/feedback/input).
    await expect(sharePage.locator('input[placeholder*="Poser une question" i]')).toHaveCount(0);

    // Revocation depuis le compte authentifie (modal encore ouverte).
    await page.getByRole("button", { name: /révoquer le partage/i }).click();
    await expect(page.getByText(/partage révoqué/i)).toBeVisible({ timeout: 5_000 });

    // Le lien devient immediatement invalide.
    await sharePage.reload();
    await expect(sharePage.getByText(/n'est plus valide/i)).toBeVisible({ timeout: 10_000 });

    await anonContext.close();
  });

  test("images : masquées par défaut, visibles une fois la case cochée", async ({
    page,
    browser,
  }) => {
    const email = uniqueEmail("shareimg");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    expect(activeId).toBeTruthy();

    // Attachment construit a la main (meme shape que image_attachments.py) —
    // pas d'upload reel ni d'appel vision LLM necessaire pour ce scenario.
    const fakePreview =
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
    await postMessageViaApi(page, activeId, "assistant", "Voici le graphique demandé", [
      {
        type: "image",
        attachment_id: "test-attachment",
        file_name: "graphique-secret.png",
        mime_type: "image/png",
        file_size: 100,
        width: 1,
        height: 1,
        storage_path: "attachments/fake-user/fake-conv/fake.png",
        preview_base64: fakePreview,
      },
    ]);
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);

    await page.getByRole("button", { name: "Partager" }).click();
    const linkInput = page.locator('input[readonly]');
    await expect(linkInput).toBeVisible({ timeout: 10_000 });
    const shareUrl = await linkInput.inputValue();

    const checkbox = page.locator('input[type="checkbox"]');
    await expect(checkbox).not.toBeChecked();

    const anonContext = await browser.newContext();
    const sharePage = await anonContext.newPage();
    await sharePage.goto(shareUrl);

    await expect(sharePage.getByText(/a été partagée par/i)).toBeVisible({ timeout: 10_000 });
    await expect(sharePage.getByText(/image non partagée/i)).toBeVisible();
    await expect(sharePage.locator('img[src^="data:image"]')).toHaveCount(0);
    // Le nom de fichier ne doit JAMAIS apparaître, ni caché ni visible.
    await expect(sharePage.getByText("graphique-secret.png")).toHaveCount(0);

    // Coche la case -> le même lien (même token) expose désormais l'image.
    await checkbox.check();
    await expect(checkbox).toBeChecked();
    await page.waitForTimeout(500);

    await sharePage.reload();
    await expect(sharePage.locator('img[src^="data:image"]')).toBeVisible({ timeout: 10_000 });
    await expect(sharePage.getByText(/image non partagée/i)).toHaveCount(0);

    await page.getByRole("button", { name: /révoquer le partage/i }).click();
    await anonContext.close();
  });
});
