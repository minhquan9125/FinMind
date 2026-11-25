// Trang Đánh giá chất lượng (route /admin/evaluation).
// Chạy bộ câu hỏi chuẩn qua Chat thật, chấm tự động theo số liệu và lưu kết quả để so sánh các lần chạy.
// Điểm chỉ hỗ trợ người kiểm tra; không thay cho việc xem lại câu trả lời.

import { useEffect, useMemo, useState } from "react";
import { Link } from "../../app/router.jsx";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import { authorizedHeaders } from "../../shared/api/authorization.js";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { getOperations, localTime } from "./operationsApi.js";
import { canStart, categories, estimateNote, evaluationErrorMessage, filterQuestions, levelView, passRate, percent, progress, runStatusLabel, runSummaryText } from "./evaluationView.js";

async function send(path, method, body) {
  const response = await fetch(`/api/v1/admin/ingestion/evaluation${path}`, {
    method, headers: authorizedHeaders(body === undefined ? {} : { "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  let data = null;
  try { data = await response.json(); } catch { /* errors may have no body */ }
  if (!response.ok) throw new Error(evaluationErrorMessage(data?.detail, response.status));
  return data;
}

function RunDetail({ run }) {
  const s = run.summary || {};
  const rows = run.results || [];
  return <div className="space-y-4">
    <div className="grid gap-3 sm:grid-cols-4">
      {[["Đạt", percent(passRate(s))], ["Điểm trung bình", s.mean_score == null ? "—" : s.mean_score.toLocaleString("vi-VN", { maximumFractionDigits: 2 })],
        ["Thời gian/câu", s.mean_latency_ms == null ? "—" : `${(s.mean_latency_ms / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} giây`],
        ["Có nguồn", s.total ? `${s.with_sources}/${s.total}` : "—"]].map(([label, value]) =>
        <div key={label} className="rounded-xl border bg-white p-4"><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-xl font-semibold tabular-nums">{value}</p></div>)}
    </div>
    <div className="flex flex-wrap gap-2 text-sm">{Object.entries(s.levels || {}).map(([level, count]) =>
      <StatusBadge key={level} tone={levelView(level).tone}>{levelView(level).label}: {count}</StatusBadge>)}</div>
    {!rows.length ? <EmptyState title="Chưa có kết quả" description="Kết quả hiện ra từng câu khi lần chạy tiến hành." /> :
      <div className="space-y-2">{rows.map(row => { const level = levelView(row.level); return <details key={row.qid} className="rounded-xl border bg-white p-3">
        <summary className="flex cursor-pointer flex-wrap items-center gap-3 text-sm">
          <span className="font-mono text-xs">{row.qid}</span><StatusBadge tone={level.tone}>{level.label}</StatusBadge>
          {row.score != null && <span className="tabular-nums text-xs text-slate-500">{row.matched}/{row.total} ý khớp</span>}
          <span className="min-w-0 flex-1 truncate">{row.question}</span>
          <span className="text-xs text-slate-400">{row.latency_ms != null ? `${(row.latency_ms / 1000).toFixed(1)}s` : ""}</span>
        </summary>
        <div className="mt-3 space-y-3 text-sm">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-lg bg-emerald-50 p-3"><p className="text-xs font-semibold text-emerald-800">Đáp án chuẩn {row.verified ? "(đã đối chiếu nguồn)" : "(chưa được duyệt)"}</p><p className="mt-1 whitespace-pre-wrap break-words">{row.expected}</p></div>
            <div className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold text-slate-600">Chat trả lời{row.status ? ` · ${row.status}` : ""}{row.route ? ` · ${row.route}` : ""}{row.citations ? ` · ${row.citations} trích dẫn` : ""}</p><p className="mt-1 whitespace-pre-wrap break-words">{row.answer || (row.error ? `Lỗi: ${row.error}` : "Không có nội dung")}</p></div>
          </div>
          {row.facts?.length > 0 && <ul className="flex flex-wrap gap-2">{row.facts.map((fact, i) => <li key={i} className={`rounded-full border px-3 py-1 text-xs ${fact.matched ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-red-200 bg-red-50 text-red-800"}`}>{fact.matched ? "✓" : "✗"} {fact.text}</li>)}</ul>}
          {row.level === "MANUAL" && <p className="text-xs text-slate-500">Đáp án chuẩn không có số liệu hay ngày để so tự động. Cần người đọc và đánh giá.</p>}
        </div></details>; })}</div>}
  </div>;
}

export default function AdminEvaluationPage() {
  const [questions, setQuestions] = useState(null), [runs, setRuns] = useState([]), [selectedRun, setSelectedRun] = useState(null), [runId, setRunId] = useState(null);
  const [picked, setPicked] = useState([]), [filters, setFilters] = useState({ category: "", verifiedOnly: false, text: "" });
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [retry, setRetry] = useState(0);

  useEffect(() => {
    const abort = new AbortController(); setError("");
    Promise.all([getOperations("/evaluation/questions", abort.signal), getOperations("/evaluation/runs", abort.signal)])
      .then(([q, r]) => { if (!abort.signal.aborted) { setQuestions(q); setRuns(r.items); setRunId(id => id || r.items[0]?.id || null); } })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [retry]);

  const active = runs.find(run => run.status === "RUNNING");
  useEffect(() => {
    if (!runId) { setSelectedRun(null); return undefined; }
    let stopped = false;
    const load = async () => {
      try {
        const [detail, list] = await Promise.all([getOperations(`/evaluation/runs/${runId}`), getOperations("/evaluation/runs")]);
        if (!stopped) { setSelectedRun(detail); setRuns(list.items); }
      } catch (e) { if (!stopped) setError(e.message); }
    };
    load();
    const timer = active ? setInterval(load, 4000) : null;
    return () => { stopped = true; if (timer) clearInterval(timer); };
  }, [runId, active?.id, retry]);

  const items = questions?.items || [];
  const visible = useMemo(() => filterQuestions(items, filters), [items, filters]);
  const toggle = id => setPicked(list => list.includes(id) ? list.filter(x => x !== id) : [...list, id]);

  async function start() {
    if (!window.confirm(estimateNote(picked.length))) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await send("/runs", "POST", { question_ids: picked });
      setMessage(`Đã bắt đầu chạy ${result.total} câu. Kết quả hiện dần bên dưới.`); setRunId(result.run_id); setPicked([]); setRetry(v => v + 1);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  async function stop(id) {
    setBusy(true); setError("");
    try { await send(`/runs/${id}/interrupt`, "POST"); setRetry(v => v + 1); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <AdminLayout>
    <header className="space-y-1">
      <Link className="text-xs text-blue-600" to={ADMIN_LINKS.overview}>Tổng quan vận hành</Link>
      <h1 className="text-xl font-bold">Đánh giá chất lượng Chat</h1>
      <p className="text-sm text-slate-500">Chạy bộ câu hỏi chuẩn qua Chat thật và chấm tự động theo số liệu, ngày và mã trong đáp án chuẩn. Điểm chỉ để xem nhanh, không thay cho việc đọc câu trả lời; câu không có số liệu để so được đánh dấu "Cần người xem".</p>
    </header>
    {error && <ErrorState message={error} onRetry={() => setRetry(v => v + 1)} />}
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">{message}</p>}
    {!questions && !error && <Skeleton rows={6} />}
    {questions && !questions.available && <EmptyState title="Chưa có bộ câu hỏi chuẩn" description="Không tìm thấy file bộ câu hỏi chuẩn ở thư mục gốc dự án." />}
    {questions?.available && <Card title={`Chọn câu hỏi (${picked.length}/${items.length})`}
      description="Mỗi câu là một lượt Chat thật và tính vào hạn mức Gemini. Nên chạy vài câu trước."
      action={<Button disabled={busy || !canStart(picked, runs)} onClick={start}>{active ? "Đang có lần chạy khác" : `Chạy ${picked.length} câu`}</Button>}>
      <div className="mb-3 flex flex-wrap items-end gap-3 text-sm">
        <label>Nhóm<select className="mt-1 block rounded border p-2" value={filters.category} onChange={e => setFilters(f => ({ ...f, category: e.target.value }))}><option value="">Tất cả</option>{categories(items).map(c => <option key={c} value={c}>{c}</option>)}</select></label>
        <label>Tìm<input className="mt-1 block rounded border p-2" placeholder="Mã hoặc từ khóa" value={filters.text} onChange={e => setFilters(f => ({ ...f, text: e.target.value }))} /></label>
        <label className="flex gap-2 pb-2"><input type="checkbox" checked={filters.verifiedOnly} onChange={e => setFilters(f => ({ ...f, verifiedOnly: e.target.checked }))} />Chỉ câu đã đối chiếu nguồn</label>
        <Button variant="secondary" onClick={() => setPicked(items.filter(i => i.verified).slice(0, 5).map(i => i.id))}>Chọn thử 5 câu</Button>
        <Button variant="secondary" onClick={() => setPicked(visible.map(i => i.id))}>Chọn các câu đang hiện ({visible.length})</Button>
        <Button variant="ghost" disabled={!picked.length} onClick={() => setPicked([])}>Bỏ chọn</Button>
      </div>
      <ul className="max-h-80 space-y-1 overflow-y-auto rounded-lg border p-2">{visible.map(item => <li key={item.id}>
        <label className="flex cursor-pointer items-start gap-3 rounded p-2 text-sm hover:bg-slate-50"><input type="checkbox" className="mt-1" checked={picked.includes(item.id)} onChange={() => toggle(item.id)} />
          <span className="font-mono text-xs text-slate-500">{item.id}</span><span className="min-w-0 flex-1">{item.question}</span>
          {item.verified ? <StatusBadge tone="success">Đã đối chiếu</StatusBadge> : <StatusBadge>Chưa duyệt</StatusBadge>}</label></li>)}
        {!visible.length && <li className="p-3 text-sm text-slate-500">Không có câu hỏi phù hợp bộ lọc.</li>}</ul>
    </Card>}
    {questions?.available && <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
      <section className="rounded-xl border bg-white p-4"><h2 className="mb-3 font-semibold">Các lần chạy ({runs.length})</h2>
        {!runs.length ? <p className="text-sm text-slate-500">Chưa có lần chạy nào.</p> : <ul className="space-y-2">{runs.map(run => <li key={run.id}>
          <button type="button" onClick={() => setRunId(run.id)} aria-current={runId === run.id ? "true" : undefined} className={`w-full rounded-lg border p-3 text-left text-sm hover:bg-slate-50 ${runId === run.id ? "border-blue-500 bg-blue-50" : ""}`}>
            <span className="flex items-center justify-between gap-2"><span>{localTime(run.created_at)}</span><StatusBadge tone={run.status === "RUNNING" ? "warning" : run.status === "COMPLETED" ? "success" : "neutral"}>{runStatusLabel(run.status)}</StatusBadge></span>
            <span className="mt-1 block text-slate-600">{run.status === "RUNNING" ? `${run.done}/${run.total} câu` : runSummaryText(run)}</span>
            {run.status === "RUNNING" && <progress className="mt-2 w-full" max="100" value={progress(run)} />}
          </button></li>)}</ul>}
      </section>
      <div className="space-y-3">{selectedRun ? <>
        <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Lần chạy {localTime(selectedRun.created_at)}</h2><p className="text-xs text-slate-500">{runStatusLabel(selectedRun.status)} · {selectedRun.done}/{selectedRun.total} câu</p></div>
          {selectedRun.status === "RUNNING" && <Button variant="secondary" disabled={busy} onClick={() => stop(selectedRun.id)}>Dừng lần chạy</Button>}</div>
        <RunDetail run={selectedRun} /></> : <EmptyState title="Chưa chọn lần chạy" description="Chọn câu hỏi rồi bấm Chạy, hoặc chọn một lần chạy ở bên trái." />}</div>
    </div>}
  </AdminLayout>;
}
