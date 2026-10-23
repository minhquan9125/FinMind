import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useSearchParams } from "../../app/router.jsx";
import { Drawer } from "../../shared/ui/index.js";
import { createSession, listSessions, getSession, sendMessage, resumeSession } from "./chatApi.js";
import { citationView, modeLabel } from './citationView.js';
import { clarificationChoices } from './clarificationView.js';

const statusLabels = { ASK_CLARIFICATION: "Cần làm rõ", EVIDENCE_READY: "Có bằng chứng mẫu",
  CLARIFICATION_STALLED: 'Cần chọn thông tin cụ thể',
  DRAFT_READY: 'Câu trả lời có nguồn', SOURCE_EXTRACT_FALLBACK: 'Câu trả lời từ nguồn',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ bằng chứng',
  SYSTEM_UNAVAILABLE: 'Lỗi tạm thời', BUDGET_EXCEEDED: 'Đã chạm giới hạn',
  NO_DATA: "Chưa đủ bằng chứng", ERROR: "Lỗi tạm thời", UNSUPPORTED: "Ngoài phạm vi" };
const empty = owner => ({ owner, snapshot: null, history: [], error: null, historyError: null,
  loading: false, historyLoading: false });
const storageKey = owner => `chat_active_${owner}`;
function stored(owner, value) {
  // Session storage is optional convenience; JSON on the backend remains authoritative.
  try {
    if (value === undefined) return sessionStorage.getItem(storageKey(owner));
    if (value === null) sessionStorage.removeItem(storageKey(owner));
    else sessionStorage.setItem(storageKey(owner), value);
  } catch { return null; }
}

