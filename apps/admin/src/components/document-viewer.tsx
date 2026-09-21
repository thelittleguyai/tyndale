'use client';

import { useEffect, useState } from 'react';

import {
  adminReviewDocumentFile,
  adminReviewDocumentText,
  reviewDocumentKey,
  type ReviewDocumentCard,
} from '@/lib/api-client';
import { Sheet, humanize } from './review-ui';

// The reviewer's ground truth (doc 39 §2): the uploaded file itself, with a toggle to the OCR
// text the audit actually read. Each open is audited server-side (review_document_view). The
// bytes live only in an object URL for as long as the sheet is open — nothing is cached.

type View = 'file' | 'text';
type Loaded = { url: string; contentType: string };

export function DocumentViewer({
  caseId,
  doc,
  page,
  onClose,
}: {
  caseId: string;
  doc: ReviewDocumentCard;
  page?: number | null;
  onClose: () => void;
}) {
  const key = reviewDocumentKey(doc);
  const [view, setView] = useState<View>('file');
  const [file, setFile] = useState<Loaded | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [textError, setTextError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    let url: string | null = null;
    setFile(null);
    setFileError(null);
    adminReviewDocumentFile(caseId, key, ctl.signal)
      .then(({ blob, contentType }) => {
        url = URL.createObjectURL(blob);
        setFile({ url, contentType });
      })
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setFileError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      ctl.abort();
      if (url) URL.revokeObjectURL(url); // the bytes do not outlive the sheet
    };
  }, [caseId, key, attempt]);

  useEffect(() => {
    if (view !== 'text' || text !== null) return;
    const ctl = new AbortController();
    setTextError(null);
    adminReviewDocumentText(caseId, key, ctl.signal)
      .then((r) => setText(r.text))
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setTextError(e instanceof Error ? e.message : String(e));
      });
    return () => ctl.abort();
  }, [caseId, key, view, text, attempt]);

  const retry = () => {
    setText(null);
    setAttempt((n) => n + 1);
  };
  const tab = (v: View, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={view === v}
      onClick={() => setView(v)}
      className={`min-h-[44px] rounded-lg px-3 text-xs font-semibold ${
        view === v ? 'bg-white/15 text-white' : 'border border-white/15 text-white/60 hover:bg-white/5'
      }`}
    >
      {label}
    </button>
  );
  const retryBtn = (
    <button type="button" onClick={retry} className="mt-3 min-h-[44px] rounded-lg border border-white/15 px-3 text-xs text-white/80 hover:bg-white/5">
      Retry
    </button>
  );
  const isImage = file?.contentType.startsWith('image/') && !/heic|heif|tiff/.test(file.contentType);
  const isPdf = file?.contentType === 'application/pdf';

  return (
    <Sheet
      wide
      title={`${humanize(doc.document_type ?? doc.kind)} · ${doc.filename ?? 'unnamed'}`}
      subtitle={[
        doc.page_count ? `${doc.page_count} pages` : null,
        doc.has_text ? `${doc.text_chars.toLocaleString()} chars extracted` : 'no text extracted',
        doc.extraction_status ? humanize(doc.extraction_status) : null,
        page ? `cited page ${page}` : null,
      ]
        .filter(Boolean)
        .join(' · ')}
      onClose={onClose}
    >
      <div role="tablist" aria-label="Document view" className="mb-3 flex gap-2">
        {tab('file', 'Document')}
        {tab('text', 'OCR text')}
      </div>

      {view === 'file' ? (
        fileError ? (
          <div role="alert" className="text-sm text-rose-soft">
            {fileError}
            <div>{retryBtn}</div>
          </div>
        ) : !file ? (
          <p className="text-sm text-white/40">Loading the document…</p>
        ) : isImage ? (
          // eslint-disable-next-line @next/next/no-img-element -- an object URL of an authenticated PHI blob; next/image can neither fetch nor optimize it
          <img src={file.url} alt={`Uploaded ${humanize(doc.document_type ?? 'document')}`} className="max-w-full rounded-lg bg-white" />
        ) : isPdf ? (
          <iframe
            title={`Uploaded ${humanize(doc.document_type ?? 'document')}`}
            src={page ? `${file.url}#page=${page}` : file.url}
            className="h-[75vh] w-full rounded-lg bg-white"
          />
        ) : (
          <div className="rounded-lg border border-dashed border-white/15 p-4 text-sm text-white/60">
            This browser can’t display <span className="font-mono">{file.contentType}</span> (an iPhone HEIC photo, or a TIFF). The OCR text
            tab shows what the audit read from it.
          </div>
        )
      ) : textError ? (
        <div role="alert" className="text-sm text-rose-soft">
          {textError}
          <div>{retryBtn}</div>
        </div>
      ) : text === null ? (
        <p className="text-sm text-white/40">Loading the OCR text…</p>
      ) : text ? (
        <pre className="whitespace-pre-wrap rounded-lg bg-white/5 p-3 font-mono text-[12px] leading-5 text-white/80">{text}</pre>
      ) : (
        <p className="text-sm text-white/40">No text was extracted from this document.</p>
      )}
    </Sheet>
  );
}
