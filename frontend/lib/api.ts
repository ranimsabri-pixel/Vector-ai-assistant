/**
 * Helper centralisé pour les appels API au backend Vector.
 *
 * Gère automatiquement :
 * - Authentification (Bearer token)
 * - Sérialisation JSON par défaut (objet → JSON.stringify)
 * - Form data OAuth2 (isForm: true → URLSearchParams + content-type form)
 * - FormData/Blob/URLSearchParams passés tels quels (le navigateur gère)
 * - Décodage des erreurs Pydantic 422 en messages lisibles
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

type ApiBody =
  | BodyInit
  | Record<string, unknown>
  | unknown[]
  | null
  | undefined;

type ApiOptions = {
  method?: string;
  body?: ApiBody;
  token?: string;
  headers?: Record<string, string>;
  /**
   * Si true, le body (objet JS) est sérialisé en form data OAuth2
   * (application/x-www-form-urlencoded). Utiliser pour /auth/login.
   */
  isForm?: boolean;
};

export async function api<T>(
  path: string,
  options: ApiOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers || {}),
  };

  // 1. Auth
  if (options.token) {
    headers["Authorization"] = "Bearer " + options.token;
  }

  // 2. Sérialisation du body selon le type
  let fetchBody: BodyInit | null = null;

  if (options.body != null) {
    if (options.isForm) {
      // Cas spécial : OAuth2 form data
      // Body est un objet → on le transforme en URLSearchParams
      const params = new URLSearchParams();
      const bodyAsRecord = options.body as Record<string, unknown>;
      for (const [key, value] of Object.entries(bodyAsRecord)) {
        if (value != null) {
          params.append(key, String(value));
        }
      }
      fetchBody = params;
      // Pas besoin de mettre Content-Type, le navigateur ajoute auto :
      // application/x-www-form-urlencoded
    } else if (
      options.body instanceof FormData ||
      options.body instanceof URLSearchParams ||
      options.body instanceof Blob ||
      options.body instanceof ArrayBuffer ||
      typeof options.body === "string"
    ) {
      // Body déjà sous forme acceptée par fetch
      fetchBody = options.body as BodyInit;
      // Pour les strings (JSON déjà stringifié), on ajoute le Content-Type
      if (typeof options.body === "string" && !headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
    } else {
      // Body est un objet JS → on le sérialise en JSON
      fetchBody = JSON.stringify(options.body);
      if (!headers["Content-Type"]) {
        headers["Content-Type"] = "application/json";
      }
    }
  }

  // 3. Fetch
  const response = await fetch(API_BASE_URL + path, {
    method: options.method || "GET",
    headers,
    body: fetchBody,
  });

  // 4. Session expirée / token invalide : deconnexion propre + redirection.
  // On exclut /auth/login pour ne pas interferer avec un mauvais mot de
  // passe (401 legitime du flow de connexion, pas une session expiree).
  // On exclut aussi les pages publiques (/share/...) : un visiteur sans
  // compte qui consulte un lien partage ne doit jamais etre renvoye vers
  // /login, meme si un appel arriere-plan echoue en 401 par erreur.
  const onPublicPage =
    typeof window !== "undefined" && window.location.pathname.startsWith("/share");
  // Un 401 sur ces deux endpoints signifie "mauvais mot de passe saisi"
  // (verification explicite avant changement/suppression de compte), pas
  // une session expiree — ne pas deconnecter l'utilisateur pour ça.
  const isPasswordCheck =
    path === "/users/me/password" || (path === "/users/me" && options.method === "DELETE");
  if (
    response.status === 401 &&
    !path.startsWith("/auth/login") &&
    !isPasswordCheck &&
    !onPublicPage &&
    typeof window !== "undefined"
  ) {
    const { useAuthStore } = await import("@/lib/store/auth");
    useAuthStore.getState().logout();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  // 5. Gestion des erreurs avec parsing Pydantic
  if (!response.ok) {
    let detail = "Erreur HTTP " + response.status;
    try {
      const data = await response.json();
      if (data?.detail) {
        if (typeof data.detail === "string") {
          detail = data.detail;
        } else if (Array.isArray(data.detail)) {
          detail = data.detail
            .map(
              (err: {
                loc?: (string | number)[];
                msg?: string;
                type?: string;
              }) => {
                const field =
                  err.loc && err.loc.length > 1
                    ? err.loc.slice(1).join(".")
                    : "body";
                return field + " : " + (err.msg || "invalide");
              }
            )
            .join(" | ");
        } else {
          detail = JSON.stringify(data.detail);
        }
      } else if (data?.message) {
        detail = data.message;
      }
    } catch {
      // Body non-JSON, on garde le message par défaut
    }
    throw new ApiError(response.status, detail);
  }

  // 6. Réponse sans body (204 No Content)
  if (response.status === 204) {
    return undefined as T;
  }

  // 7. Parsing JSON
  return response.json();
}