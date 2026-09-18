import { useEffect, useState } from "react";
import { getChunkDetails } from "../api.js";

export default function ChunkDetailPanel({ documentId }) {
  const [chunks, setChunks] = useState([]);
  const [openIndex, setOpenIndex] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getChunkDetails(documentId)
      .then((data) => !cancelled && setChunks(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  return (
    <div className="bg-white border border-border rounded-2xl p-4.5 mb-4">
      <h2 className="text-sm font-semibold mb-2.5">3. Chunk detail &amp; keywords</h2>
      <div className="text-[11.5px] text-muted leading-relaxed mb-2">
        Each chunk is now stored as a BAAI/bge-m3 dense vector (used for search above). The keyword weights and
        token trace below are TF-IDF, kept only as a human-readable explanation of which words distinguish each
        chunk - they are not what ranks search results anymore (see backend/src/text_analysis.py).
      </div>
      {error && <div className="text-red-600 text-[12.5px]">Error: {error}</div>}
      <div className="max-h-[420px] overflow-y-auto mt-2">
        {chunks.map((c) => {
          const open = openIndex === c.index;
          return (
            <div className="border border-border rounded-[10px] p-2.5 mb-2" key={c.index}>
              <div
                className="flex justify-between items-center cursor-pointer gap-2.5"
                onClick={() => setOpenIndex(open ? null : c.index)}
              >
                <span className="text-xs font-bold text-brand-dark">
                  <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>&#9656;</span>{" "}
                  Chunk #{c.index + 1} &middot; page {c.page}
                </span>
                <span className="text-[11px] text-muted whitespace-nowrap">
                  {c.word_count} words &middot; {c.token_count} tokens &middot; {c.unique_count} unique
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {c.top_terms.map(([term, weight]) => (
                  <span className="bg-brand-light text-brand-dark text-[10.5px] px-2 py-0.5 rounded-full" key={term}>
                    {term} <b>{weight.toFixed(2)}</b>
                  </span>
                ))}
              </div>
              {open && (
                <>
                  <div className="mt-2.5 pt-2.5 border-t border-dashed border-border">
                    <div className="text-[10.5px] text-muted mb-1.5">
                      Word filtering trace (tokenization step) - struck-through words were removed before
                      TF-IDF:
                    </div>
                    <div className="leading-[2.1]">
                      {c.trace.map((t, i) => (
                        <span
                          key={i}
                          title={t.reason || ""}
                          className={`inline-block text-[11.5px] px-1.5 mx-0.5 rounded ${
                            t.kept
                              ? "bg-brand-light text-brand-dark"
                              : t.reason === "stopword"
                              ? "text-[#a99a6b] line-through bg-[#f5f1e6]"
                              : "text-[#b9b3a8] line-through bg-[#f2f0ec]"
                          }`}
                        >
                          {t.word}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="text-xs leading-relaxed mt-2.5 pt-2.5 border-t border-dashed border-border whitespace-pre-wrap">
                    {c.text}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
