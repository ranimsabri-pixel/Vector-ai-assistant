import { test, expect } from "@playwright/test";
import path from "path";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Upload PDF + RAG", () => {
  test("upload un PDF et poser une question dessus fait remonter des sources", async ({
    page,
  }) => {
    test.slow(); // parsing + chunking + embeddings reels + reponse LLM

    const email = uniqueEmail("pdf");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const fileInput = page.locator('input[type="file"]').first();
    const pdfPath = path.resolve(__dirname, "fixtures/mini.pdf");
    await fileInput.setInputFiles(pdfPath);

    // Attend la fin de l'ingestion (parsing -> chunking -> embedding -> ready).
    // "pages indexées" est specifique a l'accuse de reception PDF -- un texte
    // generique comme "prêt" matcherait aussi l'indicateur de statut idle du
    // chat, present en permanence des le chargement de la page.
    await expect(page.getByText(/pages indexées/i).first()).toBeVisible({
      timeout: 60_000,
    });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Que contient ce document ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/📄 Sources \(/i).first()).toBeVisible({
      timeout: 10_000,
    });

    await deleteConversationViaApi(page, activeId);
  });
});
