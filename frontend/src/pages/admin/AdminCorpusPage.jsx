// Trang A03: Phiên bản kho dữ liệu (route /admin/corpus và /admin/corpus/:version).
// Dữ liệu thật từ PostgreSQL. Thao tác: chuyển Chat sang một phiên đã đóng băng (quay lại phiên cũ),
// lưu trữ và khôi phục phiên. Phiên mới được tạo ở trang Thu thập & duyệt (lưu database → Chuyển corpus).

import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { authorizedHeaders } from "../../shared/api/authorization.js";
import { getOperations, localTime } from "./operationsApi.js";
import { actionErrorMessage, actionSuccessMessage, availableActions, corpusStatusLabel, docTypeLabel, indexStatusLabel, indexTone, pageLabel, servingFirst, shortId, typeBreakdown } from "./corpusView.js";

const PAGE = 30;

async function runAction(corpusId, action) {
  const response = await fetch(`/api/v1/admin/ingestion/corpus/${encodeURIComponent(corpusId)}/${action}`, {
    method: "POST", headers: authorizedHeaders({}), cache: "no-store",
  });
  let data = null;
  try { data = await response.json(); } catch { /* body is optional on errors */ }
  if (!response.ok) throw new Error(actionErrorMessage(data?.detail, response.status));
  return data;
}

function Row({ label, children }) {
  return <div className="flex flex-wrap justify-between gap-3 border-b py-2 text-sm"><dt className="text-slate-500">{label}</dt><dd className="break-all text-right">{children ?? "—"}</dd></div>;
}

function Documents({ corpusId }) {
  const [docType, setDocType] = useState(""), [offset, setOffset] = useState(0), [retry, setRetry] = useState(0);
  const [page, setPage] = useState(null), [error, setError] = useState("");
  useEffect(() => { setDocType(""); setOffset(0); }, [corpusId]);
  useEffect(() => {
    const abort = new AbortController(); setPage(null); setError("");
    const query = new URLSearchParams({ offset: String(offset), limit: String(PAGE) });
    if (docType) query.set("doc_type", docType);
    getOperations(`/corpus/${encodeURIComponent(corpusId)}/documents?${query}`, abort.signal)
      .then(data => { if (!abort.signal.aborted) setPage(data); })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [corpusId, docType, offset, retry]);
  return <Card title="Tài liệu trong phiên" action={page && <label className="text-sm">Loại
      <select className="ml-2 rounded border p-1.5" value={docType} onChange={e => { setDocType(e.target.value); setOffset(0); }}>
        <option value="">Tất cả</option>{page.doc_types.map(type => <option key={type} value={type}>{docTypeLabel(type)}</option>)}
      </select></label>}>
    {error && <ErrorState message={error} onRetry={() => setRetry(v => v + 1)} />}
    {!page && !error && <Skeleton rows={5} />}
    {page && (page.items.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead className="bg-slate-50"><tr><th className="p-2">Mã</th><th className="p-2">Tài liệu</th><th className="p-2">Loại</th><th className="p-2">Hash nguồn</th></tr></thead>
      <tbody>{page.items.map(item => <tr key={item.document_id} className="border-t">
        <td className="p-2 font-medium">{item.symbol || "—"}</td>
        <td className="max-w-md p-2">{item.title || "Không có tiêu đề"}<p className="break-all font-mono text-[11px] text-slate-400">{item.document_id}</p></td>
        <td className="p-2">{docTypeLabel(item.doc_type)}</td>
        <td className="p-2">{item.hash_matches ? <StatusBadge tone="success">Khớp</StatusBadge> : <StatusBadge tone="error">Lệch hash</StatusBadge>}</td>
      </tr>)}</tbody></table></div> : <EmptyState title="Không có tài liệu phù hợp" />)}
    {page && <div className="mt-4 flex items-center justify-between gap-2 text-sm">
      <Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - PAGE))}>Trước</Button>
      <span>{pageLabel(page)}</span>
      <Button variant="secondary" disabled={offset + PAGE >= page.total} onClick={() => setOffset(v => v + PAGE)}>Sau</Button>
    </div>}
  </Card>;
}

