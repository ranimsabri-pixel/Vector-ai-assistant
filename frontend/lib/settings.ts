import { api } from "@/lib/api";
import type { User } from "@/lib/store/auth";

export async function updateProfile(
  token: string,
  full_name: string
): Promise<User> {
  return api<User>("/users/me", { method: "PATCH", token, body: { full_name } });
}

export async function changePassword(
  token: string,
  old_password: string,
  new_password: string
): Promise<void> {
  await api("/users/me/password", {
    method: "POST",
    token,
    body: { old_password, new_password },
  });
}

export async function deleteAccount(
  token: string,
  password: string
): Promise<void> {
  await api("/users/me", { method: "DELETE", token, body: { password } });
}
