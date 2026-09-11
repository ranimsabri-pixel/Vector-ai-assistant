"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError } from "@/lib/api";
import { changePassword, deleteAccount, updateProfile } from "@/lib/settings";
import { useAuthStore } from "@/lib/store/auth";
import { DeleteAccountModal } from "@/components/delete-account-modal";

function passwordStrengthError(password: string): string | null {
  if (password.length < 8) return "8 caractères minimum";
  if (!/[a-zA-Z]/.test(password)) return "Au moins une lettre";
  if (!/[0-9]/.test(password)) return "Au moins un chiffre";
  return null;
}

export function SettingsAccount() {
  const router = useRouter();
  const { token, user, setUser, logout } = useAuthStore();

  // --- Profil ---
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [nameSaving, setNameSaving] = useState(false);
  const [nameMessage, setNameMessage] = useState<string | null>(null);

  // --- Mot de passe ---
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);
  const [pwdSaving, setPwdSaving] = useState(false);

  // --- Suppression ---
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  if (!token || !user) return null;

  async function handleSaveName() {
    const trimmed = fullName.trim();
    if (!trimmed || trimmed === user!.full_name) return;
    setNameSaving(true);
    setNameMessage(null);
    try {
      const updated = await updateProfile(token!, trimmed);
      setUser(updated);
      setNameMessage("Nom mis à jour");
    } catch (err) {
      setNameMessage(err instanceof ApiError ? err.detail : "Erreur, réessaie.");
    } finally {
      setNameSaving(false);
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPwdError(null);
    setPwdSuccess(null);

    const strengthIssue = passwordStrengthError(newPassword);
    if (strengthIssue) {
      setPwdError(strengthIssue);
      return;
    }
    if (newPassword !== confirmPassword) {
      setPwdError("Les deux mots de passe ne correspondent pas");
      return;
    }

    setPwdSaving(true);
    try {
      await changePassword(token!, oldPassword, newPassword);
      setPwdSuccess("Mot de passe mis à jour");
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPwdError(
        err instanceof ApiError && err.status === 401
          ? "Mot de passe actuel incorrect"
          : "Erreur, réessaie."
      );
    } finally {
      setPwdSaving(false);
    }
  }

  async function handleDeleteAccount(password: string) {
    await deleteAccount(token!, password);
    // sessionStorage plutot qu'un query param "?deleted=1" : une requete
    // en arriere-plan encore en vol avec l'ancien token peut recevoir un
    // 401 juste apres la suppression et declencher le hard-redirect
    // generique de lib/api.ts (window.location.href = "/login", sans
    // query), qui gagnerait systematiquement la course contre ce
    // router.push. Le flag survit a n'importe lequel des deux chemins.
    sessionStorage.setItem("vector-account-deleted", "1");
    router.push("/login");
    logout();
  }

  return (
    <div className="space-y-10 max-w-lg">
      {/* Profil */}
      <section>
        <h2 className="text-sm font-semibold text-foreground mb-1">Profil</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Ton nom est visible par toi seul, il n&apos;apparaît nulle part publiquement.
        </p>
        <div className="space-y-3">
          <div>
            <label htmlFor="full-name" className="block text-xs mb-1 text-muted-foreground">
              Nom
            </label>
            <input
              id="full-name"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              onBlur={handleSaveName}
              maxLength={60}
              disabled={nameSaving}
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
            {nameMessage && (
              <p className="text-xs text-muted-foreground mt-1">{nameMessage}</p>
            )}
          </div>
          <div>
            <label htmlFor="email" className="block text-xs mb-1 text-muted-foreground">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={user.email}
              disabled
              className="w-full px-3 py-2 bg-muted border border-border rounded-lg text-sm text-muted-foreground cursor-not-allowed"
            />
          </div>
        </div>
      </section>

      {/* Mot de passe */}
      <section>
        <h2 className="text-sm font-semibold text-foreground mb-1">Mot de passe</h2>
        <p className="text-sm text-muted-foreground mb-4">
          8 caractères minimum, avec au moins une lettre et un chiffre.
        </p>
        <form onSubmit={handleChangePassword} className="space-y-3">
          <div>
            <label htmlFor="old-password" className="block text-xs mb-1 text-muted-foreground">
              Mot de passe actuel
            </label>
            <input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
          </div>
          <div>
            <label htmlFor="new-password" className="block text-xs mb-1 text-muted-foreground">
              Nouveau mot de passe
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              required
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
          </div>
          <div>
            <label htmlFor="confirm-password" className="block text-xs mb-1 text-muted-foreground">
              Confirmer le nouveau mot de passe
            </label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              required
              className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:border-emerald-500/60 transition-colors"
            />
          </div>

          {pwdError && <p className="text-sm text-red-400">{pwdError}</p>}
          {pwdSuccess && <p className="text-sm text-emerald-500">{pwdSuccess}</p>}

          <button
            type="submit"
            disabled={pwdSaving}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
          >
            {pwdSaving ? "Mise à jour..." : "Changer le mot de passe"}
          </button>
        </form>
      </section>

      {/* Zone de danger */}
      <section className="border border-red-900/40 bg-red-950/10 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-red-400 mb-1">Zone de danger</h2>
        <p className="text-sm text-muted-foreground mb-4">
          La suppression de ton compte est définitive et irréversible.
        </p>
        <button
          onClick={() => setDeleteModalOpen(true)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-red-400 border border-red-900/60 hover:bg-red-950/40 transition-colors"
        >
          Supprimer mon compte
        </button>
      </section>

      <DeleteAccountModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={handleDeleteAccount}
      />
    </div>
  );
}
