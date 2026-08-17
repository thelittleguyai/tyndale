/** One captured page as the upload path accepts it: a real File on web (getUserMedia →
 *  canvas → blob), a {uri, name, mimeType} part on native (expo-camera). `uploadDocuments`
 *  already sends both shapes, so a photographed bill travels the identical path either way. */
export type CapturedUpload = File | { uri: string; name: string; mimeType: string };

export function isFilePart(part: CapturedUpload): part is File {
  return typeof File !== 'undefined' && part instanceof File;
}
