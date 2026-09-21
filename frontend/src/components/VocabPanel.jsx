import { useEffect, useState } from "react";
import { getVocab } from "../api.js";

export default function VocabPanel({ documentId }) {
  const [filter, setFilter] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getVocab(documentId, filter)
      .then((res) => !cancelled && setData(res))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId, filter]);

  return (
    <div className="bg-white border border-border rounded-2xl p-4.5 mb-4">
      <h2 className="text-sm font-semibold mb-2.5">4. Document vocabulary</h2>
      <div className="text-[11.5px] text-muted mb-2.5">
        {data
          ? `${data.vocab_size} distinct terms in the document. Showing ${data.rows.length}${
              data.truncated ? " (limited to first 300 rows, use the filter below)" : ""
            }, sorted by document frequency (df) descending.`
          : "Loading..."}
      </div>
      <input
        type="text"
        className="w-full px-2.5 py-2 border border-border rounded-lg text-[13px] mb-2.5"
        placeholder="Filter vocabulary by keyword..."
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      {error && <div className="text-red-600 text-[12.5px]">Error: {error}</div>}
      <div className="max-h-[340px] overflow-y-auto border border-border rounded-[10px]">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              <th className="sticky top-0 bg-brand-light text-brand-dark text-left px-2.5 py-1.5 text-[11px]">
                Term (token)
              </th>
              <th className="sticky top-0 bg-brand-light text-brand-dark text-right px-2.5 py-1.5 text-[11px]">
                Appears in (chunks)
              </th>
              <th className="sticky top-0 bg-brand-light text-brand-dark text-right px-2.5 py-1.5 text-[11px]">
                Total count (TF)
              </th>
              <th className="sticky top-0 bg-brand-light text-brand-dark text-right px-2.5 py-1.5 text-[11px]">
                IDF
              </th>
            </tr>
          </thead>
          <tbody>
            {data && data.rows.length === 0 && (
              <tr>
                <td colSpan={4} className="text-center text-muted py-3.5">
                  No matching term.
                </td>
              </tr>
            )}
            {data &&
              data.rows.map((row) => (
                <tr key={row.token} className="hover:bg-[#fafaf8]">
                  <td className="px-2.5 py-1.5 border-t border-border">{row.token}</td>
                  <td className="px-2.5 py-1.5 border-t border-border text-right font-mono text-muted">
                    {row.document_frequency}
                  </td>
                  <td className="px-2.5 py-1.5 border-t border-border text-right font-mono text-muted">
                    {row.total_frequency}
                  </td>
                  <td className="px-2.5 py-1.5 border-t border-border text-right font-mono text-muted">
                    {row.idf.toFixed(3)}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
