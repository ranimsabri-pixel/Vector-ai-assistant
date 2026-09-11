"use client";

import { Download } from "lucide-react";

interface ExportButtonProps {
  /** Nom suggéré pour le fichier (sans extension) */
  filename: string;
}

export function ExportButton({ filename }: ExportButtonProps) {
  function handleExport() {
    // Met à jour le titre de la page → influence le nom suggéré du PDF
    const originalTitle = document.title;
    document.title = filename;

    // Ouvre le dialogue d'impression natif
    window.print();

    // Restaure le titre après l'impression
    setTimeout(() => {
      document.title = originalTitle;
    }, 500);
  }

  return (
    <button
      onClick={handleExport}
      className="px-3 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-lg text-xs font-medium text-white flex items-center gap-2 transition-colors shadow-lg shadow-emerald-900/30"
      title="Exporter le dashboard en PDF"
    >
      <Download size={13} />
      Exporter PDF
    </button>
  );
}