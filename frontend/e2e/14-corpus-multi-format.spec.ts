import { test, expect } from "@playwright/test";
import path from "path";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

const PASSWORD = "SecurePass123!";

test.describe("Corpus multi-format (S5 J52)", () => {
  test("création d'un corpus vide apparaît en liste", async ({ page }) => {
    const email = uniqueEmail("corpus-empty");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/datasets");
    await page.getByRole("button", { name: "Corpus" }).click();
    await page.getByText("Créer un corpus").click();
    await page.getByPlaceholder("Ex: Rapports Deloitte 2026").fill("Corpus vide E2E J52");
    await page.getByRole("button", { name: "Enregistrer" }).click();

    await expect(page.getByText("Corpus vide E2E J52")).toBeVisible({ timeout: 10_000 });
  });

  test("upload PDF+DOCX par drag-and-drop, ingestion complète, puis question cross-format", async ({
    page,
  }) => {
    test.slow(); // 2 ingestions + reponse mockee

    const email = uniqueEmail("corpus-multi");
    await registerAndLogin(page, email, PASSWORD);

    const initialConvId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    await page.goto("/datasets");
    await page.getByRole("button", { name: "Corpus" }).click();
    await page.getByText("Créer un corpus").click();
    await page.getByPlaceholder("Ex: Rapports Deloitte 2026").fill("Corpus Cross-Format E2E");

    const dropzoneInput = page.getByTestId("corpus-dropzone").locator('input[type="file"]');
    await dropzoneInput.setInputFiles([
      path.resolve(__dirname, "fixtures/corpus-doc.pdf"),
      path.resolve(__dirname, "fixtures/corpus-doc.docx"),
    ]);

    await expect(page.getByText("corpus-doc.pdf")).toBeVisible();
    await expect(page.getByText("corpus-doc.docx")).toBeVisible();

    await page.getByRole("button", { name: "Enregistrer" }).click();

    // Vue recap : les 2 fichiers passent a "Pret" (polling d'ingestion).
    await expect(page.getByText(/2 document\(s\) créé\(s\)/i)).toBeVisible({
      timeout: 15_000,
    });
    const readyLabels = page.getByText("Prêt");
    await expect(readyLabels).toHaveCount(2, { timeout: 60_000 });

    await page.getByTestId("corpus-upload-recap-close").click();

    // Le corpus contient bien les 2 documents.
    await page.getByText("Corpus Cross-Format E2E").click();
    await expect(page.getByText(/2 document/i).first()).toBeVisible({ timeout: 10_000 });

    // Association a une nouvelle conversation + question cross-format.
    await page.getByRole("button", { name: /interroger ce corpus/i }).click();
    await page.waitForFunction(() => location.pathname === "/", { timeout: 10_000 });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Que dit IBM watsonx dans ces documents ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/📄 Sources \(/i).first()).toBeVisible({
      timeout: 10_000,
    });

    // Au moins une source PDF ("page N") et une source DOCX ("section N"
    // ou "bloc N") -- top_k par defaut couvre l'integralite des quelques
    // chunks des 2 fixtures, donc les 2 formats doivent apparaitre.
    await expect(page.getByText(/page \d+/i).first()).toBeVisible({ timeout: 5_000 });
    await expect(
      page.getByText(/section \d+|bloc \d+/i).first(),
    ).toBeVisible({ timeout: 5_000 });

    const corpusConvId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    if (corpusConvId) await deleteConversationViaApi(page, corpusConvId);
    if (initialConvId) await deleteConversationViaApi(page, initialConvId);
  });

  test("un fichier de format non supporté déposé dans la modale est signalé sans bloquer les autres", async ({
    page,
  }) => {
    const email = uniqueEmail("corpus-reject");
    await registerAndLogin(page, email, PASSWORD);

    await page.goto("/datasets");
    await page.getByRole("button", { name: "Corpus" }).click();
    await page.getByText("Créer un corpus").click();
    await page.getByPlaceholder("Ex: Rapports Deloitte 2026").fill("Corpus Fichier Invalide");

    const dropzoneInput = page.getByTestId("corpus-dropzone").locator('input[type="file"]');
    await dropzoneInput.setInputFiles([
      path.resolve(__dirname, "fixtures/corpus-doc.pdf"),
      path.resolve(__dirname, "fixtures/test-image.png"), // .png non accepte par le corpus
    ]);

    await expect(page.getByText("corpus-doc.pdf")).toBeVisible();
    await expect(page.getByText("test-image.png")).toBeVisible();
    // Le fichier rejete affiche une icone d'erreur (title) sans etre envoye.
    await expect(page.locator('[title="Format non supporté"]')).toBeVisible();
  });
});
