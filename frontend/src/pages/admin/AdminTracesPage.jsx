import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { getOperations, localTime } from "./operationsApi.js";

const LABELS = { SUCCESS: "Có câu trả lời", ERROR: "Lỗi vận hành", INSUFFICIENT_EVIDENCE: "Không đủ bằng chứng", CLARIFICATION: "Cần làm rõ", OTHER: "Phản hồi khác" };
const tone = outcome => outcome === "SUCCESS" ? "success" : outcome === "ERROR" ? "error" : "warning";
const number = value => value == null ? "Chưa ghi nhận" : Number(value).toLocaleString("vi-VN");
function Row({ label, children }) { return <div className="flex flex-wrap justify-between gap-3 border-b py-2 text-sm"><dt className="text-slate-500">{label}</dt><dd className="max-w-xl break-all text-right">{children ?? "Chưa ghi nhận"}</dd></div>; }

function TraceDetail({ row }) {
  const d = row.details || {};
  const names = [...new Set(row.calls.map(call => call.model))];
  return <div className="space-y-5">
    <div className="rounded-xl border bg-white p-4"><p className="break-all font-mono text-xs">{row.id}</p><p className="mt-3 text-sm">{d.question || "Lượt cũ chưa lưu nội dung câu hỏi."}</p><div className="mt-3"><StatusBadge tone={tone(row.outcome)}>{LABELS[row.outcome] || row.outcome}</StatusBadge></div></div>
    <Card title="(1) Tổng quan truy vấn"><dl>
      <Row label="Bắt đầu">{localTime(row.created_at)}</Row><Row label="Thời gian thực tế">{(row.duration_ms / 1000).toFixed(3)} giây</Row>
      <Row label="Doanh nghiệp">{row.companies.join(", ") || "Không xác định"}</Row><Row label="Model">{names.join(", ") || "Không gọi model"}</Row>
      <Row label="Phiên bản cấu hình xử lý">{d.policy_version}</Row><Row label="Phiên bản kho dữ liệu">{d.corpus_version_id}</Row><Row label="Cách trả lời">{row.response_mode || "Không sinh câu trả lời"}</Row>
    </dl></Card>
    <Card title="(2) Lý do trạng thái"><p className="break-all text-sm">{d.reason_code || "Lượt cũ chưa lưu mã nguyên nhân."}</p><p className="mt-3 text-xs text-slate-500">Có câu trả lời gồm cả trích nguyên văn từ nguồn dự phòng; chưa đồng nghĩa với toàn bộ nội dung đã qua Verifier.</p></Card>
    <Card title="(3) Phân loại nguyên nhân"><StatusBadge tone={tone(row.outcome)}>{LABELS[row.outcome] || row.outcome}</StatusBadge><p className="mt-3 text-sm text-slate-500">{row.response_mode === "SOURCE_EXTRACT" ? "Kết quả trích từ nguồn; không coi là model diễn đạt thành công." : "Phân loại dựa trên kết quả cuối của lượt xử lý, không suy đoán từ lượng token."}</p></Card>
    <Card title="(4) Các bước xử lý"><dl><Row label="Tìm bằng chứng">{d.timings?.retrieval_seconds == null ? null : `${d.timings.retrieval_seconds} giây`}</Row><Row label="Tạo/kiểm tra câu trả lời">{d.timings?.answer_seconds == null ? null : `${d.timings.answer_seconds} giây`}</Row><Row label="Toàn lượt">{(row.duration_ms / 1000).toFixed(3)} giây</Row></dl><p className="mt-3 text-xs text-slate-500">Chưa tách phép đo từng bước ý định, Graph, Gate và Verifier. Không gán thời gian 0 cho bước chưa được đo.</p></Card>
    <Card title="(5) Truy xuất dữ liệu & nguồn đã dùng"><dl><Row label="Backend truy xuất">{d.retrieval_backend}</Row><Row label="Đoạn bằng chứng ứng viên">{d.evidence_count == null ? null : number(d.evidence_count)}</Row></dl>
      <div className="mt-4 space-y-3">{(d.sources || []).map((source, i) => <div key={`${source.chunk_id}-${i}`} className="rounded-lg border p-3 text-sm"><p>{source.title || source.source_type || "Nguồn trích dẫn"}</p><p className="mt-1 break-all text-xs text-slate-500">Chunk: {source.chunk_id || "Chưa ghi nhận"}</p>{source.url && <a className="mt-2 inline-block text-blue-600 underline" href={source.url} target="_blank" rel="noreferrer">Mở nguồn gốc</a>}</div>)}{!d.sources?.length && <p className="text-sm text-slate-500">Không có nguồn trích dẫn được ghi cho lượt này.</p>}</div>
    </Card>
    <Card title="(6) Evidence Gate"><StatusBadge>Chưa có phép đo Gate đầy đủ</StatusBadge><p className="mt-3 text-sm text-slate-500">Không suy ra Gate đạt chỉ từ việc tìm thấy đoạn trích hoặc có câu trả lời.</p></Card>
    <Card title="(7) Xác minh câu trả lời (Verifier)"><StatusBadge>Chưa có kết quả Verifier</StatusBadge><p className="mt-3 text-sm text-slate-500">Chưa có tỷ lệ luận điểm được hỗ trợ từ bộ Verifier để hiển thị cho lượt này.</p></Card>
    <Card title="(8) Mức sử dụng tài nguyên & Token"><dl><Row label="Input token đã biết">{number(row.known_input)}</Row><Row label="Output token đã biết">{number(row.known_output)}</Row><Row label="Tổng token đã biết">{number(row.known_total)}</Row><Row label="Lần gọi thiếu số liệu">{row.unknown_calls}</Row></dl>
      {row.calls.map((call, i) => <p key={i} className="mt-3 text-xs text-slate-500">{call.model} · {call.usage ? `${number(call.usage.total_tokens)} token` : "Không xác định token"}</p>)}
      <p className="mt-3 text-xs text-slate-500">Tổng có thể gồm token suy luận. Không gọi model là 0; thiếu usage được ghi riêng.</p>
    </Card>
  </div>;
}

