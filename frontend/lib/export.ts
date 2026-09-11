"use client";

import html2canvas from "html2canvas-pro";
import { jsPDF } from "jspdf";

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function captureCanvas(el: HTMLElement): Promise<HTMLCanvasElement> {
  // Lit --background en live (theme courant) plutot qu'une valeur figee,
  // pour que l'export PNG/PDF corresponde a ce que l'utilisateur voit.
  const bg = getComputedStyle(document.documentElement)
    .getPropertyValue("--background")
    .trim() || "#09090b";
  return html2canvas(el, {
    backgroundColor: bg,
    scale: 2,
    useCORS: true,
  });
}

export async function exportElementAsPng(
  el: HTMLElement,
  filename: string
): Promise<void> {
  const canvas = await captureCanvas(el);
  const blob: Blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b);
      else reject(new Error("Échec de la génération du PNG"));
    }, "image/png");
  });
  downloadBlob(blob, filename);
}

export async function copyElementAsPngToClipboard(el: HTMLElement): Promise<void> {
  const canvas = await captureCanvas(el);
  const blob: Blob = await new Promise((resolve, reject) => {
    canvas.toBlob((b) => {
      if (b) resolve(b);
      else reject(new Error("Échec de la génération du PNG"));
    }, "image/png");
  });
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}

export async function copyTextToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export async function exportElementAsPdf(
  el: HTMLElement,
  filename: string
): Promise<void> {
  const canvas = await captureCanvas(el);
  const imgData = canvas.toDataURL("image/png");

  // Oriente le PDF selon la forme de la capture, une page pleine largeur.
  const orientation = canvas.width >= canvas.height ? "landscape" : "portrait";
  const pdf = new jsPDF({ orientation, unit: "px", format: [canvas.width, canvas.height] });
  pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
  pdf.save(filename);
}
