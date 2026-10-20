// Photos go up as JPEG or PNG of at most 8 MB, the limits the server checks.
import { problemText } from './problem';
import type { Problem } from './problem';

const MAX_BYTES = 8 * 1024 * 1024;
const MAX_SIDE = 2560;
const UNREADABLE = 'This photo cannot be read. Take it again with the camera.';

function toJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error(UNREADABLE))), 'image/jpeg', quality);
  });
}

export async function preparePhoto(file: File): Promise<{ photo: File; reencoded: boolean }> {
  if ((file.type === 'image/jpeg' || file.type === 'image/png') && file.size <= MAX_BYTES) return { photo: file, reencoded: false };
  // shortcut: re-encoding drops the place and time stored in the photo; the form fields from the phone fill them, and the server records which source it used.
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error(UNREADABLE);
  }
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  let blob = await toJpeg(canvas, 0.85);
  if (blob.size > MAX_BYTES) blob = await toJpeg(canvas, 0.7);
  return { photo: new File([blob], 'photo.jpg', { type: 'image/jpeg' }), reencoded: true };
}

// problemText, except that a photo the browser cannot read says so.
export function photoProblem(error: unknown): Problem {
  return error instanceof Error && error.message === UNREADABLE ? { title: 'Could not send', text: UNREADABLE } : problemText(error);
}