export default function AdminTracesPage() {
  const { traceId } = useParams(), [params] = useSearchParams(), navigate = useNavigate();
  const [filters, setFilters] = useState({ outcome: "", company: "", day: "" }), [offset, setOffset] = useState(0), [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(null), [selected, setSelected] = useState(null), [error, setError] = useState(""), [detailError, setDetailError] = useState("");
  const selectedId = traceId || params.get("trace") || page?.items[0]?.id;
  useEffect(() => {
    const abort = new AbortController();setError("");
    const query = new URLSearchParams({ offset: String(offset), limit: "20" });
    Object.entries(filters).forEach(([k, v]) => { if (v) query.set(k, v); });
    getOperations(`/traces?${query}`, abort.signal).then(data => { if (!abort.signal.aborted) setPage(data); }).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [offset, filters, refresh]);
  useEffect(() => {
    const abort = new AbortController();setSelected(null);setDetailError("");
    if (selectedId) getOperations(`/traces/${encodeURIComponent(selectedId)}`, abort.signal).then(data => { if (!abort.signal.aborted) setSelected(data); }).catch(e => { if (!abort.signal.aborted) setDetailError(e.message); });
    return () => abort.abort();
  }, [selectedId, refresh]);
  const change = (key, value) => { setFilters(f => ({ ...f, [key]: value })); setOffset(0); };
  return <AdminLayout>
    <header className="flex flex-wrap items-center justify-between gap-3"><div><Link className="text-xs text-blue-600" to={ADMIN_LINKS.overview}>Tổng quan vận hành</Link><h1 className="mt-2 text-xl font-bold">Theo dõi truy vấn & Trace</h1><p className="mt-2 text-sm text-slate-500">Dữ liệu Chat thật trên máy này, lưu qua lần khởi động lại. Lượt trước khi bật thống kê không được dựng lại.</p></div><Button variant="secondary" onClick={() => setRefresh(v => v + 1)}>Làm mới</Button></header>
    <section className="flex flex-wrap items-end gap-4 rounded-xl border bg-white p-4">
      <label className="text-sm">Trạng thái<select className="mt-1 block rounded border p-2" value={filters.outcome} onChange={e => change("outcome", e.target.value)}><option value="">Tất cả</option>{Object.entries(LABELS).map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></label>
      <label className="text-sm">Mã công ty<input className="mt-1 block w-36 rounded border p-2" maxLength="15" placeholder="VD: ICT" value={filters.company} onChange={e => change("company", e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} /></label>
      <label className="text-sm">Ngày (Việt Nam)<input type="date" className="mt-1 block rounded border p-2" value={filters.day} onChange={e => change("day", e.target.value)} /></label>
      <Button variant="ghost" onClick={() => { setFilters({ outcome: "", company: "", day: "" });setOffset(0); }}>Xóa lọc</Button>
    </section>
    {error && <ErrorState message={error} onRetry={() => setRefresh(v => v + 1)} />}
    {!page && !error && <Skeleton rows={6} />}
    {page && <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
      <section className="rounded-xl border bg-white p-4"><h2 className="mb-4 font-semibold">Danh sách truy vấn ({page.total})</h2><ul className="space-y-3">{page.items.map(row => <li key={row.id}><button type="button" aria-current={selectedId === row.id ? "true" : undefined} onClick={() => navigate(`${ADMIN_LINKS.traces}/${row.id}`)} className={`w-full rounded-lg border p-3 text-left ${selectedId === row.id ? "border-blue-400 bg-blue-50" : "hover:bg-slate-50"}`}><p className="text-xs text-slate-500">{localTime(row.created_at)} · {row.companies.join(", ") || "Chưa rõ mã"}</p><p className="mt-2 break-all text-xs">{row.id}</p><p className="my-2 line-clamp-2 text-sm">{row.details?.question || "Lượt cũ chưa lưu câu hỏi"}</p><StatusBadge tone={tone(row.outcome)}>{LABELS[row.outcome] || row.outcome}</StatusBadge><p className="mt-2 text-xs">{(row.duration_ms / 1000).toFixed(2)}s · {number(row.known_total)} token đã biết{row.unknown_calls ? " · Có số liệu chưa xác định" : ""}</p></button></li>)}</ul>
        {!page.items.length && <EmptyState title="Không có truy vấn phù hợp" />}
        <div className="mt-4 flex justify-between gap-2"><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Trước</Button><span className="self-center text-xs">Trang {offset / 20 + 1}</span><Button variant="secondary" disabled={offset + 20 >= page.total} onClick={() => setOffset(v => v + 20)}>Sau</Button></div>
      </section>
      <div>{detailError ? <ErrorState message={detailError} onRetry={() => setRefresh(v => v + 1)} /> : selected ? <TraceDetail row={selected} /> : selectedId ? <Skeleton rows={4} /> : <EmptyState title="Chưa chọn truy vấn" />}</div>
    </div>}
  </AdminLayout>;
}
