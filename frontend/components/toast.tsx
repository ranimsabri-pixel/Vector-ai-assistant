"use client";

import { useEffect } from "react";
import { CheckCircle2, X, AlertCircle, Info } from "lucide-react";

export type ToastVariant = "success" | "error" | "info";

export interface ToastData {
  id: string;
  variant: ToastVariant;
  message: string;
}

interface ToastProps {
  toast: ToastData;
  onClose: (id: string) => void;
}

const VARIANT_CONFIG = {
  success: {
    icon: CheckCircle2,
    color: "bg-emerald-500/10 border-emerald-500/30 text-emerald-300",
    iconColor: "text-emerald-400",
  },
  error: {
    icon: AlertCircle,
    color: "bg-red-500/10 border-red-500/30 text-red-300",
    iconColor: "text-red-400",
  },
  info: {
    icon: Info,
    color: "bg-blue-500/10 border-blue-500/30 text-blue-300",
    iconColor: "text-blue-400",
  },
};

export function Toast({ toast, onClose }: ToastProps) {
  const config = VARIANT_CONFIG[toast.variant];
  const Icon = config.icon;

  useEffect(() => {
    const timer = setTimeout(() => onClose(toast.id), 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onClose]);

  return (
    <div
      className={
        "flex items-start gap-3 p-3 pr-2 border rounded-lg backdrop-blur-sm shadow-lg min-w-[300px] max-w-md animate-in slide-in-from-right duration-200 " +
        config.color
      }
    >
      <Icon size={18} className={config.iconColor + " flex-shrink-0 mt-0.5"} />
      <p className="flex-1 text-sm">{toast.message}</p>
      <button
        onClick={() => onClose(toast.id)}
        className="p-1 hover:bg-white/5 rounded transition-colors flex-shrink-0"
        aria-label="Fermer"
      >
        <X size={14} />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: ToastData[];
  onClose: (id: string) => void;
}

export function ToastContainer({ toasts, onClose }: ToastContainerProps) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-20 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      <div className="pointer-events-auto flex flex-col gap-2">
        {toasts.map((t) => (
          <Toast key={t.id} toast={t} onClose={onClose} />
        ))}
      </div>
    </div>
  );
}