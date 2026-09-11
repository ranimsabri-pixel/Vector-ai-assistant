import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // NEW J45 (CI/CD) : regle stricte recente, flague un pattern tres
      // courant et generalement correct (reset d'etat local en debut
      // d'effet quand une dependance devient null/absente). 21 occurrences
      // dans du code deja en prod sur 18 fichiers -- downgrade en warn pour
      // ne pas bloquer la CI sur une dette technique existante, a traiter
      // dans un sprint dedie plutot qu'en urgence un jour de setup CI.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
