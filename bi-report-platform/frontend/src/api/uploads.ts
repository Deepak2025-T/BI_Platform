import { api } from "./client";

export interface UploadedFile {
  /** Where to point an <img> at. Relative, so it works wherever the app is served from. */
  url: string;
  name: string;
  content_type: string;
  size_bytes: number;
}

/**
 * Pictures for reports: a logo, or an image tile.
 *
 * Anyone with the address can open an uploaded picture — a browser can't send a token with an
 * <img> tag — so the address is a long random name instead. Don't upload anything confidential.
 */
export const uploadsApi = {
  image: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return api.post<UploadedFile>("/api/uploads", body, { timeout: 120000 }).then((r) => r.data);
  },
};

/** What the picker accepts, matching what the server stores. */
export const IMAGE_TYPES = "image/png,image/jpeg,image/webp,image/gif,image/svg+xml";
export const MAX_IMAGE_MB = 4;
