import { useState } from "react";
import PipelineStepper from "./PipelineStepper.jsx";
import { importSymbol, uploadDocument, uploadJsonDocument } from "../api.js";

// Same 8 tickers as TARGET_SYMBOLS in data_pipeline/src/scrapers/direct_vn_collector.py
// (the only symbols with a pre-scraped data/normalized/{SYMBOL}.json on disk).
const AVAILABLE_SYMBOLS = ["FPT", "VNM", "HPG", "VCB", "MWG", "VIC", "TCB", "SSI"];

export default function UploadPanel({ onProcessed }) {
  const [file, setFile] = useState(null);
  const [symbol, setSymbol] = useState(AVAILABLE_SYMBOLS[0]);
  const [status, setStatus] = useState(null); // 'uploading' | 'processing' | 'ready' | null
  const [error, setError] = useState(null);
  const [document, setDocument] = useState(null);

  async function runIngest(uploadPromise) {
    setError(null);
    setDocument(null);
    setStatus("uploading");
    try {
      // uploading -> processing happens server-side within the same request;
      // we flip to "processing" right after the browser finishes sending the
      // file so the stepper reflects what's actually happening.
      setTimeout(() => setStatus((s) => (s === "uploading" ? "processing" : s)), 300);
      const doc = await uploadPromise;
      setStatus("ready");
      setDocument(doc);
      onProcessed(doc);
    } catch (err) {
      setError(err.message);
      setStatus(null);
    }
  }

  function handleProcess() {
    if (!file) return;
    const isJson = file.name.endsWith(".json") || file.type === "application/json";
    runIngest(isJson ? uploadJsonDocument(file) : uploadDocument(file));
  }

  function handleImportSymbol() {
    runIngest(importSymbol(symbol));
  }

  return (
    <div className="bg-white border border-border rounded-2xl p-4.5 mb-4">
      <h2 className="text-sm font-semibold mb-2.5">1. Upload a PDF or JSON document</h2>
      <div className="flex gap-2.5 flex-wrap items-center">
        <input
          type="file"
          accept="application/pdf,application/json,.json"
          className="text-[13px]"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <button
          disabled={!file || status === "uploading" || status === "processing"}
          onClick={handleProcess}
          className="bg-brand hover:bg-brand-dark disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-[13.5px] font-semibold"
        >
          Process document
        </button>
      </div>

      <div className="flex gap-2.5 flex-wrap items-center mt-3 pt-3 border-t border-border">
        <span className="text-[12.5px] text-muted">Or import a pre-scraped ticker:</span>
        <select
          className="px-2.5 py-2 border border-border rounded-lg text-[13px] bg-white"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
        >
          {AVAILABLE_SYMBOLS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button
          disabled={status === "uploading" || status === "processing"}
          onClick={handleImportSymbol}
          className="bg-brand hover:bg-brand-dark disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-[13.5px] font-semibold"
        >
          Import {symbol}
        </button>
      </div>

      {status && <PipelineStepper status={status} />}

      <div className="text-[12.5px] text-muted mt-2 flex items-center gap-1.5 min-h-[16px]">
        {(status === "uploading" || status === "processing") && <span className="spinner" />}
        {status === "uploading" && <span>Sending file to backend...</span>}
        {status === "processing" && <span>Extracting, chunking and embedding on the server...</span>}
        {status === "ready" && document && (
          <span>Done. Indexed {document.chunk_count} chunks from {document.page_count} pages.</span>
        )}
        {error && <span className="text-red-600">Error: {error}</span>}
      </div>

      {document && (
        <div className="flex gap-2.5 flex-wrap mt-3">
          <Stat value={document.page_count} label="Pages" />
          <Stat value={document.chunk_count} label="Chunks" />
          <Stat value={document.vocab_size} label="Vocabulary" />
          <Stat value={document.total_tokens} label="Total tokens" />
        </div>
      )}

      <div className="text-[11.5px] text-muted mt-2.5 leading-relaxed">
        The file (or the imported ticker's normalized JSON) is sent to the FinMind backend, split into
        ~130-word overlapping chunks, embedded with BAAI/bge-m3 and stored in PostgreSQL/pgvector (ADR01,
        ADR04) - unlike the original browser-only demo, the corpus now persists across page reloads.
      </div>
    </div>
  );
}

function Stat({ value, label }) {
  return (
    <div className="bg-brand-light rounded-[10px] px-3.5 py-2 text-xs text-brand-dark">
      <b className="text-[15px] block">{value}</b>
      {label}
    </div>
  );
}
