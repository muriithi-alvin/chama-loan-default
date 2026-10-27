"use client";

// Photos are shrunk in the browser before upload (OFF-8, X9): longest side
// 2,400 px, JPEG quality 0.85. Drawing onto a canvas also drops the EXIF
// data (such as location); the server re-saves the photo without it as well.

export const MAX_BYTES = 20 * 1024 * 1024;
export const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const LONG_SIDE = 2400;

export function checkFile(file: File): string | null {
  if (!ACCEPTED.includes(file.type)) return "Choose a JPEG, PNG or WebP photo.";
  if (file.size > MAX_BYTES) return "The photo is larger than 20 MB. Take it again or choose a smaller one.";
  if (file.size === 0) return "The file is empty. Choose the photo again.";
  return null;
}

export async function shrink(file: File): Promise<Blob> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  const scale = Math.min(1, LONG_SIDE / Math.max(bitmap.width, bitmap.height));
  const width = Math.round(bitmap.width * scale);
  const height = Math.round(bitmap.height * scale);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("This browser cannot prepare the photo.");
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  return await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("The photo could not be prepared."))), "image/jpeg", 0.85),
  );
}
