"use client";

import { useState, useCallback } from "react";

type ConfirmOptions = {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning";
};

type ConfirmState = ConfirmOptions & {
  open: boolean;
  onConfirm: () => void;
};

/**
 * Hook pour gérer un ConfirmDialog impératif.
 * Usage :
 *   const { confirm, dialogProps } = useConfirm();
 *   ...
 *   const ok = await confirm({ title: "...", description: "..." });
 *   if (ok) { ... }
 *   ...
 *   return <ConfirmDialog {...dialogProps} />;
 */
export function useConfirm() {
  const [state, setState] = useState<ConfirmState>({
    open: false,
    title: "",
    description: "",
    onConfirm: () => {},
  });

  const confirm = useCallback(
    (options: ConfirmOptions): Promise<boolean> => {
      return new Promise((resolve) => {
        setState({
          open: true,
          ...options,
          onConfirm: () => {
            resolve(true);
            setState((s) => ({ ...s, open: false }));
          },
        });
      });
    },
    [],
  );

  const dialogProps = {
    open: state.open,
    onClose: () => {
      setState((s) => ({ ...s, open: false }));
    },
    onConfirm: state.onConfirm,
    title: state.title,
    description: state.description,
    confirmLabel: state.confirmLabel,
    cancelLabel: state.cancelLabel,
    variant: state.variant,
  };

  return { confirm, dialogProps };
}