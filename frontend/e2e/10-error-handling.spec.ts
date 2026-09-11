import { test, expect } from "@playwright/test";
import fs from "fs";
import os from "os";
import path from "path";
import { registerAndLogin } from "./helpers/auth";
import { uniqueEmail } from "./fixtures/test-users";

test.describe("Gestion d'erreurs", () => {
  test("un fichier de données trop gros est rejeté instantanément côté client", async ({
    page,
  }) => {
    const email = uniqueEmail("bigfile");
    await registerAndLogin(page, email, "SecurePass123!");

    // 105 Mo > MAX_DATASET_FILE_SIZE (100 Mo) — rejet cote client, avant tout
    // upload reseau. Ecrit sur disque : setInputFiles refuse un buffer en
    // memoire au-dela de 50 Mo ("Cannot set buffer larger than 50Mb").
    const bigFilePath = path.join(os.tmpdir(), "trop-gros-e2e.csv");
    fs.writeFileSync(bigFilePath, Buffer.alloc(105 * 1024 * 1024, "a"));

    const fileInput = page.locator('input[type="file"]').first();
    await fileInput.setInputFiles(bigFilePath);

    await expect(page.getByText(/trop volumineux/i).first()).toBeVisible({
      timeout: 5_000,
    });

    fs.unlinkSync(bigFilePath);
  });

  test("une session invalidée en cours d'usage redirige vers /login", async ({ page }) => {
    const email = uniqueEmail("expired");
    await registerAndLogin(page, email, "SecurePass123!");

    await expect(
      page.locator('input[placeholder*="Poser une question" i]'),
    ).toBeVisible({ timeout: 10_000 });

    // Invalide le token en pleine session (simule une expiration serveur)
    await page.evaluate(() => {
      const raw = localStorage.getItem("vector-auth");
      if (!raw) return;
      const parsed = JSON.parse(raw);
      parsed.state.token = "expired_token_xyz";
      localStorage.setItem("vector-auth", JSON.stringify(parsed));
    });

    // Un reload declenche loadFromBackend(token) au mount (useEffect) : appel
    // API garanti avec le token invalide, contrairement a un clic dont l'effet
    // reseau exact n'est pas certain -> intercepteur global 401 (lib/api.ts)
    // doit rediriger vers /login.
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
  });

  test("un corpus vide ne peut pas être interrogé (bouton désactivé)", async ({ page }) => {
    const email = uniqueEmail("emptycorpus");
    await registerAndLogin(page, email, "SecurePass123!");

    await page.goto("/datasets");
    await page.getByRole("button", { name: "Corpus" }).click();
    await page.getByText("Créer un corpus").click();
    await page.getByPlaceholder("Ex: Rapports Deloitte 2026").fill("Corpus vide E2E");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Corpus cree")).toBeVisible({ timeout: 5_000 });

    const askButton = page.getByRole("button", { name: /interroger ce corpus/i });
    await expect(askButton).toBeDisabled();
  });
});
