import { useState } from "react";
import { Button } from "../../shared/ui";
import { authorizedHeaders } from "../../shared/api/authorization.js";
import { readNewsGraphPackage, newsGraphError } from "./newsGraphImport.js";

async function request(path, body) {
  const response = await fetch(`/api/v1/admin/news-graph/${path}`, {
    method: "POST", headers: authorizedHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body), cache: "no-store",
  });
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(newsGraphError(response.status, value.detail));
  return value;
}

function sourceUrl(value) {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}

const reasons = {
  WARN_AMBIGUOUS_FACT: "Nội dung mới là đề xuất hoặc chưa xác nhận đã thực hiện",
  WARN_ENTITY_UNVERIFIED: "Chưa xác minh được định danh doanh nghiệp",
  WARN_EVIDENCE_INSUFFICIENT: "Đoạn trích chưa chứng minh đầy đủ quan hệ",
  WARN_TEMPORAL_BASIS_MISSING: "Chưa có thời điểm được xác nhận trong nguồn",
  ERR_SOURCE_HASH_MISMATCH: "Nội dung nguồn đã thay đổi",
  ERR_SOURCE_VERSION_MISMATCH: "Phiên bản nguồn không khớp",
  ERR_EVIDENCE_UNGROUNDED: "Đoạn trích không có trong nguồn đã lưu",
};

export default function NewsGraphPanel() {
  const [batch, setBatch] = useState(null);
  const [selected, setSelected] = useState(0);
  const [evaluation, setEvaluation] = useState(null);
  const [approved, setApproved] = useState({});
  const [published, setPublished] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const item = batch?.items[selected];
  const candidate = item?.candidate;
  const saved = candidate && approved[candidate.candidate_id];
  async function action(fn) {
    setBusy(true); setMessage("");
    try { await fn(); } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  async function load(file) {
    if (!file) return;
    setBatch(null); setEvaluation(null); setApproved({}); setPublished(false);
    await action(async () => {
      if (file.size > 2 * 1024 * 1024) throw new Error("Chỉ nhận file JSON tối đa 2 MB.");
      const data = readNewsGraphPackage(await file.text());
      const loaded = { ...data, graph_version_id: data.graph_version_id || crypto.randomUUID() };
      setBatch(loaded); setSelected(0); setNote("");
      const state = await request("state", { graph_version_id: loaded.graph_version_id });
      setApproved(Object.fromEntries(state.approved_candidate_ids.map(id => [id, { status: "APPROVED" }])));
      setPublished(state.published);
      setMessage(state.published ? "Phiên quan hệ này đã được nạp Neo4j." : "Đã đọc file và đối chiếu trạng thái duyệt. Cần kiểm tra nguồn tại server trước khi duyệt bản mới.");
    });
  }
  return <section className="space-y-4 rounded-xl border bg-white p-5">
    <h2 className="text-lg font-semibold">Quan hệ từ tin tức</h2>
    <p className="text-sm text-slate-600">Nhập bản trích xuất có đoạn bằng chứng. Kiểm tra nguồn, lưu quyết định duyệt bằng tài khoản đang đăng nhập, rồi nạp các quan hệ đã duyệt vào Neo4j.</p>
    <label className="block text-sm">File quan hệ cần duyệt
      <input type="file" accept=".json,application/json" disabled={busy} className="mt-2 block w-full" onChange={e => load(e.target.files[0])} />
    </label>
    {batch && <>
      <label className="block text-sm">Quan hệ
        <select className="mt-1 w-full rounded border p-2" value={selected} disabled={busy || published} onChange={e => {
          setSelected(Number(e.target.value)); setEvaluation(null); setNote(""); setMessage("");
        }}>
          {batch.items.map((row, index) => <option key={row.candidate.candidate_id} value={index}>
            {row.candidate.subject?.canonical_name} — {row.candidate.object?.canonical_name}
          </option>)}
        </select>
      </label>
      <p className="text-sm">Phạm vi: {candidate.attributes?.cooperation_scope || candidate.attributes?.position || candidate.relation_type}
        {candidate.temporal?.as_of ? ` · Theo nguồn ngày ${candidate.temporal.as_of.split("-").reverse().join("/")}` : " · Chưa xác định ngày trong nguồn"}</p>
      {candidate.evidence.map((evidence, index) => <article key={`${evidence.chunk_id}-${index}`} className="space-y-2 rounded border p-3 text-sm">
        <p className="font-medium">Bằng chứng {index + 1}</p>
        <blockquote className="whitespace-pre-wrap border-l-2 pl-3">{evidence.quote}</blockquote>
        {sourceUrl(evidence.locator?.url) && <a href={sourceUrl(evidence.locator.url)} target="_blank" rel="noreferrer" className="text-blue-700 underline">Mở bài gốc</a>}
      </article>)}
      <div className="flex flex-wrap gap-3">
        <Button disabled={busy || published} variant="secondary" onClick={() => action(async () => {
          const result = await request("evaluate", { graph_version_id: batch.graph_version_id, candidate });
          setEvaluation(result); setMessage(result.status === "APPROVED" ? "Bằng chứng đã qua kiểm tra nguồn. Bạn có thể lưu quyết định duyệt." : "Quan hệ còn thiếu điều kiện, chưa được nạp.");
        })}>Kiểm tra nguồn</Button>
      </div>
      {evaluation && <div className="text-sm"><p>Kết quả kiểm tra: {evaluation.status === "APPROVED" ? "Đủ điều kiện duyệt" : evaluation.status === "PENDING" ? "Cần bổ sung bằng chứng" : "Không đạt kiểm tra nguồn"}</p>
        {evaluation.reasons?.length > 0 && <ul className="mt-2 list-disc pl-5">{evaluation.reasons.map(code => <li key={code}>{reasons[code] || "Cần kiểm tra lại bằng chứng và thông tin quan hệ"}</li>)}</ul>}
      </div>}
      <label className="block text-sm">Ghi chú quyết định duyệt
        <textarea className="mt-1 w-full rounded border p-2" value={note} maxLength={2000} disabled={busy || published} onChange={e => setNote(e.target.value)} />
      </label>
      <div className="flex flex-wrap gap-3">
        <Button disabled={busy || published || Boolean(saved) || evaluation?.status !== "APPROVED" || !note.trim()} onClick={() => action(async () => {
          const result = await request("approve", { graph_version_id: batch.graph_version_id, candidate, note });
          setApproved(old => ({ ...old, [candidate.candidate_id]: result })); setMessage("Đã lưu quyết định duyệt và người duyệt. Quan hệ chưa được nạp Neo4j.");
        })}>Lưu quyết định duyệt</Button>
        <Button disabled={busy || published || !Object.keys(approved).length} onClick={() => action(async () => {
          const result = await request("publish", { graph_version_id: batch.graph_version_id });
          setPublished(result.published === true); setMessage(`Đã nạp ${result.counts.loaded} quan hệ đã duyệt vào Neo4j và đọc kiểm tra lại.`);
        })}>Nạp các quan hệ đã duyệt</Button>
      </div>
      {saved && <p className="text-sm text-green-700">Quan hệ này đã lưu quyết định duyệt.</p>}
      <p className="break-all text-xs text-slate-500">Phiên graph: {batch.graph_version_id}</p>
    </>}
    {message && <p role="status" className="rounded bg-slate-50 p-3 text-sm">{message}</p>}
  </section>;
}
