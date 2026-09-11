import { defineConfig } from "@playwright/test";
import baseConfig from "./playwright.config";

/**
 * Config "bucket mocke" (S5 J54) : ne selectionne que les specs 12-18
 * (S5 J52), 100% deterministes, sans appel LLM externe. Utilisee par
 * `pnpm test:e2e:mocked` pour un dev local rapide/offline.
 *
 * Filtre par nom de fichier (regex sur testMatch), pas par expansion
 * shell -- portable Windows/Linux/CI, et une future spec 19-*.spec.ts
 * mockee serait automatiquement incluse sans toucher ce fichier.
 */
export default defineConfig(baseConfig, {
  testMatch: /(^|[\\/])1[2-8]-.+\.spec\.ts$/,
});
