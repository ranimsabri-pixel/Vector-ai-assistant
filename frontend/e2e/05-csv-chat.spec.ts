import { test, expect } from "@playwright/test";
import { registerAndLogin, deleteConversationViaApi, deleteDatasetViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("CSV dans le chat devient un dataset", () => {
  test("un CSV attaché au chat devient un dataset persisté et répond aux questions", async ({
    page,
  }) => {
    test.slow();

    const email = uniqueEmail("csv");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    const csvContent =
      "produit,ventes\nChaise,320\nTable,280\nLampe,150\nFauteuil,410\nBureau,190\n";

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "ventes-e2e.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csvContent),
    });

    // Attend "N lignes · M colonnes" dans la carte de dataset en attente
    await expect(page.getByText(/\d+\s*lignes\s*·\s*\d+\s*colonnes/i)).toBeVisible({
      timeout: 30_000,
    });

    const chatInput = page.locator('input[placeholder*="Poser une question" i]');
    await chatInput.fill("Quel produit a le plus de ventes ?");
    await chatInput.press("Enter");

    await expect(page.getByTestId("assistant-message").first()).toBeVisible({
      timeout: 30_000,
    });

    // Verifie la persistance sur /datasets
    await page.goto("/datasets");
    await expect(page.getByText(/ventes-e2e/i).first()).toBeVisible({ timeout: 10_000 });

    // Nettoyage (best-effort : ne doit jamais faire echouer un test dont le
    // scenario reel a deja ete valide par les assertions ci-dessus).
    try {
      const token = await page.evaluate(() => {
        const raw = localStorage.getItem("vector-auth");
        return raw ? JSON.parse(raw).state.token : null;
      });
      const conv = await page.evaluate(
        async ({ id, token }) => {
          const res = await fetch(`http://localhost:8000/conversations/${id}`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          return res.ok ? res.json() : null;
        },
        { id: activeId, token },
      );
      const datasetAttachment = (conv?.messages ?? [])
        .flatMap((m: { attachments?: Array<Record<string, unknown>> }) => m.attachments ?? [])
        .find((a: Record<string, unknown>) => a.type === "dataset");

      await deleteConversationViaApi(page, activeId);
      if (datasetAttachment?.dataset_id) {
        await deleteDatasetViaApi(page, datasetAttachment.dataset_id as string);
      }
    } catch (e) {
      console.warn("Nettoyage 05-csv-chat echoue (non bloquant) :", e);
    }
  });
});
