"use client";

import { api } from "./api";

// ============================================================
// Types
// ============================================================

export type ImageAttachmentPayload = {
  type: "image";
  attachment_id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  width: number;
  height: number;
  storage_path: string;
  preview_base64: string;
};

export const ALLOWED_IMAGE_MIME = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
];
export const MAX_IMAGE_FILE_SIZE = 10 * 1024 * 1024; // 10 Mo, doit rester
// synchronise avec MAX_IMAGE_SIZE dans backend/app/services/image_attachments.py
const RESIZE_MAX_SIDE = 2048;

// ============================================================
// Redimensionnement client-side (Canvas) si l'image depasse 2048px
// ============================================================

export async function resizeImageIfNeeded(file: File): Promise<File> {
  const dims = await new Promise<{ width: number; height: number }>(
    (resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ width: img.width, height: img.height });
      img.onerror = () => reject(new Error("Image illisible"));
      img.src = URL.createObjectURL(file);
    },
  );

  if (dims.width <= RESIZE_MAX_SIDE && dims.height <= RESIZE_MAX_SIDE) {
    return file;
  }

  const scale = RESIZE_MAX_SIDE / Math.max(dims.width, dims.height);
  const targetWidth = Math.round(dims.width * scale);
  const targetHeight = Math.round(dims.height * scale);

  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return file; // fallback : pas de resize possible, on envoie l'original

  ctx.drawImage(bitmap, 0, 0, targetWidth, targetHeight);

  // GIF anime perdrait son animation au resize -> on ne resize jamais les GIF
  const outputType = file.type === "image/gif" ? file.type : "image/jpeg";
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, outputType, 0.9),
  );
  if (!blob) return file;

  const ext = outputType === "image/jpeg" ? "jpg" : "gif";
  const newName = file.name.replace(/\.[^.]+$/, "") + `_resized.${ext}`;
  return new File([blob], newName, { type: outputType });
}

// ============================================================
// Upload
// ============================================================

export async function uploadImageAttachment(
  token: string,
  conversationId: string,
  file: File,
): Promise<ImageAttachmentPayload> {
  const formData = new FormData();
  formData.append("file", file);

  return api<ImageAttachmentPayload>(
    `/conversations/${conversationId}/attach-image`,
    { method: "POST", token, body: formData },
  );
}
