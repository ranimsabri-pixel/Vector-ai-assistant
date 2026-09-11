import { test, expect } from "@playwright/test";
import { registerAndLogin, deleteConversationViaApi } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Création de dashboard depuis une action rapide", () => {
  test("uploader un dataset via l'action rapide génère un dashboard", async ({ page }) => {
    test.slow(); // upload + profilage + calcul KPI

    const email = uniqueEmail("dash");
    await registerAndLogin(page, email, "SecurePass123!");

    const activeId = await page.evaluate(() => {
      const raw = localStorage.getItem("vector-discussions");
      return raw ? JSON.parse(raw).state.activeId : null;
    });

    // La conversation est vierge (0 message) -> la grille d'actions rapides
    // est visible (elle disparait des qu'un message existe).
    await page.getByText("Dashboard KPI général").click();

    const csvContent =
      "produit,region,ventes,mois\n" +
      "A,Nord,320,2026-01\n" +
      "B,Sud,280,2026-01\n" +
      "A,Est,150,2026-02\n" +
      "B,Ouest,410,2026-02\n" +
      "A,Nord,190,2026-03\n";

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles({
      name: "dashboard-e2e.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csvContent),
    });
    await expect(page.getByText("dashboard-e2e.csv")).toBeVisible({ timeout: 5_000 });

    // .first() : le bouton "Envoyer" du formulaire d'action rapide (dans la
    // liste de messages) precede dans le DOM le bouton d'envoi du chat
    // (icone seule, mais accessible-name "Envoyer" via son attribut title —
    // les deux matchent getByRole sans .first()/.last()).
    await page.getByRole("button", { name: "Envoyer" }).first().click();

    // /agent/run-tool est deterministe (pas de LLM) mais l'upload+profilage
    // en amont prend un peu de temps.
    await expect(page.getByText(/dashboard.*généré/i).first()).toBeVisible({
      timeout: 30_000,
    });

    const openDashboardLink = page.getByRole("link", { name: /ouvrir le dashboard/i });
    await expect(openDashboardLink).toBeVisible({ timeout: 5_000 });

    const [dashboardPage] = await Promise.all([
      page.context().waitForEvent("page"),
      openDashboardLink.click(),
    ]);
    await dashboardPage.waitForLoadState("domcontentloaded");
    // S5 J55 : /dashboard/[id] -> /dashboard?id=... (export statique, cf
    // docs/DEPLOYMENT_RENDER.md decision F).
    expect(dashboardPage.url()).toMatch(/\/dashboard\?id=/);
    await dashboardPage.close();

    await deleteConversationViaApi(page, activeId);
  });
});
