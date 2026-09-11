import { test, expect } from "@playwright/test";
import path from "path";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Corpus multi-documents", () => {
  test("créer un corpus avec un document puis l'interroger renvoie des sources", async ({
    page,
  }) => {
    test.slow(); // ingestion PDF reelle + reponse LLM

    const email = uniqueEmail("corpus");
    await registerAndLogin(page, email, "SecurePass123!");

    const initialConvId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    // 1. Upload un PDF via le chat pour avoir un document "ready".
    // corpus-doc.pdf (pas mini.pdf) : le retrieval multi-doc (contrairement
    // au RAG mono-document) filtre les chunks < MIN_CHUNK_TOKENS (30 tokens)
    // — mini.pdf ne contient que 2 phrases tres courtes par page, filtrees
    // integralement, ce qui faisait echouer ce test avec 0 source retournee.
    const fileInput = page.locator('input[type="file"]').first();
    const pdfPath = path.resolve(__dirname, "fixtures/corpus-doc.pdf");
    await fileInput.setInputFiles(pdfPath);
    await expect(page.getByText(/pages indexées/i).first()).toBeVisible({
      timeout: 60_000,
    });

    // 2. Va sur /datasets, onglet Corpus, cree un corpus avec ce document
    await page.goto("/datasets");
    await page.getByRole("button", { name: "Corpus" }).click();
    await page.getByText("Créer un corpus").click();

    await page.getByPlaceholder("Ex: Rapports Deloitte 2026").fill("Corpus E2E");
    await page.getByRole("button", { name: /corpus-doc/i }).click();
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Corpus cree")).toBeVisible({ timeout: 5_000 });

    // 3. Interroge ce corpus
    await page.getByRole("button", { name: /interroger ce corpus/i }).click();
    await page.waitForFunction(() => location.pathname === "/", { timeout: 10_000 });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Que contiennent ces documents ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/📄 Sources \(/i).first()).toBeVisible({
      timeout: 10_000,
    });

    // Nettoyage (best-effort)
    const corpusConvId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });
    if (corpusConvId) await deleteConversationViaApi(page, corpusConvId);
    if (initialConvId) await deleteConversationViaApi(page, initialConvId);
  });
});
