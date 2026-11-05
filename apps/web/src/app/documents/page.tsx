'use client';

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { apiErrorMessage, MAX_UPLOAD_BYTES, type Document } from '@careerfit/shared';
import { getApi } from '@/lib/api';
import { AnalysisPanel } from './AnalysisPanel';

const POLL_INTERVAL_MS = 2000;

const buttonClass = 'rounded border border-zinc-400 px-3 py-2 font-medium disabled:opacity-50';
const inputClass = 'rounded border border-zinc-400 bg-transparent p-2';

const STATUS_LABELS: Record<Document['status'], string> = {
  pending: 'Waiting to be read…',
  parsing: 'Reading…',
  ready: 'Ready',
  failed: 'Failed',
};

const EXTRACTION_LABELS: Record<'pending' | 'running' | 'failed', string> = {
  pending: 'Waiting to be analysed…',
  running: 'Analysing…',
  failed: 'Analysis failed',
};

const TYPE_LABELS: Record<Document['type'], string> = {
  resume: 'Resume',
  cover_letter: 'Cover letter',
  portfolio_link: 'Portfolio link',
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [docType, setDocType] = useState<'resume' | 'cover_letter'>('resume');
  const [progress, setProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [link, setLink] = useState('');
  const [linkError, setLinkError] = useState<string | null>(null);
  const [linkBusy, setLinkBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await getApi().documents.list());
      setLoadError(null);
    } catch {
      setLoadError('Could not load your documents.');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loads data from the API on mount
    void refresh();
  }, [refresh]);

  const processing = documents?.some(
    (d) =>
      d.status === 'pending' ||
      d.status === 'parsing' ||
      d.extractionStatus === 'pending' ||
      d.extractionStatus === 'running',
  );

  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [processing, refresh]);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setUploadError(null);
    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadError('This file is larger than the 10 MB limit.');
    } else {
      const form = new FormData();
      form.append('type', docType);
      form.append('file', file);
      setProgress(0);
      try {
        await getApi().documents.upload(form, setProgress);
        await refresh();
      } catch (error) {
        setUploadError(apiErrorMessage(error, 'The upload failed. Please try again.'));
      }
      setProgress(null);
    }
    if (fileInput.current) fileInput.current.value = '';
  }

  async function handleLink(event: FormEvent) {
    event.preventDefault();
    setLinkError(null);
    setLinkBusy(true);
    try {
      await getApi().documents.addPortfolioLink({ url: link });
      setLink('');
      await refresh();
    } catch (error) {
      setLinkError(apiErrorMessage(error, 'Could not add this link. Please try again.'));
    }
    setLinkBusy(false);
  }

  async function handleDelete(document: Document) {
    const label = document.fileName ?? document.url ?? 'this item';
    const scores = document.type === 'resume' ? ' and any scores made from it' : '';
    if (!window.confirm(`Delete ${label}${scores}?`)) return;
    try {
      await getApi().documents.delete(document.id);
      await refresh();
    } catch (error) {
      setLoadError(apiErrorMessage(error, 'Could not delete this. Please try again.'));
    }
  }

  const uploading = progress !== null;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 p-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">Your documents</h1>
        <div className="flex gap-4">
          <Link className="underline" href="/analysis">
            Score my resume
          </Link>
          <Link className="underline" href="/account">
            Account
          </Link>
        </div>
      </div>

      <section className="flex flex-col gap-3" aria-labelledby="upload-heading">
        <h2 id="upload-heading" className="text-lg font-medium">
          Upload a file
        </h2>
        <p className="text-sm text-zinc-500">PDF or DOCX, up to 10 MB.</p>
        <label className="flex flex-col gap-1">
          Document type
          <select
            className={inputClass}
            value={docType}
            disabled={uploading}
            onChange={(e) => setDocType(e.target.value as 'resume' | 'cover_letter')}
          >
            <option value="resume">Resume</option>
            <option value="cover_letter">Cover letter</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          File
          <input
            ref={fileInput}
            className={inputClass}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            disabled={uploading}
            onChange={(e) => void handleFile(e.target.files?.[0])}
          />
        </label>
        {uploading && (
          <label className="flex flex-col gap-1">
            {progress < 1
              ? `Uploading… ${Math.round(progress * 100)}%`
              : 'Uploaded. Reading your file, which can take a minute…'}
            <progress className="w-full" value={progress} max={1} />
          </label>
        )}
        {uploadError && (
          <p role="alert" className="text-red-600">
            {uploadError}
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="link-heading">
        <h2 id="link-heading" className="text-lg font-medium">
          Add a portfolio link
        </h2>
        <p className="text-sm text-zinc-500">
          GitHub, Behance or your own site. LinkedIn is saved as a link only and is not read.
        </p>
        <form onSubmit={handleLink} className="flex flex-col gap-2 sm:flex-row">
          <label className="flex grow flex-col gap-1">
            <span className="sr-only">Portfolio address</span>
            <input
              className={inputClass}
              type="url"
              required
              placeholder="https://"
              value={link}
              onChange={(e) => setLink(e.target.value)}
            />
          </label>
          <button className={buttonClass} type="submit" disabled={linkBusy}>
            Add link
          </button>
        </form>
        {linkError && (
          <p role="alert" className="text-red-600">
            {linkError}
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="list-heading">
        <h2 id="list-heading" className="text-lg font-medium">
          Added so far
        </h2>
        {loadError && (
          <p role="alert" className="text-red-600">
            {loadError}
          </p>
        )}
        {documents === null && !loadError && <p role="status">Loading…</p>}
        {documents?.length === 0 && <p>Nothing here yet. Upload your resume to get started.</p>}
        <ul className="flex flex-col gap-2">
          {documents?.map((document) => (
            <li
              key={document.id}
              data-testid="document-row"
              className="flex items-start justify-between gap-4 rounded border border-zinc-400 p-3"
            >
              <div className="flex min-w-0 flex-col gap-1">
                <span className="font-medium break-words">
                  {document.fileName ?? document.url}
                </span>
                <span className="text-sm text-zinc-500">{TYPE_LABELS[document.type]}</span>
                <span role="status" className="text-sm">
                  {STATUS_LABELS[document.status]}
                </span>
                {document.errorMessage && (
                  <span className="text-sm text-red-600">{document.errorMessage}</span>
                )}
                {document.extractionStatus && document.extractionStatus !== 'ready' && (
                  <span className="text-sm">{EXTRACTION_LABELS[document.extractionStatus]}</span>
                )}
                {document.extractionErrorMessage && (
                  <span className="text-sm text-red-600">{document.extractionErrorMessage}</span>
                )}
                {document.extractionStatus === 'ready' && (
                  <details>
                    <summary className="cursor-pointer text-sm font-medium underline">
                      See what we found
                    </summary>
                    <div className="pt-2">
                      <AnalysisPanel documentId={document.id} />
                    </div>
                  </details>
                )}
              </div>
              <button
                className={buttonClass}
                aria-label={`Delete ${document.fileName ?? document.url}`}
                onClick={() => void handleDelete(document)}
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
