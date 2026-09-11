"use client";

import Papa from "papaparse";
import * as XLSX from "xlsx";

// Note : le dtype reel du backend (voir profiler.py) est
// "numeric" | "categorical" | "datetime" | "text" | "boolean" -- PAS "date".
// On aligne le preview client sur ces memes valeurs pour rester coherent
// avec le profilage backend qui reste la source de verite.
export type ColumnDetectedType =
  | "numeric"
  | "categorical"
  | "datetime"
  | "boolean"
  | "text";

export type ColumnPreview = {
  name: string;
  detected_type: ColumnDetectedType;
  sample_values: string[]; // premieres 5 valeurs
};

export type FilePreview = {
  columns: ColumnPreview[];
  rows: string[][]; // 10 premieres lignes de donnees (hors header)
  total_rows_estimated: number;
};

export class FileTooLargeForPreviewError extends Error {
  constructor(public fileSizeBytes: number) {
    super("Fichier trop volumineux pour un aperçu (>20 Mo)");
    this.name = "FileTooLargeForPreviewError";
  }
}

const PREVIEW_ROW_COUNT = 10;
const MAX_PREVIEW_FILE_SIZE = 20 * 1024 * 1024; // 20 Mo

const BOOLEAN_VALUES = new Set([
  "true", "false", "0", "1", "yes", "no", "oui", "non",
]);

const DATE_LIKE_PATTERNS = [
  /^\d{4}-\d{1,2}-\d{1,2}/, // 2024-01-15
  /^\d{1,2}\/\d{1,2}\/\d{4}/, // 15/01/2024
  /^\d{1,2}-\d{1,2}-\d{4}/, // 15-01-2024
  /^\d{4}\/\d{1,2}\/\d{1,2}/, // 2024/01/15
];

function looksLikeDate(value: string): boolean {
  // Exige un separateur typique d'une date pour eviter les faux positifs
  // de Date.parse sur des mots ou codes quelconques.
  if (!/[-/]/.test(value)) return false;
  if (DATE_LIKE_PATTERNS.some((re) => re.test(value))) return true;
  return !Number.isNaN(Date.parse(value));
}

function detectColumnType(values: string[]): ColumnDetectedType {
  const nonEmpty = values.map((v) => v.trim()).filter((v) => v.length > 0);
  if (nonEmpty.length === 0) return "text";

  const lower = nonEmpty.map((v) => v.toLowerCase());

  if (lower.every((v) => BOOLEAN_VALUES.has(v))) {
    return "boolean";
  }

  if (nonEmpty.every((v) => !Number.isNaN(Number(v)))) {
    return "numeric";
  }

  if (nonEmpty.every(looksLikeDate)) {
    return "datetime";
  }

  const uniqueCount = new Set(lower).size;
  if (uniqueCount < 10) {
    return "categorical";
  }

  return "text";
}

function buildColumns(header: string[], rows: string[][]): ColumnPreview[] {
  return header.map((rawName, i) => {
    const colValues = rows.map((r) => (r[i] ?? "").toString());
    return {
      name: rawName?.toString().trim() || `Colonne ${i + 1}`,
      detected_type: detectColumnType(colValues),
      sample_values: colValues.slice(0, 5),
    };
  });
}

export async function previewCsvFile(file: File): Promise<FilePreview> {
  return new Promise((resolve, reject) => {
    Papa.parse<string[]>(file, {
      preview: PREVIEW_ROW_COUNT + 1,
      skipEmptyLines: true,
      complete: (results) => {
        const data = results.data;
        if (!data || data.length === 0) {
          reject(new Error("Fichier vide ou illisible"));
          return;
        }
        const [header, ...rows] = data;

        // Estimation grossiere du nombre total de lignes a partir du
        // ratio taille-fichier / taille-moyenne-d'une-ligne-echantillonnee
        // (on ne lit que l'echantillon preview, jamais le fichier entier).
        const headerBytes = new Blob([header.join(",")]).size;
        const sampleBytes = rows.reduce(
          (sum, r) => sum + new Blob([r.join(",")]).size + 1,
          0,
        );
        const avgRowBytes = rows.length > 0 ? sampleBytes / rows.length : 0;
        const dataBytes = Math.max(file.size - headerBytes, 0);
        const total_rows_estimated =
          avgRowBytes > 0 ? Math.round(dataBytes / avgRowBytes) : rows.length;

        resolve({
          columns: buildColumns(header, rows),
          rows,
          total_rows_estimated,
        });
      },
      error: (err) => reject(err),
    });
  });
}

export async function previewExcelFile(file: File): Promise<FilePreview> {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: "array" });
  const firstSheetName = workbook.SheetNames[0];
  if (!firstSheetName) {
    throw new Error("Le fichier Excel ne contient aucune feuille");
  }

  const sheet = workbook.Sheets[firstSheetName];
  const data = XLSX.utils.sheet_to_json<string[]>(sheet, {
    header: 1,
    blankrows: false,
    raw: false,
  });
  if (data.length === 0) {
    throw new Error("Feuille vide ou illisible");
  }

  const [rawHeader, ...allRows] = data;
  const header = rawHeader.map((h) => (h ?? "").toString());
  const rows = allRows
    .slice(0, PREVIEW_ROW_COUNT)
    .map((r) => header.map((_, i) => (r[i] ?? "").toString()));

  return {
    columns: buildColumns(header, rows),
    rows,
    total_rows_estimated: allRows.length,
  };
}

export async function previewFile(file: File): Promise<FilePreview> {
  if (file.size > MAX_PREVIEW_FILE_SIZE) {
    throw new FileTooLargeForPreviewError(file.size);
  }

  const ext = file.name.split(".").pop()?.toLowerCase();
  if (ext === "csv") {
    return previewCsvFile(file);
  }
  if (ext === "xlsx" || ext === "xls") {
    return previewExcelFile(file);
  }
  throw new Error(`Format de fichier non supporté pour l'aperçu : .${ext}`);
}
