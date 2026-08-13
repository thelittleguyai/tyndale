/**
 * Client-side upload allowlist (PDF + common images). The <input accept="…"> attribute is only a
 * hint the user can override (e.g. "All files"), so we enforce here too — and the server does the
 * authoritative magic-byte check. Keep this a SUBSET of the server allowlist
 * (runtime/app/routes/upload.py::_sniff_upload_type) so a file the client accepts never 422s.
 */

const ACCEPTED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'heif', 'tif', 'tiff', 'bmp'];
const ACCEPTED_MIME = new Set([
  'application/pdf',
  'image/jpeg',
  'image/jpg',
  'image/png',
  'image/heic',
  'image/heif',
  'image/tiff',
  'image/bmp',
]);

/** The `accept` attribute for the file <input> — narrows the native picker to our allowlist. */
export const UPLOAD_ACCEPT_ATTR =
  'application/pdf,image/jpeg,image/png,image/heic,image/heif,.pdf,.jpg,.jpeg,.png,.heic,.heif';

/** Plain-language reminder shown when a rejected file is picked. */
export const ACCEPTED_UPLOAD_HINT = 'Upload a PDF or an image (JPG, PNG, or HEIC).';

/** Mirrors the server's per-file cap (config.max_upload_file_bytes). Checked client-side so a
 *  capture that came out too big is caught before the user waits on an upload that 413s. */
export const MAX_UPLOAD_FILE_BYTES = 20 * 1024 * 1024;

export function isAcceptedUpload(file: { name?: string; type?: string }): boolean {
  const type = (file.type || '').toLowerCase();
  if (ACCEPTED_MIME.has(type)) return true;
  const ext = (file.name || '').toLowerCase().split('.').pop() ?? '';
  return ACCEPTED_EXTENSIONS.includes(ext);
}

/** Split a picked list into accepted files + the names we rejected (for a friendly message). */
export function partitionUploads<T extends { name?: string; type?: string }>(
  files: T[],
): { accepted: T[]; rejectedNames: string[] } {
  const accepted: T[] = [];
  const rejectedNames: string[] = [];
  for (const f of files) {
    if (isAcceptedUpload(f)) accepted.push(f);
    else rejectedNames.push(f.name || 'that file');
  }
  return { accepted, rejectedNames };
}
