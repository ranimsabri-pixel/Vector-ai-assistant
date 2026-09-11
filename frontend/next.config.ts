import type { NextConfig } from "next";

// S5 J55 — export statique pour le déploiement Render (RAM: aucun process
// Node persistant en prod, Nginx sert les fichiers directement).
// trailingSlash volontairement PAS activé : ça introduirait des redirects
// 308 ("/login" -> "/login/") absents en dev, un écart de comportement
// avec ce que Playwright teste. Next émet donc des fichiers plats
// (login.html) -- Nginx les sert via `try_files $uri $uri.html $uri/
// =404`, pas de changement d'URL. images.unoptimized est requis : l'API
// d'optimisation d'image Next n'existe pas en export statique. Les 4
// anciennes routes dynamiques ([id]/[token]) ont été restructurées en
// routes à paramètre de requête (?id=/?token=) — voir
// docs/DEPLOYMENT_RENDER.md décision F.
const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
