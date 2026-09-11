"use client";

import { useEffect } from "react";

type Shortcut = {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  meta?: boolean;
  callback: () => void;
  preventDefault?: boolean;
};

/**
 * Hook générique pour enregistrer des raccourcis clavier globaux.
 * Ignoré si l'utilisateur tape dans un input/textarea.
 */
export function useKeyboardShortcuts(shortcuts: Shortcut[]) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      // Ne pas capturer si l'utilisateur tape dans un champ
      const target = e.target as HTMLElement;
      const isTyping =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      for (const shortcut of shortcuts) {
        const keyMatch = e.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl ? e.ctrlKey || e.metaKey : true;
        const shiftMatch = shortcut.shift ? e.shiftKey : !e.shiftKey;
        const metaMatch = shortcut.meta ? e.metaKey : true;

        if (keyMatch && ctrlMatch && shiftMatch && metaMatch) {
          // Si le raccourci ne nécessite PAS de modifier et qu'on tape → skip
          if (isTyping && !shortcut.ctrl && !shortcut.meta) continue;

          if (shortcut.preventDefault !== false) {
            e.preventDefault();
          }
          shortcut.callback();
          return;
        }
      }
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [shortcuts]);
}