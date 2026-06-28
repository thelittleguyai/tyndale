import { getProfileState, patchProfile, uploadInsuranceCard } from '../lib/api-client';
import { formatPhone, isoToMdy, validateDob } from '../lib/profile-ui';

describe('validateDob (18+ gate, DL-17)', () => {
  const y = new Date().getFullYear();

  it('rejects an under-18 DOB', () => {
    const r = validateDob(`06/15/${y - 10}`);
    expect(r.iso).toBeNull();
    expect(r.error).toMatch(/18/);
  });

  it('rejects a future DOB', () => {
    const r = validateDob(`06/15/${y + 1}`);
    expect(r.iso).toBeNull();
    expect(r.error).toMatch(/future/i);
  });

  it('rejects a malformed date', () => {
    expect(validateDob('1990-04-15').iso).toBeNull(); // ISO, not MM/DD/YYYY
    expect(validateDob('13/40/2000').error).toBeTruthy();
    expect(validateDob('nope').error).toBeTruthy();
  });

  it('accepts a valid adult DOB -> ISO', () => {
    const r = validateDob(`04/15/${y - 30}`);
    expect(r.error).toBeNull();
    expect(r.iso).toBe(`${y - 30}-04-15`);
  });

  it('treats empty as untouched (no value, no error)', () => {
    expect(validateDob('')).toEqual({ iso: null, error: null });
  });
});

describe('formatPhone + isoToMdy', () => {
  it('formats a phone progressively', () => {
    expect(formatPhone('5551234567')).toBe('(555) 123-4567');
    expect(formatPhone('555')).toBe('555');
    expect(formatPhone('abc555def12')).toBe('(555) 12');
  });

  it('converts an ISO date to MM/DD/YYYY', () => {
    expect(isoToMdy('1990-04-15')).toBe('04/15/1990');
    expect(isoToMdy(null)).toBe('');
  });
});

describe('profile / insurance api-client endpoints', () => {
  let fetchMock: jest.Mock;
  beforeEach(() => {
    fetchMock = jest
      .fn()
      .mockResolvedValue({ ok: true, json: async () => ({}), text: async () => '' });
    (global as unknown as { fetch: jest.Mock }).fetch = fetchMock;
  });

  it('uploadInsuranceCard POSTs base64 to the card endpoint with credentials', async () => {
    await uploadInsuranceCard('front', 'QkFTRTY0', 'image/png', 42);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/v1/insurance/card/upload');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('include');
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({
      card_type: 'front',
      image_base64: 'QkFTRTY0',
      mime_type: 'image/png',
    });
  });

  it('patchProfile PATCHes /v1/profile', async () => {
    await patchProfile({ first_name: 'Jane', accept_terms: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/v1\/profile$/);
    expect(init.method).toBe('PATCH');
    expect(init.credentials).toBe('include');
  });

  it('getProfileState GETs /v1/profile/state', async () => {
    await getProfileState();
    expect(fetchMock.mock.calls[0][0]).toContain('/v1/profile/state');
  });
});
