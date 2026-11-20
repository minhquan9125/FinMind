// Giới hạn trả lời của Chat (sửa được, có phiên bản) và trạng thái xoay khóa Gemini (chỉ đọc).
import { useEffect, useState } from "react";
import { Button, Card, ErrorState, Skeleton, StatusBadge } from "../../shared/ui";
import { authorizedHeaders } from "../../shared/api/authorization.js";
import { getOperations, localTime } from "./operationsApi.js";
import { LIMIT_FIELDS, addResultNote, draftFrom, envKeyView, isUnchanged, keyErrorMessage, keyStatusView, limitsErrorMessage, managedKeyView, overridesFrom, testResultLabel, validateDraft, validateKeyForm } from "./limitsForm.js";

async function saveLimits(body) {
  const response = await fetch("/api/v1/admin/ingestion/limits", {
    method: "PUT", headers: authorizedHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(body), cache: "no-store",
  });
  let data = null;
  try { data = await response.json(); } catch { /* errors may have no body */ }
  if (!response.ok) throw new Error(limitsErrorMessage(data?.detail, response.status));
  return data;
}

async function keyRequest(method, path, body) {
  const response = await fetch(`/api/v1/admin/ingestion/gemini-keys${path}`, {
    method, headers: authorizedHeaders(body === undefined ? {} : { "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store",
  });
  let data = null;
  try { data = await response.json(); } catch { /* errors may have no body */ }
  if (!response.ok) throw new Error(keyErrorMessage(data?.detail, response.status));
  return data;
}

function LimitsEditor() {
  const [view, setView] = useState(null), [draft, setDraft] = useState(null), [reason, setReason] = useState("");
  const [error, setError] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false), [reload, setReload] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setError("");
    getOperations("/limits", abort.signal).then(result => { if (!abort.signal.aborted) { setView(result); setDraft(draftFrom(result.effective)); } })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [reload]);
  if (error && !view) return <ErrorState message={error} onRetry={() => setReload(v => v + 1)} />;
  if (!view || !draft) return <Skeleton rows={4} />;
  const errors = validateDraft(draft, view.bounds);
  const overrides = overridesFrom(draft, view.defaults);
  const unchanged = isUnchanged(overrides, view.overrides);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await saveLimits({ values: overrides, reason, expected_version: view.version });
      setView(result); setDraft(draftFrom(result.effective)); setReason("");
      setMessage("Đã lưu phiên bản mới. Áp dụng từ câu hỏi kế tiếp, không cần khởi động lại.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="space-y-4">
    <p className="text-sm text-slate-600">Giá trị mặc định lấy từ cấu hình dự án. Chỉ các giá trị bạn đổi mới được lưu như ghi đè, và có thể quay về mặc định bất cứ lúc nào.
      Model ({view.locked.model}) và chi phí tối đa ({view.locked.max_cost_usd} USD, khóa free tier) không sửa được ở đây.</p>
    <div className="grid gap-4 md:grid-cols-2">{LIMIT_FIELDS.map(({ key, label, hint }) => <label key={key} className="text-sm">{label}
      <input inputMode="numeric" className={`mt-1 block w-full rounded border p-2 ${errors[key] ? "border-red-400" : ""}`} value={draft[key]} disabled={busy}
        onChange={e => setDraft(d => ({ ...d, [key]: e.target.value }))} aria-invalid={!!errors[key]} />
      <span className="mt-1 block text-xs text-slate-500">{errors[key] || `${hint}. Mặc định ${view.defaults[key].toLocaleString("vi-VN")}.`}</span>
      {errors[key] && <span className="sr-only">{errors[key]}</span>}</label>)}</div>
    <label className="block text-sm">Lý do thay đổi<textarea required minLength="3" maxLength="500" className="mt-1 block w-full rounded border p-3" value={reason} disabled={busy} onChange={e => setReason(e.target.value)} /></label>
    {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">{message}</p>}
    <div className="flex flex-wrap gap-3">
      <Button type="submit" disabled={busy || unchanged || Object.keys(errors).length > 0 || reason.trim().length < 3}>Lưu phiên bản & áp dụng</Button>
      <Button variant="ghost" disabled={busy || !Object.keys(view.overrides).length} onClick={() => setDraft(draftFrom(view.defaults))}>Điền lại giá trị mặc định</Button>
      <Button variant="ghost" disabled={busy} onClick={() => setReload(v => v + 1)}>Tải lại</Button>
    </div>
    <div className="space-y-2">{view.history.map((item, index) => <details key={item.id} className="rounded-lg border p-3">
      <summary className="cursor-pointer text-sm">{localTime(item.created_at)} · {index === 0 ? "Đang áp dụng" : "Đã thay thế"} · {Object.keys(item.values).length ? `${Object.keys(item.values).length} giá trị ghi đè` : "Về mặc định"}</summary>
      <p className="mt-2 break-all text-xs text-slate-500">{item.id} · {item.actor}</p><p className="mt-2 text-sm">{item.reason}</p>
      <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(item.values, null, 2)}</pre></details>)}
      {!view.history.length && <p className="text-sm text-slate-500">Chưa có phiên bản ghi đè nào, đang dùng giá trị mặc định.</p>}</div>
  </form>;
}

function ManagedKeys({ data, onChanged }) {
  const [form, setForm] = useState({ label: "", key: "" }), [busy, setBusy] = useState(false), [note, setNote] = useState(null);
  const errors = validateKeyForm(form);
  const filled = form.label.trim() && form.key.trim();
  async function act(work) {
    setBusy(true); setNote(null);
    try { await work(); onChanged(); }
    catch (e) { setNote({ ok: false, text: e.message }); }
    finally { setBusy(false); }
  }
  const add = event => {
    event.preventDefault();
    act(async () => {
      const result = await keyRequest("POST", "", { label: form.label.trim(), key: form.key.trim() });
      setForm({ label: "", key: "" });                    // the key leaves the page as soon as it is sent
      setNote({ ok: true, text: addResultNote(result) });
    });
  };
  if (!data.store.usable) return <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Chưa bật kho khóa trên trang web: đặt GEMINI_KEYS_SECRET (ít nhất 16 ký tự ngẫu nhiên) trong backend/.env rồi khởi động lại backend. Khóa vẫn thêm được qua GEMINI_API_KEYS trong .env.</p>;
  return <div className="space-y-4">
    <h3 className="text-sm font-semibold">Khóa thêm từ trang này</h3>
    {data.managed.length ? <ul className="space-y-2">{data.managed.map(item => { const view = managedKeyView(item); return <li key={view.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
      <span><span className="font-medium">{view.name}</span> <span className="font-mono text-xs text-slate-500">{view.tail}</span></span>
      <span className="flex flex-wrap items-center gap-2"><StatusBadge tone={view.tone}>{view.label}</StatusBadge>
        <Button variant="ghost" disabled={busy || !item.readable} onClick={() => act(async () => { const r = await keyRequest("POST", `/${view.id}/test`); setNote({ ok: r.result === "OK" || r.result === "QUOTA", text: `${view.name}: ${testResultLabel(r.result)}` }); })}>Thử</Button>
        <Button variant="ghost" disabled={busy} onClick={() => act(() => keyRequest("PATCH", `/${view.id}`, { enabled: !item.enabled }))}>{item.enabled ? "Tắt" : "Bật"}</Button>
        <Button variant="ghost" disabled={busy} onClick={() => { if (window.confirm(`Xóa khóa "${view.name}"? Khóa sẽ bị bỏ khỏi vòng xoay và xóa khỏi kho.`)) act(() => keyRequest("DELETE", `/${view.id}`)); }}>Xóa</Button></span></li>; })}</ul>
      : <p className="text-sm text-slate-500">Chưa có khóa nào được thêm từ trang này.</p>}
    <form onSubmit={add} className="space-y-3 rounded-lg border p-4" autoComplete="off">
      <p className="text-sm font-medium">Thêm khóa mới</p>
      <div className="grid gap-3 md:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
        <label className="text-sm">Tên gợi nhớ<input className="mt-1 block w-full rounded border p-2" maxLength="60" value={form.label} disabled={busy} autoComplete="off" onChange={e => setForm(f => ({ ...f, label: e.target.value }))} placeholder="VD: Khóa của Huyền" /></label>
        <label className="text-sm">Khóa API (chỉ ghi, không hiển thị lại)<input type="password" className="mt-1 block w-full rounded border p-2 font-mono" value={form.key} disabled={busy} autoComplete="new-password" spellCheck="false" onChange={e => setForm(f => ({ ...f, key: e.target.value }))} placeholder="AIza..." /></label>
      </div>
      {filled && (errors.key || errors.label) && <p className="text-xs text-red-700">{errors.label || errors.key}</p>}
      <p className="text-xs text-slate-500">Khóa được kiểm tra với Google (không sinh nội dung) rồi lưu mã hóa trên máy chạy backend, và chỉ hiện lại 4 ký tự cuối. Chỉ thêm khóa mà nhóm được phép dùng.</p>
      <Button type="submit" disabled={busy || !filled || Object.keys(errors).length > 0}>Kiểm tra & thêm khóa</Button>
    </form>
    {note && <p role={note.ok ? "status" : "alert"} className={`rounded-lg border p-3 text-sm ${note.ok ? "border-blue-200 bg-blue-50 text-blue-900" : "border-red-200 bg-red-50 text-red-800"}`}>{note.text}</p>}
  </div>;
}

function EnvKeys({ items, onChanged }) {
  const [busy, setBusy] = useState(false), [note, setNote] = useState(null);
  async function toggle(item) {
    setBusy(true); setNote(null);
    try { await keyRequest("PATCH", `/env/${item.id}`, { enabled: !item.enabled }); onChanged(); }
    catch (e) { setNote(e.message); }
    finally { setBusy(false); }
  }
  if (!items?.length) return null;
  return <div className="space-y-3">
    <h3 className="text-sm font-semibold">Khóa trong backend/.env</h3>
    <p className="text-xs text-slate-500">Tắt để chat thôi dùng khóa này ngay ở câu hỏi kế tiếp, không cần sửa file hay khởi động lại. Khóa vẫn nằm trong .env; bật lại bất cứ lúc nào.</p>
    <ul className="space-y-2">{items.map(item => { const view = envKeyView(item); return <li key={view.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
      <span><span className="font-medium">{view.name}</span> <span className="font-mono text-xs text-slate-500">{view.tail}</span></span>
      <span className="flex flex-wrap items-center gap-2"><StatusBadge tone={view.tone}>{view.label}</StatusBadge>
        <Button variant="ghost" disabled={busy} onClick={() => toggle(item)}>{item.enabled ? "Tắt" : "Bật"}</Button></span></li>; })}</ul>
    {note && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{note}</p>}
  </div>;
}

function GeminiKeys() {
  const [data, setData] = useState(null), [error, setError] = useState(""), [reload, setReload] = useState(0);
  useEffect(() => {
    const abort = new AbortController(); setError("");
    getOperations("/gemini-keys", abort.signal).then(result => { if (!abort.signal.aborted) setData(result); })
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [reload]);
  if (error) return <ErrorState message={error} onRetry={() => setReload(v => v + 1)} />;
  if (!data) return <Skeleton rows={2} />;
  return <div className="space-y-5">
    {data.configured ? <div className="space-y-3">
      <p className="text-sm text-slate-600">{data.keys.length} khóa đang xoay vòng. Khi một khóa hết hạn mức hoặc bị từ chối, hệ thống tự chuyển sang khóa kế tiếp trong cùng câu hỏi và tạm nghỉ khóa đó. Khóa không bao giờ hiển thị ở đây.</p>
      <ul className="space-y-2">{data.keys.map(item => { const view = keyStatusView(item); return <li key={view.name} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
        <span><span className="font-medium">{view.name}</span>{item.label && <span className="ml-2 text-slate-600">{item.label}</span>}<span className="ml-2 text-xs text-slate-400">{item.source === "web" ? "thêm từ trang web" : "từ .env"}</span></span>
        <StatusBadge tone={view.tone}>{view.label}</StatusBadge></li>; })}</ul>
      <Button variant="ghost" onClick={() => setReload(v => v + 1)}>Làm mới trạng thái</Button>
    </div> : <p className="text-sm text-slate-600">Chat chưa dùng Gemini (chưa có khóa hoặc chưa xác nhận free tier). Thêm khóa đầu tiên bên dưới rồi khởi động lại backend một lần.</p>}
    <EnvKeys items={data.env} onChanged={() => setReload(v => v + 1)} />
    <ManagedKeys data={data} onChanged={() => setReload(v => v + 1)} />
  </div>;
}

export default function AdminLimitsPanel() {
  return <div className="space-y-5">
    <Card title="Giới hạn trả lời của Chat" description="Token, số lần gọi model và thời gian chờ. Sửa được, có lịch sử phiên bản."><LimitsEditor /></Card>
    <Card title="Xoay khóa Gemini" description="Trạng thái các khóa API của nhóm dùng cho Chat."><GeminiKeys /></Card>
  </div>;
}
