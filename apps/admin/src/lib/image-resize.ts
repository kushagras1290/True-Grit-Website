/**
 * Client-side "resize to the placement's canonical canvas" step, run right
 * before a file reaches `api.uploadImage`.
 *
 * The upload target (R2, via `POST /v1/admin/media/images`) stores whatever
 * bytes it is given -- there is no Cloudflare Images transform binding wired
 * up, so without this an editor's raw phone photo or oddly-cropped export
 * would go out exactly as uploaded, on a page that always renders it at a
 * fixed aspect ratio (see `IMAGE_SPECIFICATIONS` / the Image Size Guide).
 * This crops+scales to that exact canvas client-side (a "cover" fit, the
 * same behaviour the storefront's own `object-cover` CSS produces) so what
 * an editor previews here is what customers see, regardless of the source
 * photo's original size or aspect ratio.
 *
 * Resizing is best-effort: any failure (a file the browser's decoder can't
 * read, no canvas support) falls back to uploading the original file rather
 * than blocking the editor's upload entirely.
 */

import type { ImageSpecification } from "./image-specifications";

const OUTPUT_QUALITY = 0.88;

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Could not decode the selected file as an image."));
    };
    image.src = url;
  });
}

function canvasToFile(canvas: HTMLCanvasElement, fileName: string): Promise<File> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("Canvas produced no image data."));
          return;
        }
        const withoutExtension = fileName.replace(/\.[^./\\]+$/, "");
        resolve(new File([blob], `${withoutExtension}.webp`, { type: "image/webp" }));
      },
      "image/webp",
      OUTPUT_QUALITY,
    );
  });
}

/** Resizes `file` to exactly `spec.width` x `spec.height`, cropping any
 *  excess from the centre (a "cover" fit) so the subject stays framed the
 *  same way `safeArea` describes. Falls back to the original file on any
 *  decode/canvas failure. */
export async function resizeImageToSpec(
  file: File,
  spec: Pick<ImageSpecification, "width" | "height">,
): Promise<File> {
  try {
    const image = await loadImage(file);
    const canvas = document.createElement("canvas");
    canvas.width = spec.width;
    canvas.height = spec.height;
    const context = canvas.getContext("2d");
    if (!context) return file;

    const scale = Math.max(spec.width / image.naturalWidth, spec.height / image.naturalHeight);
    const drawWidth = image.naturalWidth * scale;
    const drawHeight = image.naturalHeight * scale;
    const offsetX = (spec.width - drawWidth) / 2;
    const offsetY = (spec.height - drawHeight) / 2;

    context.drawImage(image, offsetX, offsetY, drawWidth, drawHeight);
    return await canvasToFile(canvas, file.name);
  } catch {
    return file;
  }
}
