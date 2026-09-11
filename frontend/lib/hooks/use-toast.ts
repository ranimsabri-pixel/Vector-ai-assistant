"use client";

import { useState, useCallback } from "react";
import { type ToastData, type ToastVariant } from "@/components/toast";

export function useToast() {
  const [toasts, setToasts] = useState<ToastData[]>([]);

  const showToast = useCallback((variant: ToastVariant, message: string) => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { id, variant, message }]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return {
    toasts,
    showToast,
    success: (msg: string) => showToast("success", msg),
    error: (msg: string) => showToast("error", msg),
    info: (msg: string) => showToast("info", msg),
    removeToast,
  };
}