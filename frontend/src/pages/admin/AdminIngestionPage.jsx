import { useCallback, useEffect, useRef, useState } from "react";
import AdminLayout from "./AdminLayout.jsx";
import { Button, EmptyState, StatusBadge, Modal } from "../../shared/ui";
import { authorizedHeaders } from "../../shared/api/authorization.js";
import { retainApprovedSelection, toggleArticleSelection } from "./ingestionSelection.js";
import { qualityLabel, reviewNote, replacementArticleId } from "./sourceQuality.js";

async function api(path, method = "GET", body) {
  const response = await fetch(`/api/v1/admin/ingestion${path}`, {
    method, headers: authorizedHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok) {
    const messages = { ANOTHER_JOB_IS_RUNNING: "Đang có job khác xử lý. Đợi hoàn tất hoặc kiểm tra job bị treo.",
      ARTICLE_NOT_APPROVED: "Chỉ chọn các bài đã duyệt và chưa được lập chỉ mục.",
      ARTICLE_ALREADY_DECIDED: "Bài này đã có quyết định. Hãy làm mới để xem trạng thái hiện tại.",
      ADMIN_INGEST_DATABASE_URL_REQUIRED: "Chưa cấu hình kết nối ghi chỉ mục cho admin.",
      INDEX_ACTIVATION_UNAVAILABLE: "Chưa kích hoạt được phiên mới. Kiểm tra kết nối DB và thử lại.",
      NEW_CORPUS_SEARCH_UNAVAILABLE: "Chưa tìm thử được phiên mới. Kiểm tra nguồn và cache truy xuất.",
      INCOMPLETE_SOURCE: "Nguồn còn thiếu tiêu đề, nội dung hoặc URL nên chưa thể duyệt.",
      SOURCE_TEXT_EXTRACTION_REQUIRED: "Phải đọc PDF / OCR ảnh để có nội dung chính trước khi duyệt hoặc tạo chunk.",
      NO_AUTOMATICALLY_HELD_ARTICLES: "Không còn bài bị giữ tự động để kiểm tra lại. Các bài do người duyệt giữ cần mở và xử lý riêng.",
      INDEX_CHANGED_SINCE_BUILD: "Chỉ mục đã thay đổi sau khi tạo. Cần kiểm tra lại trước khi kích hoạt." };
    throw new Error(messages[data.detail] || (response.status === 401 ? "Phiên đăng nhập hết hạn." : response.status === 403 ? "Tài khoản không có quyền quản trị." : typeof data.detail === "string" ? data.detail : `Yêu cầu thất bại (${response.status})`));
  }
  return data;
}
const STATUS = { PENDING: "Chờ duyệt", APPROVED: "Đã duyệt", REJECTED: "Đã từ chối", SUPERSEDED: "Đã thay bằng bản PDF/OCR",
  QUARANTINED: "Cần kiểm tra", INDEXED: "Đã xử lý", QUEUED: "Đang đợi", RUNNING: "Đang xử lý",
  COMPLETED: "Hoàn tất", PARTIAL: "Có lỗi thu thập", FAILED: "Thất bại", ACTIVE: "Đã nạp xong", INTERRUPTED: "Đã ngắt" };
const PHASE = { OCR: "Đọc PDF / OCR ảnh", COLLECTING: "Đang lấy nguồn", WAITING_REVIEW: "Chờ duyệt", CHUNKING: "Chia chunk",
  EMBEDDING: "Tạo vector", WRITING_INDEX: "Lưu vào dữ liệu chung", PUBLISHING: "Hoàn tất nạp dữ liệu",
  PREPARING_SEARCH: "Chuẩn bị tìm kiếm dữ liệu vừa nạp",
  READY_TO_ACTIVATE: "Lần nạp cũ chưa hoàn tất", PUBLISHED_NEW_VERSION: "Đã lưu và có thể hỏi trong Chat", INDEXING: "Lập chỉ mục" };
function sourceLink(value) {
  try { const u = new URL(value); return u.protocol === "https:" && u.hostname === "fireant.vn" ? u.href : null; }
  catch { return null; }
}

export default function AdminIngestionPage() {
  const [source, setSource] = useState(null), [articles, setArticles] = useState([]), [jobs, setJobs] = useState([]);
  const [detail, setDetail] = useState(null), [note, setNote] = useState("");
  const [sourceOpen, setSourceOpen] = useState(false), [sourceLoading, setSourceLoading] = useState(false), [sourceError, setSourceError] = useState("");
  const [chunks, setChunks] = useState(null), [chunkOffset, setChunkOffset] = useState(0), [chunksLoading, setChunksLoading] = useState(false), [chunksError, setChunksError] = useState("");
  const [selectionInfo, setSelectionInfo] = useState({ counts:{}, approved_ids:[], selection_limit:500 });
  const sourceRequest = useRef(0);
  const closeSource = useCallback(() => { sourceRequest.current += 1; setSourceOpen(false); }, []);
  async function openSource(id) {
    const request = ++sourceRequest.current;
    setSourceOpen(true); setDetail(null); setNote(""); setChunks(null); setChunkOffset(0); setChunksError(""); setSourceLoading(true); setSourceError(""); setError(""); setMessage("");
    try { const data = await api(`/articles/${id}`); if (request === sourceRequest.current) setDetail(data); }
    catch (e) { if (request === sourceRequest.current) setSourceError(e.message || "Không tải được nguồn."); }
    finally { if (request === sourceRequest.current) setSourceLoading(false); }
  }
  async function loadChunks(offset = 0) {
    const request = sourceRequest.current;
    setChunksLoading(true); setChunksError("");
    try {
      const data = await api(`/articles/${detail.id}/chunks?offset=${offset}&limit=30`);
      if (request === sourceRequest.current) { setChunks(data); setChunkOffset(offset); }
    } catch (e) { if (request === sourceRequest.current) setChunksError(e.message); }
    finally { if (request === sourceRequest.current) setChunksLoading(false); }
  }
  const [articleOffset, setArticleOffset] = useState(0), [articleTotal, setArticleTotal] = useState(0), [articleStatus, setArticleStatus] = useState("PENDING");
  const articlePath = `/articles?offset=${articleOffset}&limit=50${articleStatus ? `&status=${articleStatus}` : ""}`;
  const [selected, setSelected] = useState([]), [error, setError] = useState(""), [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState(""), [searchResult, setSearchResult] = useState(null);
  async function reload() {
    const [s, a, j, selections] = await Promise.all([api("/source"), api(articlePath), api("/jobs"), api("/articles/selection")]);
    setSource(s); setArticles(a.items); setArticleTotal(a.total); setJobs(j.items);
    setSelectionInfo(selections); setSelected(ids => retainApprovedSelection(ids, selections.approved_ids));
  }
  useEffect(() => {
    let active = true;
    reload().catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [articlePath]);
  // Poll job progress without replacing the source form while it is being edited.
  useEffect(() => {
    let active = true;
    const timer = setInterval(async () => {
      try {
        const [a, j, selections] = await Promise.all([api(articlePath), api("/jobs"), api("/articles/selection")]);
        if (active) {
          setArticles(a.items); setArticleTotal(a.total); setJobs(j.items);
          setSelectionInfo(selections); setSelected(ids => retainApprovedSelection(ids, selections.approved_ids));
        }
      } catch { /* Manual refresh reports errors; polling preserves the current view. */ }
    }, 10000);
    return () => { active = false; clearInterval(timer); };
  }, [articlePath]);
  async function action(fn, success) {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); await reload(); if (success) setMessage(success); }
    catch (e) { setError(e.message || "Không kết nối được backend."); }
    finally { setBusy(false); }
  }
  const running = jobs.some(j => ["RUNNING", "QUEUED"].includes(j.status));
  return <AdminLayout>
    <div className="flex flex-wrap justify-between gap-3"><div><h1 className="text-2xl font-semibold">Thu thập và duyệt News</h1><p className="mt-1 text-sm text-slate-500">Nguồn gốc → duyệt bài → chunk → embedding → index mới</p></div>
      <Button disabled={busy} onClick={() => action(reload, "Đã làm mới.")}>Làm mới</Button></div>
    {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-xl border bg-blue-50 p-4 text-blue-900">{message}</p>}
    {loading && <p role="status">Đang tải…</p>}
    {source && <section className="space-y-4 rounded-xl border bg-white p-5"><h2 className="text-lg font-semibold">Nguồn FireAnt</h2>
      <div className="flex flex-wrap items-end gap-5">
        <label className="text-sm">Giờ chạy mỗi ngày (Việt Nam)<input className="mt-1 block rounded border p-2" type="number" min="0" max="23" value={source.hour} onChange={e => setSource({ ...source, hour: Number(e.target.value) })} /></label>
        <label className="text-sm">Số bài tối đa/lượt<input className="mt-1 block rounded border p-2" type="number" min="1" max="500" value={source.limit} onChange={e => setSource({ ...source, limit: Number(e.target.value) })} /></label>
        <label className="text-sm">Số trang tối đa/mã<input className="mt-1 block rounded border p-2" type="number" min="1" max="20" value={source.max_pages} onChange={e => setSource({ ...source, max_pages: Number(e.target.value) })} /></label>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={source.enabled} onChange={e => setSource({ ...source, enabled: e.target.checked })} />Bật lịch hằng ngày</label>
        <Button disabled={busy} onClick={() => action(() => api("/source", "PUT", source), "Đã lưu lịch. Scheduler phải đang chạy để thực thi.")}>Lưu cấu hình</Button>
        <Button disabled={busy || running} onClick={() => action(() => api("/crawl", "POST"), "Đã tạo job thu thập. Kết quả sẽ vào hàng đợi duyệt.")}>Cào ngay</Button>
      </div>
      <div className="flex flex-wrap gap-5 text-sm">
        <label className="flex gap-2"><input type="checkbox" checked={source.include_market} onChange={e => setSource({ ...source, include_market: e.target.checked })} />Gồm tin thị trường chung</label>
        <label className="flex gap-2"><input type="checkbox" checked={source.auto_approve} onChange={e => setSource({ ...source, auto_approve: e.target.checked })} />Tự động duyệt bài mới đạt kiểm tra nguồn</label>
      </div>
      <label className="block text-sm">Mã cổ phiếu (cách nhau bằng dấu phẩy)<input className="mt-1 block w-full rounded border p-2" value={(source.symbols || []).join(",")} onChange={e => setSource({ ...source, symbols: e.target.value.toUpperCase().split(",") })} onBlur={() => setSource({ ...source, symbols: [...new Set(source.symbols.map(s => s.trim()).filter(Boolean))] })} /></label>
      <p className="text-sm text-slate-500">Nguồn: FireAnt → tin theo các mã trên{source.include_market ? " và thị trường chung" : ""}. Đọc luân phiên từng mã, chống trùng URL. Giới hạn số bài là toàn lượt, không phải mỗi mã; không bảo đảm đủ toàn bộ lịch sử.</p>
      <p className="text-sm text-slate-500">Tin ngắn có đủ nội dung vẫn được xét duyệt. Bài chỉ dẫn sang PDF hoặc ảnh cần đọc tệp/OCR trước. Duyệt tự động kiểm nguồn, phần chữ và ngày đăng; không xác minh sự thật tài chính, không tự tạo vector hoặc kích hoạt corpus.</p>
    </section>}
    <section className="space-y-3">
      <nav aria-label="Các bước xử lý bài" className="flex flex-wrap gap-2">{["PENDING","APPROVED","INDEXED","QUARANTINED","REJECTED"].map(status => <Button key={status} variant={articleStatus === status ? "primary" : "secondary"} onClick={() => { setArticleStatus(status); setArticleOffset(0); }}>{STATUS[status]} ({selectionInfo.counts[status] || 0})</Button>)}</nav>
      <div className="flex flex-wrap justify-between gap-3"><h2 className="text-lg font-semibold">{STATUS[articleStatus] || "Tất cả bài"} ({articleTotal})</h2>
      {articleStatus === "PENDING" && <Button disabled={busy || running} variant="secondary" onClick={() => action(async () => {
        const result = await api("/auto-review", "POST");
        setMessage(`Tự động duyệt: ${result.approved} đạt, ${result.quarantined} cần kiểm tra.`);
      }, null)}>Duyệt tự động bài đang chờ</Button>}
      {articleStatus === "QUARANTINED" && <Button disabled={busy || running} variant="secondary" onClick={() => action(async () => {
        await api("/auto-review/recheck", "POST");
        setMessage("Đã bắt đầu kiểm tra lại và đọc PDF / OCR các bài thiếu phần chữ. Xem tiến độ ở Các lần chạy gần nhất; bản đọc được sẽ vào Chờ duyệt.");
      }, null)}>Kiểm tra lại & đọc PDF / OCR</Button>}
      {articleStatus === "APPROVED" && <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={busy || running || !selectionInfo.approved_ids.length} onClick={() => setSelected([...selectionInfo.approved_ids])}>{(selectionInfo.counts.APPROVED || 0) > selectionInfo.selection_limit ? `Chọn ${selectionInfo.selection_limit} bài đầu đã duyệt` : "Chọn tất cả bài đã duyệt"}</Button>
        <Button variant="ghost" disabled={!selected.length || busy} onClick={() => setSelected([])}>Bỏ chọn tất cả</Button>
        <Button disabled={busy || running || !selected.length} onClick={() => action(() => api("/index", "POST", { article_ids: selected }), "Đang chia chunk, tạo vector và nạp vào dữ liệu chung. Hoàn tất là có thể hỏi trong Chat.")}>Tạo chunk & lưu dữ liệu ({selected.length})</Button>
      </div>}</div>
      {articleStatus === "APPROVED" && <p className="text-sm text-slate-500">Mở lại từng bài để kiểm tra. Có thể chọn tất cả trên các trang rồi bỏ tick bài chưa muốn xử lý. Đang chọn {selected.length} bài, tối đa {selectionInfo.selection_limit} bài/lượt.</p>}
      {articleStatus === "APPROVED" && <p className="text-sm text-slate-500">Một lần bấm sẽ chia chunk, tạo vector, lưu vào dữ liệu chung và cho Chat sử dụng sau khi nạp xong.</p>}
      {articleStatus === "QUARANTINED" && <p className="text-sm text-slate-500">Kiểm tra lại các bài bị giữ tự động, gồm đọc PDF và OCR ảnh khi thiếu chữ. Bản trích xuất cần kiểm tra trong Chờ duyệt; bài lỗi giữ nguyên tại đây. Mỗi lượt tối đa 500 bài.</p>}
      {articles.length ? <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-slate-50"><tr><th className="p-3">Chọn</th><th className="p-3">Bài viết</th><th className="p-3">Trạng thái</th><th className="p-3">Chi tiết</th></tr></thead>
        <tbody>{articles.map(a => <tr key={a.id} className="border-t"><td className="p-3">{a.status === "APPROVED" ? <input aria-label={`Chọn ${a.title}`} type="checkbox" disabled={busy || running || !selectionInfo.approved_ids.includes(a.id) || (selected.length >= selectionInfo.selection_limit && !selected.includes(a.id))} checked={selected.includes(a.id)} onChange={e => setSelected(ids => toggleArticleSelection(ids, a.id, e.target.checked))} /> : "—"}</td>
          <td className="max-w-lg p-3"><p className="font-medium">{a.title || "Thiếu tiêu đề"}</p><p className="text-xs text-slate-500">{a.source} · {(a.symbols || []).join(", ") || "Tin thị trường chung"} · {a.published_at || "Chưa rõ ngày đăng"}</p></td><td className="p-3">{STATUS[a.status]}{a.status === "QUARANTINED" && <p className="mt-1 max-w-xs text-xs text-amber-800">{(a.quality_reasons || []).length ? a.quality_reasons.map(qualityLabel).join("; ") : "Đạt điều kiện mới — có thể kiểm tra lại"}</p>}</td>
          <td className="p-3"><Button disabled={busy} variant="secondary" onClick={() => openSource(a.id)}>{a.status === "INDEXED" ? "Xem bài & chunk" : "Xem nguồn"}</Button></td></tr>)}</tbody></table></div>
        : <EmptyState title={`Chưa có bài trong mục ${STATUS[articleStatus] || "này"}`} description="Chọn mục khác để xem bài ở bước tương ứng." />}
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><span>{articleTotal ? `${articleOffset+1}–${Math.min(articleOffset+50,articleTotal)} / ${articleTotal}` : "0 bài"}</span><div className="flex gap-2"><Button disabled={!articleOffset} onClick={() => setArticleOffset(n => Math.max(0,n-50))}>Trước</Button><Button disabled={articleOffset+50>=articleTotal} onClick={() => setArticleOffset(n => n+50)}>Sau</Button></div></div>
    </section>
    <Modal open={sourceOpen} title={detail?.payload.title || "Xem nguồn bài viết"} onClose={closeSource} wide>
      {sourceLoading && <p role="status">Đang tải bản nguồn…</p>}
      {(sourceError || error) && <p role="alert" className="rounded bg-red-50 p-3 text-red-800">{sourceError || error}</p>}
      {detail && <section className="space-y-4">
      <p className="text-sm">Nguồn: {detail.payload.source} · Mã: {(detail.payload.symbols || []).join(", ") || "Tin thị trường chung"} · {detail.payload.published_at || "Chưa rõ ngày đăng"}</p>
      {replacementArticleId(detail) && <section className="space-y-2 rounded border border-blue-200 bg-blue-50 p-3 text-sm"><p>Đây là bản nguồn trước khi đọc PDF/OCR. Nội dung đã đọc được lưu ở bản mới để kiểm tra và duyệt.</p><Button onClick={() => openSource(replacementArticleId(detail))}>Mở bản đã đọc PDF/OCR</Button></section>}
      {!replacementArticleId(detail) && detail.quality_reasons?.length > 0 && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-amber-900">{detail.quality_reasons.map(code => <p key={code}>{qualityLabel(code)}</p>)}</div>}
      {detail.attachments?.length > 0 && <section className="space-y-2 rounded border p-3"><h3 className="font-semibold">Tệp đính kèm</h3>{detail.attachments.map((file,i) => <a key={i} className="block break-all text-blue-700 underline" href={file.url} target="_blank" rel="noreferrer">{file.name}</a>)}<p className="text-xs text-slate-500">Bấm đọc PDF / OCR để đưa nội dung tệp vào bản mới trước khi duyệt.</p></section>}
      {!detail.payload.extraction && ["PENDING", "QUARANTINED"].includes(detail.status) && <Button disabled={busy || running} variant="secondary" onClick={() => action(async () => {
        await api(`/articles/${detail.id}/ocr`, "POST"); closeSource();
      }, "Đã bắt đầu đọc PDF / OCR. Khi hoàn tất, mở bản mới trong Chờ duyệt để kiểm tra.")}>Đọc PDF / OCR ảnh</Button>}
      {detail.payload.extraction && <section className="rounded border border-blue-200 bg-blue-50 p-3 text-sm"><p>Đã trích xuất bằng OCR sẵn có của dự án. Kiểm tra nội dung, đặc biệt số liệu, trước khi duyệt.</p>{detail.payload.extraction.files.map((file,i) => <p key={i}>{file.name} · {file.pages.length} trang · {file.pages.some(p => p.method === "tesseract") ? "Có OCR ảnh" : "Đọc lớp chữ PDF"}</p>)}</section>}
      {sourceLink(detail.payload.url) && <a className="text-sm text-blue-700 underline" href={sourceLink(detail.payload.url)} target="_blank" rel="noreferrer">Mở bài gốc</a>}
      <p className="break-all text-xs text-slate-500">SHA256: {detail.digest}</p><pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-4 font-sans text-sm">{detail.payload.content || "Thiếu nội dung"}</pre>
      <details><summary className="cursor-pointer text-sm">Payload gốc và metadata đã lưu</summary><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(detail.payload, null, 2)}</pre></details>
      {["PENDING", "QUARANTINED"].includes(detail.status) && <><label className="block text-sm">Lý do quyết định<textarea className="mt-1 block w-full rounded border p-3" maxLength="2000" value={note} onChange={e => setNote(e.target.value)} /></label>
        {detail.quality_reasons?.some(code => ["OCR_REQUIRED", "ATTACHMENT_TEXT_REQUIRED"].includes(code)) && <p className="text-sm text-amber-800">Chưa thể duyệt: cần bấm Đọc PDF / OCR ảnh và kiểm tra nội dung trích xuất trước.</p>}
        <div className="flex flex-wrap gap-3">{[["APPROVED", "Duyệt bài"], ["REJECTED", "Từ chối"], ["QUARANTINED", "Cần kiểm tra"]].map(([decision, label]) => <Button key={decision} disabled={busy || note.trim().length < 3 || (decision === "APPROVED" && detail.quality_reasons?.some(code => ["OCR_REQUIRED", "ATTACHMENT_TEXT_REQUIRED"].includes(code)))} variant={decision === "REJECTED" ? "danger" : "secondary"}
          onClick={() => action(async () => { setDetail(await api(`/articles/${detail.id}/review`, "POST", { decision, note })); setNote(""); }, "Đã lưu quyết định và lịch sử.")}>{label}</Button>)}</div></>}
      <h3 className="font-medium">Lịch sử duyệt</h3>{detail.reviews.length ? detail.reviews.map(r => <p className="break-all text-sm" key={r.id}>{r.created_at} · {r.decision === "REJECTED" && r.note.startsWith("Đã thay bằng bản trích xuất cần duyệt: ") ? STATUS.SUPERSEDED : STATUS[r.decision]} · {reviewNote(r.note)} · {r.actor}</p>) : <p className="text-sm text-slate-500">Chưa có quyết định.</p>}
      {detail.status === "INDEXED" && <section className="space-y-3 border-t pt-4"><h3 className="font-semibold">Chunk đã lưu và phiên index</h3>
        <Button disabled={chunksLoading} onClick={() => loadChunks(0)}>{chunksLoading ? "Đang tải chunk…" : "Xem chunk đã lưu trong DB"}</Button>
        {chunksError && <p role="alert" className="text-red-700">{chunksError}</p>}
        {chunks && <><p className="text-sm">Tổng {chunks.total} chunk</p>{chunks.versions.map(v => <p key={v.index_version_id} className="break-all font-mono text-xs">Index: {v.index_version_id} · {v.status === "ACTIVE" ? "Đã kích hoạt" : "Chờ kích hoạt"} · Corpus: {v.corpus_version_id || "—"}</p>)}
          {chunks.items.map(c => <article key={c.chunk_id} className="space-y-2 rounded border p-3"><h4 className="font-medium">Chunk {c.position+1} · {c.token_count} từ</h4><p className="break-all font-mono text-xs">{c.chunk_id}</p><pre className="whitespace-pre-wrap font-sans text-sm">{c.text}</pre><p className="break-all font-mono text-xs text-slate-500">SHA256: {c.content_hash}</p></article>)}
          <div className="flex gap-2"><Button disabled={chunksLoading || !chunkOffset} onClick={() => loadChunks(Math.max(0,chunkOffset-30))}>Chunk trước</Button><Button disabled={chunksLoading || chunkOffset+30>=chunks.total} onClick={() => loadChunks(chunkOffset+30)}>Chunk sau</Button></div>
        </>}
      </section>}
    </section>}
    </Modal>
    <section className="space-y-3"><h2 className="text-lg font-semibold">Các lần chạy gần nhất</h2>
      {jobs.map(j => <div key={j.id} className="space-y-2 rounded-xl border bg-white p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><StatusBadge tone={j.status === "FAILED" ? "error" : "neutral"}>{STATUS[j.status] || j.status}</StatusBadge><span className="ml-3 text-sm">{j.kind === "CRAWL" ? "Thu thập nguồn" : j.kind === "RECHECK" ? "Kiểm tra lại & OCR" : j.kind === "OCR" ? "Đọc PDF / OCR ảnh" : "Chunk và vector"} · {PHASE[j.details.phase] || "Đang đợi"}</span></div>
        {j.kind === "INDEX" && ["FAILED","INDEXED"].includes(j.status) && <Button disabled={busy || running} onClick={() => action(() => api(`/jobs/${j.id}/retry`, "POST"), "Đã chạy lại lần nạp. Hệ thống tự hoàn tất các bước còn lại.")}>{j.status === "FAILED" ? "Chạy lại lần nạp" : "Tiếp tục lần nạp cũ"}</Button>}</div>
        <p className="break-all font-mono text-xs text-slate-500">{j.id}</p><p className="text-sm">Bài mới: {j.details.new_articles ?? "—"} · Trùng: {j.details.duplicates ?? "—"} · Chunk: {j.details.chunks ?? "—"}</p>
        {j.details.shared_chunk_count > 0 && <p className="text-sm text-blue-700">Dữ liệu tìm kiếm chung: {j.details.shared_chunk_count.toLocaleString("vi-VN")} chunk</p>}
        {j.kind === "OCR" && j.details.total > 0 && <p className="text-sm">Đã đọc {j.details.completed || 0}/{j.details.total} tệp</p>}
        {j.kind === "OCR" && j.details.article_id && <Button variant="secondary" onClick={() => openSource(j.details.article_id)}>Xem bản đã đọc để duyệt</Button>}
        {j.kind === "RECHECK" && <section className="space-y-2"><p className="text-sm">Đã kiểm tra {j.details.completed || 0}/{j.details.total || j.details.article_ids.length} bài · Đã đọc PDF/OCR: {j.details.extracted || 0} · Đạt điều kiện: {j.details.approved || 0} · Lỗi: {j.details.errors?.length || 0}</p>
          {(j.details.results || []).filter(r => r.article_id).map(r => <Button key={r.article_id} variant="secondary" onClick={() => openSource(r.article_id)}>Xem bản đã đọc: {r.title}</Button>)}
          {(j.details.errors || []).map(e => <div key={e.article_id} className="rounded bg-red-50 p-2 text-sm"><p className="text-red-700">{e.error}</p><Button variant="secondary" onClick={() => openSource(e.article_id)}>Mở bài bị lỗi</Button></div>)}
        </section>}
        {j.details.total_documents > 0 && <div><p className="text-sm">Đã tạo vector: {j.details.completed_documents || 0}/{j.details.total_documents} bài · {PHASE[j.details.phase] || j.details.phase}</p><progress className="h-2 w-full" value={j.details.completed_documents || 0} max={j.details.total_documents} /></div>}
        {j.details.error && <p className="text-sm text-red-700">Mã lỗi: {j.details.error}</p>}
        {["QUEUED", "RUNNING"].includes(j.status) && <Button disabled={busy} variant="secondary" onClick={() => {
          if (window.confirm("Ngắt job này? Bước đang thực hiện có thể cần hoàn tất trước khi dừng. Bạn có thể tạo lại job sau đó."))
            action(() => api(`/jobs/${j.id}/interrupt`, "POST"), "Đã yêu cầu ngắt job; phiên dữ liệu đang phục vụ được giữ nguyên.");
        }}>Ngắt / giải phóng job bị treo</Button>}
        {j.kind !== "RECHECK" && j.details.errors?.length > 0 && <p className="text-sm text-red-700">{j.details.errors.length} bài thu thập lỗi; xem lại lượt chạy.</p>}
        {j.details.corpus_version_id && <p className="break-all text-xs">Corpus mới: {j.details.corpus_version_id}</p>}
        {j.status === "ACTIVE" && <div className="flex flex-wrap gap-3"><input aria-label="Câu hỏi tìm thử phiên mới" className="min-w-64 flex-1 rounded border p-2 text-sm" placeholder="Nhập câu hỏi để tìm thử trên phiên mới…" value={question} onChange={e => setQuestion(e.target.value)} />
          <Button disabled={busy || question.trim().length < 3} onClick={() => action(async () => setSearchResult(await api(`/jobs/${j.id}/search`, "POST", { question })), "Đã tìm trên corpus mới.")}>Tìm thử phiên mới</Button></div>}
      </div>)}
      {!jobs.length && <EmptyState title="Chưa có lần chạy" />}
    </section>
    {searchResult && <section className="space-y-3 rounded-xl border bg-white p-5"><h2 className="font-semibold">Bằng chứng từ phiên mới</h2><p className="break-all text-xs text-slate-500">Corpus: {searchResult.corpus_version_id}</p>
      {searchResult.items.length ? searchResult.items.map(hit => <article key={hit.chunk_id} className="space-y-2 border-t pt-3"><h3 className="font-medium">{hit.title}</h3><pre className="whitespace-pre-wrap font-sans text-sm">{hit.text}</pre>
        {sourceLink(hit.source_url) && <a href={sourceLink(hit.source_url)} target="_blank" rel="noreferrer" className="text-sm text-blue-700 underline">Bài gốc</a>}<p className="break-all font-mono text-xs">{hit.content_hash}</p></article>) : <p>Không có kết quả phù hợp.</p>}
    </section>}
  </AdminLayout>;
}
