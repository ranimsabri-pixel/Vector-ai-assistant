import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  hasHydrated: boolean;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
  setHasHydrated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      hasHydrated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
      setHasHydrated: (v) => set({ hasHydrated: v }),
    }),
    {
      name: "vector-auth",  // Clé localStorage
      // Le store persist se rehydrate de façon asynchrone après le premier
      // rendu. Sans ce flag, tout code qui redirige quand isAuthenticated
      // est false (ex: AppLayout) se déclenche AVANT que le token stocké
      // en localStorage ait pu être relu, et renvoie l'utilisateur au
      // login même s'il est bien connecté.
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);