export default function ResearchChat({ historyOpen, onHistoryClose, resetKey = 0,
  onHistoryCount, onBusyChange }) {
  const { user, isLoading: authLoading } = useAuth();
  const owner = user?.id || null;
  const [params] = useSearchParams();
  const prefill = params.get("question") || "";
  const [model, setModel] = useState(() => empty(owner));
  const [draft, setDraft] = useState({ owner, text: prefill });
  const generation = useRef(0);
  const busy = useRef(false);
  const previousReset = useRef(resetKey);
  const scroll = useRef(null);
  const view = model.owner === owner ? model : empty(owner);
  const input = draft.owner === owner ? draft.text : "";
  const snapshot = view.snapshot;
  const valid = epoch => generation.current === epoch;
  function adopt(data) {
    setModel(previous => ({ ...previous, snapshot: data }));
    stored(owner, data.session_id);
  }
  async function refreshHistory(epoch) {
    if (!owner || !valid(epoch)) return;
    setModel(previous => ({ ...previous, historyLoading: true, historyError: null }));
    try {
      const data = await listSessions();
      if (!valid(epoch)) return;
      setModel(previous => ({ ...previous, history: data.items, historyLoading: false }));
      onHistoryCount?.(data.items.length);
    } catch (error) {
      if (valid(epoch)) setModel(previous => ({ ...previous, historyError: error, historyLoading: false }));
    }
  }
  async function run(operation, kind = "chat") {
    if (!owner || authLoading || busy.current) return;
    const epoch = generation.current;
    busy.current = true;
    onBusyChange?.(true);
    setModel(previous => ({ ...previous, loading: true, error: null }));
    try { await operation(epoch); }
    catch (error) {
      if (valid(epoch)) setModel(previous => ({ ...previous, error,
        historyError: kind === "history" ? error : previous.historyError }));
    } finally {
      if (valid(epoch)) {
        busy.current = false;
        onBusyChange?.(false);
        setModel(previous => ({ ...previous, loading: false }));
      }
    }
  }
  useEffect(() => {
    const epoch = ++generation.current;
    busy.current = false;
    setModel(empty(owner));
    setDraft({ owner, text: prefill });
    onHistoryCount?.(0);
    onBusyChange?.(false);
    if (owner && !authLoading) {
      const id = stored(owner);
      if (id) {
        busy.current = true;
        onBusyChange?.(true);
        setModel(previous => ({ ...previous, loading: true }));
        getSession(id).then(data => { if (valid(epoch)) adopt(data); })
          .catch(error => {
            if (!valid(epoch)) return;
            if (error.status === 404) stored(owner, null);
            setModel(previous => ({ ...previous, error }));
          }).finally(() => {
            if (!valid(epoch)) return;
            busy.current = false;
            onBusyChange?.(false);
            setModel(previous => ({ ...previous, loading: false }));
          });
      }
      void refreshHistory(epoch);
    }
    return () => { generation.current++; busy.current = false; onBusyChange?.(false); };
  }, [owner, authLoading]);
  useEffect(() => {
    if (previousReset.current === resetKey) return;
    previousReset.current = resetKey;
    generation.current++;
    busy.current = false;
    if (owner) stored(owner, null);
    setModel(previous => ({ ...empty(owner), history: previous.owner === owner ? previous.history : [] }));
    setDraft({ owner, text: prefill });
    onBusyChange?.(false);
  }, [resetKey]);
  useEffect(() => { if (historyOpen && owner) void refreshHistory(generation.current); }, [historyOpen, owner]);
  useEffect(() => { if (scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight; }, [snapshot?.messages.length, view.loading, view.error]);
  useEffect(() => { if (prefill) setDraft({ owner, text: prefill }); }, [prefill]);

  function submit(event) {
    event.preventDefault();
    submitText(input.trim());
  }
  function submitText(text) {
    if (!text) return;
    void run(async epoch => {
      let current = snapshot;
      if (!current) {
        current = await createSession();
        if (!valid(epoch)) return;
        adopt(current); // Preserve the new ID even if the following send fails.
      }
      const next = await sendMessage(current.session_id, text, current.revision);
      if (!valid(epoch)) return;
      adopt(next);
      setDraft({ owner, text: "" });
      void refreshHistory(epoch); // A list failure must never turn a saved message into a send failure.
    });
  }
  function resume(id) {
    void run(async epoch => {
      const next = await resumeSession(id);
      if (!valid(epoch)) return;
      adopt(next);
      setDraft({ owner, text: "" });
      onHistoryClose?.();
      void refreshHistory(epoch);
    }, "history");
  }
  function reload() {
    if (!snapshot) return;
    void run(async epoch => {
      const next = await getSession(snapshot.session_id);
      if (valid(epoch)) adopt(next);
    });
  }
  if (authLoading) return <p role="status">Đang kiểm tra phiên đăng nhập...</p>;
  if (!owner) return <p>Vui lòng <a href="/login" className="text-blue-600 underline">đăng nhập</a> để bắt đầu hội thoại.</p>;
  return <section aria-label="Hội thoại nghiên cứu" className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <div className="shrink-0 border-b border-slate-100 px-4 py-3">
      <p className="text-xs text-amber-800">{modeLabel(snapshot)}</p>
      <p className="mt-1 whitespace-pre-wrap break-words text-sm text-slate-600">{snapshot?.context || "Nhập câu hỏi để bắt đầu. Bạn có thể bổ sung mã, kỳ hoặc chỉ tiêu ở lượt sau."}</p>
    </div>
    <div ref={scroll} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4" role="log" aria-label="Các lượt hỏi đáp" aria-live="polite">
      {!snapshot?.messages.length && !view.loading && <p className="py-8 text-center text-sm text-slate-500">Bạn muốn tra cứu điều gì?</p>}
      {(snapshot?.messages || []).map((message, index) => <div key={`${index}-${message.timestamp}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
        <div className={`min-w-0 max-w-[92%] rounded-xl px-4 py-3 sm:max-w-[85%] ${message.role === "user" ? "bg-blue-600 text-white" : "border border-slate-200 bg-slate-50 text-slate-900"}`}>
          <p className={`mb-1 text-xs font-semibold ${message.role === "user" ? "text-blue-100" : "text-blue-700"}`}>{message.role === "user" ? "Bạn" : message.result?.scope?.source_type === 'PRICE' ? 'Giá cổ phiếu' : message.result?.answering?.manifest?.response_mode === 'NEWS_LIST' ? 'Tin tức' : message.result?.execution_mode === 'LIVE' && message.result?.status === 'EVIDENCE_READY' && message.result?.answering?.status !== 'DRAFT_READY' ? 'Nguồn ứng viên' : statusLabels[message.result?.answering?.status] || statusLabels[message.result?.status] || "FinMind"}</p>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{message.content}</p>
          {clarificationChoices(message.result).length > 0 && <div className="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Lựa chọn làm rõ câu hỏi">
            {clarificationChoices(message.result).map(option => <button key={option.id} type="button"
              disabled={view.loading || index !== snapshot.messages.length - 1}
              onClick={() => submitText(option.reply)}
              className="min-h-11 rounded-lg border border-blue-200 bg-white px-3 py-2 text-left text-sm text-blue-900 hover:bg-blue-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 disabled:cursor-default disabled:opacity-50">
              <span className="block font-medium">{option.id}. {option.label}</span>
              {option.description && <span className="mt-1 block text-xs text-slate-600">{option.description}</span>}
            </button>)}
          </div>}
          {citationView(message.result).length > 0 && <div className="mt-3 space-y-2 border-t border-slate-200 pt-3" aria-label="Nguồn của phản hồi">
            <p className="text-xs font-semibold text-slate-600">{citationView(message.result).every(source => source.compact) ? 'Bài viết' : 'Mở nguồn để xem đoạn trích và vị trí dữ liệu'}</p>
            {citationView(message.result).map(source => source.compact ? source.url && <a key={source.id} href={source.url}
              target="_blank" rel="noopener noreferrer" className="flex min-h-11 items-center break-words text-sm text-blue-700 underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
              {source.citationNumber ? `[${source.citationNumber}] ` : ''}{source.title}
            </a> : <details key={source.id} className="rounded-lg border border-slate-200 bg-white p-3">
              <summary className="min-h-11 cursor-pointer break-words text-sm font-medium text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500">
                {source.citationNumber ? `[${source.citationNumber}] ` : ''}{source.used ? 'Đã trích dẫn' : 'Nguồn ứng viên'} · {source.title}
              </summary>
              <p className="mt-2 text-xs text-slate-600">{source.location}</p>
              <blockquote className="mt-2 whitespace-pre-wrap break-words border-l-2 border-blue-200 pl-3 text-sm leading-relaxed">{source.passage}</blockquote>
              {source.rows.length > 0 && <p className="mt-2 break-all text-xs text-slate-500">Vị trí dòng dữ liệu: {source.rows.join(', ')}</p>}
              {source.url && <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex min-h-11 items-center text-sm text-blue-700 underline">Mở bài gốc</a>}
            </details>)}
          </div>}
        </div>
      </div>)}
      {view.loading && <p role="status" className="text-sm text-slate-500">Đang xử lý… Lần tìm kiếm đầu tiên có thể cần thêm thời gian để nạp mô hình.</p>}
      {view.error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        <p>{view.error.message}</p>
        {view.error.status === 401 && <a href="/login" className="underline">Đăng nhập lại</a>}
        {snapshot && <button type="button" disabled={view.loading} onClick={reload} className="mt-2 min-h-11 underline disabled:opacity-50">Tải lại phiên</button>}
      </div>}
    </div>
    <form onSubmit={submit} className="shrink-0 border-t border-slate-200 p-3 sm:p-4">
      <label htmlFor="research-chat-input" className="mb-1 block text-xs font-semibold text-slate-600">Câu hỏi</label>
      <div className="flex gap-2">
        <input id="research-chat-input" maxLength={4000} value={input} onChange={event => setDraft({ owner, text: event.target.value })}
          disabled={view.loading} placeholder="Nhập câu hỏi hoặc bổ sung thông tin..." autoComplete="off"
          className="h-11 min-w-0 flex-1 rounded-lg border border-slate-200 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100" />
        <button type="submit" disabled={view.loading || !input.trim()} className="h-11 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 disabled:opacity-40">Gửi</button>
      </div>
      <p className="mt-2 text-center text-xs text-slate-400">Chỉ hỗ trợ nghiên cứu · Không phải khuyến nghị đầu tư</p>
    </form>
    <Drawer open={historyOpen} title="Lịch sử hội thoại" onClose={onHistoryClose}>
      <div className="space-y-3">
        {view.historyLoading && <p role="status">Đang tải lịch sử...</p>}
        {view.historyError && <p role="alert" className="text-red-700">{view.historyError.message}</p>}
        <button type="button" disabled={view.loading || view.historyLoading} onClick={() => void refreshHistory(generation.current)} className="min-h-11 text-blue-600 underline disabled:opacity-50">Tải lại lịch sử</button>
        {!view.history.length && !view.historyLoading && <p>Chưa có hội thoại nào.</p>}
        {view.history.map(item => <article key={item.session_id} className="rounded-lg border border-slate-200 p-3">
          <p className="break-words font-medium">{item.preview || "Phiên chưa có câu hỏi"}</p>
          <p className="mt-1 text-xs text-slate-500">{item.turns} lượt · {new Date(item.saved_at).toLocaleString("vi-VN")}</p>
          <button type="button" disabled={view.loading} onClick={() => resume(item.session_id)} className="mt-2 min-h-11 text-blue-600 underline disabled:opacity-50">Mở và tiếp tục</button>
        </article>)}
      </div>
    </Drawer>
  </section>;
}