function Detail({ item, onChanged }) {
  const [busy, setBusy] = useState(false), [notice, setNotice] = useState(null);
  useEffect(() => { setNotice(null); }, [item.corpus_version_id]);
  async function perform(action) {
    if (!window.confirm(action.confirm)) return;
    setBusy(true); setNotice(null);
    try { const result = await runAction(item.corpus_version_id, action.id); setNotice({ ok: true, text: actionSuccessMessage(action.id, result) }); onChanged(); }
    catch (e) { setNotice({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }
  const actions = availableActions(item);
  return <div className="space-y-5">
    <Card title={`Phiên ${shortId(item.corpus_version_id)}${item.version_label ? ` · ${item.version_label}` : ""}`}
      action={item.serving ? <StatusBadge tone="success">Đang phục vụ Chat</StatusBadge> : null}>
      <dl>
        <Row label="Mã phiên corpus"><span className="font-mono text-xs">{item.corpus_version_id}</span></Row>
        <Row label="Trạng thái corpus">{corpusStatusLabel(item.status)}</Row>
        <Row label="Đóng băng lúc">{localTime(item.frozen_at)}</Row>
        <Row label="Chỉ mục (index)"><span className="font-mono text-xs">{item.index_version_id}</span></Row>
        <Row label="Trạng thái chỉ mục"><StatusBadge tone={indexTone(item.index_status)}>{indexStatusLabel(item.index_status)}</StatusBadge></Row>
        <Row label="Mô hình embedding">{item.embedding_model}</Row>
        <Row label="Chỉ mục tạo lúc">{localTime(item.built_at)}</Row>
        <Row label="Manifest SHA-256"><span className="font-mono text-xs">{item.manifest_sha256}</span></Row>
        <Row label="Tổng số tài liệu">{Number(item.documents).toLocaleString("vi-VN")}</Row>
      </dl>
      {item.description && <p className="mt-3 text-sm text-slate-600">{item.description}</p>}
      {actions.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{actions.map(action => <Button key={action.id} disabled={busy} variant={action.tone} onClick={() => perform(action)}>{action.label}</Button>)}</div>}
      {notice && <p role={notice.ok ? "status" : "alert"} className={`mt-3 rounded-lg border p-3 text-sm ${notice.ok ? "border-blue-200 bg-blue-50 text-blue-900" : "border-red-200 bg-red-50 text-red-800"}`}>{notice.text}</p>}
      <div className="mt-4 flex flex-wrap gap-2">{typeBreakdown(item.by_type).map(row =>
        <span key={row.type} className="rounded-full border bg-slate-50 px-3 py-1 text-xs">{row.label}: <strong>{row.count.toLocaleString("vi-VN")}</strong></span>)}</div>
    </Card>
    <Documents corpusId={item.corpus_version_id} />
  </div>;
}

export default function AdminCorpusPage() {
  const { version } = useParams(), navigate = useNavigate();
  const [data, setData] = useState(null), [error, setError] = useState(""), [retry, setRetry] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setError("");
    getOperations("/corpus", abort.signal)
      .then(result => { if (!abort.signal.aborted) setData(result); })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [retry]);
  const items = servingFirst(data?.items);
  const selected = items.find(item => item.corpus_version_id === version) || (version ? null : items[0]);
  return <AdminLayout>
    <header className="space-y-1">
      <Link className="text-xs text-blue-600" to={ADMIN_LINKS.overview}>Tổng quan vận hành</Link>
      <h1 className="text-xl font-bold">Phiên bản kho dữ liệu</h1>
      <p className="text-sm text-slate-500">Dữ liệu thật từ PostgreSQL. Chuyển Chat về một phiên cũ hoặc lưu trữ phiên ở đây; tạo phiên mới ở <Link className="text-blue-600 underline" to={ADMIN_LINKS.ingestion}>Thu thập & duyệt</Link>.</p>
    </header>
    {error && <ErrorState message={error} onRetry={() => setRetry(v => v + 1)} />}
    {!data && !error && <Skeleton rows={6} />}
    {data && (items.length ? <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
      <section className="rounded-xl border bg-white p-4"><h2 className="mb-4 font-semibold">Các phiên ({items.length})</h2>
        <ul className="space-y-3">{items.map(item => <li key={item.corpus_version_id}>
          <button type="button" aria-current={selected?.corpus_version_id === item.corpus_version_id ? "true" : undefined}
            onClick={() => navigate(`${ADMIN_LINKS.corpus}/${item.corpus_version_id}`)}
            className={`w-full rounded-lg border p-3 text-left text-sm hover:bg-slate-50 ${selected?.corpus_version_id === item.corpus_version_id ? "border-blue-500 bg-blue-50" : ""}`}>
            <span className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs">{shortId(item.corpus_version_id)}</span>
              {item.serving && <StatusBadge tone="success">Đang phục vụ</StatusBadge>}</span>
            <span className="mt-1 block text-slate-700">{Number(item.documents).toLocaleString("vi-VN")} tài liệu · {indexStatusLabel(item.index_status)}</span>
            <span className="block text-xs text-slate-500">{localTime(item.frozen_at || item.built_at)}</span>
          </button></li>)}</ul>
      </section>
      <div>{selected ? <Detail item={selected} onChanged={() => setRetry(v => v + 1)} /> : <EmptyState title="Không tìm thấy phiên này" description="Chọn một phiên trong danh sách bên trái." />}</div>
    </div> : <EmptyState title="Chưa có phiên corpus nào" />)}
  </AdminLayout>;
}
