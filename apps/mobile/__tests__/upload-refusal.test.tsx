/**
 * e2e round 3 R5 — a refused file is ONE readable line, and only that file leaves the queue.
 * The screen printed "Upload failed: upload failed: 422 {"detail": …}" and a corrupt PDF sank the
 * valid file queued beside it.
 */
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockUpload = jest.fn();
jest.mock('../lib/api-client', () => {
  const actual = jest.requireActual('../lib/api-client');
  return {
    ...actual,
    uploadDocuments: (...a: unknown[]) => mockUpload(...a),
    getSurfaceCopy: () => Promise.resolve({}),
    extractLineItems: jest.fn(),
    handoffIntake: jest.fn(),
  };
});
jest.mock('expo-router', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  useLocalSearchParams: () => ({}),
}));
jest.mock('../components/upload/CameraCapture', () => ({
  CameraCapture: () => null,
  isCaptureSupported: () => false,
}));

import { Platform } from 'react-native';

import { UploadError } from '../lib/api-client';
import UploadScreen from '../app/(app)/upload';

// The web surface (app.tyndaleapp.net — where the round-3 run happened): the picker is a hidden
// <input type="file">. jest can't run the native path (its picker is a dynamic import).
const realOS = Platform.OS;
beforeAll(() => {
  (Platform as { OS: string }).OS = 'web';
});
afterAll(() => {
  (Platform as { OS: string }).OS = realOS;
});

const pdf = (name: string, bytes: number) => new File([new Uint8Array(bytes)], name, { type: 'application/pdf' });
const pick = (r: ReturnType<typeof render>) =>
  r.UNSAFE_getByType('input' as never).props.onChange({ target: { files: [pdf('corrupt.pdf', 2048), pdf('bill.pdf', 4096)] } });

const REASON = '"corrupt.pdf" isn\'t a PDF or image, so I left it out. Add a PDF, or a clear photo of the page.';

describe('a refused upload', () => {
  it('shows one line for the bad file, keeps the good one queued, and lets it be sent', async () => {
    mockUpload.mockRejectedValueOnce(
      new UploadError(422, REASON, [{ index: 0, filename: 'corrupt.pdf', code: 'not_a_document', reason: REASON }]),
    );
    const r = render(<UploadScreen />);
    act(() => pick(r));
    await waitFor(() => expect(r.getByText('Submit 2 documents')).toBeTruthy());

    fireEvent.press(r.getByText('Submit 2 documents'));
    await waitFor(() => expect(r.getAllByTestId('upload-refused')).toHaveLength(1));
    const line = r.getByTestId('upload-refused').props.children as string;
    expect(line).toBe(REASON); // the server's own line — no status, no envelope, no "Upload failed:"
    expect(line).not.toMatch(/422|detail|\{/);
    expect(r.queryByText('corrupt.pdf')).toBeNull(); // the refused file left the queue
    expect(r.getByText('bill.pdf')).toBeTruthy(); // the good one stayed
    expect(r.getByText('Submit 1 document')).toBeTruthy(); // …and can be sent

    mockUpload.mockResolvedValueOnce({ case_file_id: 'cf', uploads: [], chat_first: true, conversation_id: 'c' });
    fireEvent.press(r.getByText('Submit 1 document'));
    await waitFor(() => expect(mockUpload).toHaveBeenCalledTimes(2));
    expect((mockUpload.mock.calls[1][0] as { name: string }[]).map((f) => f.name)).toEqual(['bill.pdf']);
  });

  it('a send that failed without a reason says so plainly, and keeps every file', async () => {
    mockUpload.mockRejectedValueOnce(new UploadError(502, null, []));
    const r = render(<UploadScreen />);
    act(() => pick(r));
    await waitFor(() => expect(r.getByText('Submit 2 documents')).toBeTruthy());
    fireEvent.press(r.getByText('Submit 2 documents'));
    await waitFor(() => expect(r.getByTestId('upload-error')).toBeTruthy());
    expect(r.getByTestId('upload-error').props.children).not.toMatch(/502|upload failed/i);
    expect(r.getByText('Submit 2 documents')).toBeTruthy();
  });
});
