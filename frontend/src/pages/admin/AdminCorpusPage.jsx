// Trang A03: Phiên bản kho dữ liệu (route /admin/corpus và /admin/corpus/:version).
// Mở manifest bằng :version hoặc ?corpus=; ?tab=registry mở thẳng Sổ đăng ký tài liệu.
// Dữ liệu minh họa lấy từ ./corpusMock.js; mọi thay đổi (kích hoạt, lưu trữ, freeze) chỉ lưu trong bộ nhớ trang.

import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "../../app/router.jsx";
import { Button, Card, Drawer, EmptyState, ErrorState, FilterBar, Modal, Select, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { CANDIDATE_DOC_IDS, getCorpusData } from "./corpusMock.js";
import useToasts from "./useToasts.jsx";

// ─── Hằng số & hàm thuần ────────────────────────────────────────────────────

const STATUS_TONE = {
  "Đang hoạt động": "success", "Chưa kích hoạt": "warning", "Đang chuẩn bị": "info",
  "Đã lưu trữ": "neutral", "Kiểm tra không đạt": "error",
};
const validationTone = (v) => (v === "Đã xác thực" ? "success" : v === "Không đạt kiểm tra integrity" ? "error" : "warning");

const EMPTY_FILTERS = { q: "", company: "all", period: "all", source: "all", type: "all", validation: "all", corpus: "all" };
const NO_DATA = "Chưa có dữ liệu";

const unique = (list, pick) => Array.from(new Set(list.map(pick)));
const options = (labelAll, values, label = (v) => v) => [{ value: "all", label: labelAll }, ...values.map((v) => ({ value: v, label: label(v) }))];

const parseVersion = (v) => { const m = /^v(\d+)\.(\d+)$/.exec(v); return m ? [Number(m[1]), Number(m[2])] : [0, 0]; };
const compareVersions = (a, b) => { const [a1, a2] = parseVersion(a); const [b1, b2] = parseVersion(b); return a1 - b1 || a2 - b2; };
const nextVersion = (corpora) => {
  const latest = corpora.map((c) => c.v).sort(compareVersions).at(-1);
  const [major, minor] = parseVersion(latest);
  return `v${major}.${minor + 1}`;
};
const todayLabel = () => new Date().toLocaleDateString("en-GB"); // dd/mm/yyyy

const docRef = (d) => `DOC-DEMO-${d.id}`;
const belongsTo = (corpora, docId) => {
  const versions = corpora.filter((c) => c.docs.includes(docId)).map((c) => c.v);
  return versions.length ? `Corpus ${versions.join(", ")}` : "Chưa thuộc corpus nào";
};

function filterDocuments(docs, corpora, f) {
  const q = f.q.trim().toLowerCase();
  const corpus = f.corpus === "all" ? null : corpora.find((c) => c.v === f.corpus);
  return docs.filter((d) =>
    (!q || [d.name, d.id, d.co].some((v) => v.toLowerCase().includes(q))) &&
    (f.company === "all" || d.co === f.company) &&
    (f.period === "all" || d.period === f.period) &&
    (f.source === "all" || d.source === f.source) &&
    (f.type === "all" || d.type === f.type) &&
    (f.validation === "all" || d.validation === f.validation) &&
    (f.corpus === "all" || Boolean(corpus?.docs.includes(d.id))));
}

function wizardIssues(selectedDocs) {
  const count = (issue) => selectedDocs.filter((d) => d.issue === issue).length;
  const issues = { pubDate: count("pubDate"), scope: count("scope"), hash: count("hash") };
  return { ...issues, total: issues.pubDate + issues.scope + issues.hash };
}

function compareCorpora(a, b, docs) {
  const byId = (id) => docs.find((d) => d.id === id);
  const label = (id) => { const d = byId(id); return d ? `${d.name} (${d.ver})` : id; };
  const sources = (c) => new Set(c.docs.map(byId).filter(Boolean).map((d) => `${d.source} ${d.srcVer}`));
  const sa = sources(a); const sb = sources(b);
  return {
    added: b.docs.filter((id) => !a.docs.includes(id)).map(label),
    removed: a.docs.filter((id) => !b.docs.includes(id)).map(label),
    addedSources: [...sb].filter((s) => !sa.has(s)),
    removedSources: [...sa].filter((s) => !sb.has(s)),
    period: a.period !== b.period ? `${a.period} → ${b.period}` : null,
  };
}

// ─── Thành phần nhỏ ─────────────────────────────────────────────────────────

function InfoRows({ rows }) {
  return (
    <div className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-slate-50 px-4 text-xs">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-3 py-2.5">
          <span className="text-slate-500">{label}</span>
          <span className="text-right font-medium text-slate-900">{value}</span>
        </div>
      ))}
    </div>
  );
}

function Heading({ children }) {
  return <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">{children}</h3>;
}

function HashCell({ hash, onCopy }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2 py-0.5">
      <span className="font-mono text-[11px] text-slate-600">{hash}</span>
      <button type="button" title="Sao chép hash" aria-label={`Sao chép hash ${hash}`} onClick={(e) => { e.stopPropagation(); onCopy(hash); }}
        className="text-slate-400 hover:text-blue-600">⧉</button>
    </span>
  );
}

function Tabs({ tab, counts, onChange }) {
  const items = [["corpora", "Phiên bản corpus", counts.corpora], ["registry", "Sổ đăng ký tài liệu", counts.registry]];
  return (
    <div role="tablist" className="flex gap-8 border-b border-slate-200">
      {items.map(([id, label, count]) => (
        <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => onChange(id)}
          className={`-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 pb-3 text-sm ${tab === id ? "border-blue-600 font-semibold text-blue-600" : "border-transparent font-medium text-slate-500 hover:text-slate-700"}`}>
          {label}
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${tab === id ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-600"}`}>{count}</span>
        </button>
      ))}
    </div>
  );
}

// ─── Tab 1: phiên bản corpus ────────────────────────────────────────────────

function CorporaTable({ corpora, onOpen, onActivate, onArchive, onCompare }) {
  const small = "min-h-8 px-2 py-1 text-xs";
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-xs">
        <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-600">
          <tr>
            {["Phiên bản", "Trạng thái", "Ngày tạo", "Số tài liệu", "Phạm vi doanh nghiệp", "Phạm vi kỳ dữ liệu", "Người tạo", "Manifest", "Thao tác"].map((h) => (
              <th key={h} scope="col" className={`whitespace-nowrap px-4 py-3 ${h === "Thao tác" ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {corpora.map((c) => (
            <tr key={c.v} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-4 py-3 font-semibold">
                <button type="button" onClick={() => onOpen(c.v)} className="text-blue-600 hover:underline">Corpus {c.v}</button>
              </td>
              <td className="whitespace-nowrap px-4 py-3"><StatusBadge tone={STATUS_TONE[c.status]}>{c.status}</StatusBadge></td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{c.created}</td>
              <td className="whitespace-nowrap px-4 py-3 tabular-nums text-slate-600">{c.docs.length} tài liệu</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{c.companies}</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{c.period}</td>
              <td className="whitespace-nowrap px-4 py-3 text-slate-600">{c.by}</td>
              <td className="whitespace-nowrap px-4 py-3 font-medium">{c.manifest ? <span className="text-emerald-700">Có manifest</span> : <span className="text-slate-400">Chưa có manifest</span>}</td>
              <td className="px-4 py-3 text-right">
                <div className="inline-flex flex-wrap items-center justify-end gap-1">
                  <Button variant="ghost" className={small} onClick={() => onOpen(c.v)}>Xem chi tiết</Button>
                  {c.status === "Chưa kích hoạt" && <Button variant="secondary" className={small} onClick={() => onActivate(c.v)}>Kích hoạt</Button>}
                  {c.status === "Đang hoạt động" && <Button variant="secondary" className={small} disabled title="Không thể lưu trữ corpus đang hoạt động">Lưu trữ</Button>}
                  {c.status !== "Đang hoạt động" && c.status !== "Đã lưu trữ" && c.status !== "Kiểm tra không đạt" && (
                    <Button variant="secondary" className={small} onClick={() => onArchive(c.v)}>Lưu trữ</Button>
                  )}
                  <Button variant="secondary" className={small} onClick={() => onCompare(c.v)}>So sánh</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Tab 2: sổ đăng ký tài liệu ─────────────────────────────────────────────

function RegistryTable({ rows, corpora, onOpen, onCopy }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full border-collapse text-left text-xs">
        <thead className="border-b border-slate-200 bg-slate-50 font-semibold text-slate-600">
          <tr>
            {["Tài liệu", "Doanh nghiệp", "Loại báo cáo", "Kỳ", "Nguồn", "Phiên bản", "Hash", "Ngày công bố", "Validation", "Thuộc corpus"].map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap px-3 py-3 first:px-4">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((d) => (
            <tr key={d.id} onClick={() => onOpen(d.id)} className="cursor-pointer hover:bg-slate-50">
              <td className="px-4 py-3">
                <button type="button" onClick={(e) => { e.stopPropagation(); onOpen(d.id); }} className="text-left font-medium text-slate-900 hover:text-blue-600">{d.name}</button>
                <div className="text-[11px] text-slate-400">{docRef(d)}</div>
              </td>
              <td className="whitespace-nowrap px-3 py-3"><span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs font-bold text-slate-700">{d.co}</span></td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{d.type}</td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{d.period}</td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{d.source}</td>
              <td className="whitespace-nowrap px-3 py-3 font-semibold text-slate-700">{d.ver}</td>
              <td className="whitespace-nowrap px-3 py-3"><HashCell hash={d.hash} onCopy={onCopy} /></td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{d.pub}</td>
              <td className="whitespace-nowrap px-3 py-3"><StatusBadge tone={validationTone(d.validation)}>{d.validation}</StatusBadge></td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">{belongsTo(corpora, d.id)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Nội dung các panel ─────────────────────────────────────────────────────

function ManifestBody({ corpus, corpora, docs }) {
  if (!corpus.manifest) {
    return (
      <div className="space-y-2 p-8 text-center">
        <p className="text-sm font-semibold text-slate-700">Chưa có manifest</p>
        <p className="mx-auto max-w-sm text-xs text-slate-500">Phiên bản {corpus.v} chưa hoàn tất quy trình freeze hoặc không đạt kiểm tra tính hợp lệ.</p>
      </div>
    );
  }
  const items = corpus.docs.map((id) => docs.find((d) => d.id === id)).filter(Boolean);
  const sources = unique(items, (d) => `${d.source} ${d.srcVer}`);
  const sorted = [...corpora].sort((a, b) => compareVersions(b.v, a.v));
  const previous = sorted.slice(sorted.findIndex((c) => c.v === corpus.v) + 1)[0];

  return (
    <div className="space-y-5">
      <InfoRows rows={[
        ["Corpus version:", <strong key="v">{corpus.v}</strong>], ["Company scope:", corpus.companies], ["Period scope:", corpus.period],
        ["Configuration metadata:", <span key="c" className="rounded bg-slate-200/60 px-2 py-0.5 font-mono">{corpus.config}</span>],
        ["Created by:", corpus.by], ["Created at:", corpus.created],
      ]} />
      <section>
        <Heading>Document version IDs ({items.length})</Heading>
        <div className="flex max-h-36 flex-wrap gap-1.5 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
          {items.map((d) => <span key={d.id} className="rounded border border-slate-200 bg-slate-100 px-2 py-1 font-mono text-[11px] text-slate-700">{docRef(d)} · {d.ver}</span>)}
        </div>
      </section>
      <section>
        <Heading>Evidence hashes (Short form)</Heading>
        <div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
          {items.map((d) => <span key={d.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 font-mono text-[11px] text-slate-600">{d.hash}</span>)}
        </div>
      </section>
      <section>
        <Heading>Source versions</Heading>
        <ul className="space-y-1 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          {sources.map((s) => <li key={s}>• {s}</li>)}
        </ul>
      </section>
      <section>
        <Heading>Lịch sử phiên bản corpus</Heading>
        <ul className="space-y-2 text-xs">
          <li className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-2.5">
            <div><p className="font-semibold text-slate-800">Corpus {corpus.v} (đang xem)</p><p className="text-[11px] text-slate-500">Ngày tạo: {corpus.created}{previous ? ` · Kế thừa ${previous.v}` : ""}</p></div>
            <StatusBadge tone={STATUS_TONE[corpus.status]}>{corpus.status}</StatusBadge>
          </li>
          {previous && (
            <li className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <div><p className="font-semibold text-slate-700">Corpus {previous.v}</p><p className="text-[11px] text-slate-500">Phiên bản liền trước · Bảo toàn chứng cứ lịch sử</p></div>
              <StatusBadge tone={STATUS_TONE[previous.status]}>{previous.status}</StatusBadge>
            </li>
          )}
        </ul>
      </section>
    </div>
  );
}

function DocDetailBody({ doc, corpora, docs, onCopy }) {
  const other = docs.find((d) => d.id === (doc.supersedes || doc.supersededBy));
  return (
    <div className="space-y-5 text-xs">
      {doc.issue === "hash" && (
        <div role="alert" className="space-y-2 rounded-xl border border-rose-200 bg-rose-50 p-4">
          <p className="font-bold text-rose-800">✕ Không đạt kiểm tra integrity</p>
          <p className="text-rose-700">Không được đưa vào frozen corpus. Hệ thống kiểm soát tính toàn vẹn phát hiện bất thường mã băm.</p>
          <p className="border-t border-rose-200 pt-1 text-[11px] font-medium italic text-rose-600">Chính sách hệ thống: Không có cơ chế can thiệp thủ công (No override) nhằm bảo vệ tính bất biến.</p>
        </div>
      )}
      {doc.family && (
        <section>
          <Heading>Document family ({doc.family})</Heading>
          {doc.supersedes ? (
            <div className="space-y-2 rounded-xl border border-blue-200 bg-blue-50 p-3">
              <div className="flex items-center justify-between"><span className="font-semibold text-blue-900">{doc.ver} (Đang dùng)</span><StatusBadge tone="info">Hiện hành</StatusBadge></div>
              <p className="text-blue-800">{doc.ver} thay thế {other?.ver} (không ghi đè, {other?.ver} vẫn được bảo toàn nguyên vẹn trong kho lưu trữ).</p>
              <p className="border-t border-blue-200 pt-1 text-[11px] text-slate-600">Tài liệu tiền nhiệm: <span className="font-mono font-medium">{other?.id} ({other?.ver})</span></p>
            </div>
          ) : (
            <div className="space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <div className="flex items-center justify-between"><span className="font-semibold text-slate-700">{doc.ver} (Đã bị thay thế)</span><StatusBadge>Lịch sử</StatusBadge></div>
              <p className="text-slate-600">Đã bị thay thế bởi phiên bản {other?.ver} ({other?.id}). Bản ghi {doc.ver} được lưu trữ bất biến phục vụ mục đích kiểm toán.</p>
            </div>
          )}
        </section>
      )}
      <section>
        <Heading>Thông tin Provenance &amp; Nguồn</Heading>
        <InfoRows rows={[
          ["Nguồn:", doc.source], ["URL nguồn:", <span key="u" className="italic text-slate-500">{NO_DATA}</span>],
          ["Source version:", doc.srcVer], ["Ngày công bố:", doc.pub], ["Ngày ingest:", <span key="i" className="font-mono">{doc.ingest}</span>],
          ["Hash (Mã băm):", <HashCell key="h" hash={doc.hash} onCopy={onCopy} />],
          ["Validation state:", <StatusBadge key="v" tone={validationTone(doc.validation)}>{doc.validation}</StatusBadge>],
          ["Corpus version đang sử dụng:", belongsTo(corpora, doc.id)],
        ]} />
      </section>
    </div>
  );
}

function CompareBody({ a, b, docs }) {
  const diff = compareCorpora(a, b, docs);
  const none = <span className="italic text-slate-400">Không có thay đổi</span>;
  const box = (title, right, children) => (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between font-semibold text-slate-800"><span>{title}</span>{right}</div>
      {children}
    </div>
  );
  return (
    <div className="space-y-4 text-xs">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3"><span className="text-[11px] font-semibold uppercase text-slate-400">Phiên bản gốc (A)</span><p className="mt-1 text-sm font-bold text-slate-800">Corpus {a.v}</p><p className="mt-0.5 text-slate-500">{a.docs.length} tài liệu trong manifest</p></div>
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-3"><span className="text-[11px] font-semibold uppercase text-blue-500">Phiên bản so sánh (B)</span><p className="mt-1 text-sm font-bold text-blue-900">Corpus {b.v}</p><p className="mt-0.5 text-blue-700">{b.docs.length} tài liệu trong manifest</p></div>
      </div>
      {box("Số tài liệu thay đổi", <span className="font-mono text-[11px] font-bold text-blue-600">Thêm: {diff.added.length} / Bớt: {diff.removed.length}</span>,
        <p className="text-slate-600">{diff.added.length + diff.removed.length === 0 ? "Không có thay đổi" : `Biến động tài liệu: +${diff.added.length} mới, -${diff.removed.length} đã bị gỡ bỏ.`}</p>)}
      {box("Document version mới", null, diff.added.length ? <ul className="list-disc space-y-1 pl-4 text-slate-700">{diff.added.map((n) => <li key={n}>{n}</li>)}</ul> : none)}
      {box("Source thay đổi", null, diff.addedSources.length + diff.removedSources.length ? (
        <div className="space-y-1">
          {diff.addedSources.map((s) => <p key={s} className="text-emerald-700">+ Thêm nguồn: {s}</p>)}
          {diff.removedSources.map((s) => <p key={s} className="text-rose-700">- Bớt nguồn: {s}</p>)}
        </div>
      ) : none)}
      {box("Kỳ thay đổi", null, diff.period ? <p className="text-slate-700">{diff.period}</p> : none)}
    </div>
  );
}

const STEPS = ["Chọn record", "Phạm vi", "Metadata & Hash", "Xác nhận"];

function Check({ tone, title, text, verdict }) {
  const styles = { ok: "border-emerald-200 bg-emerald-50/50 text-emerald-900", warn: "border-amber-200 bg-amber-50/50 text-amber-900", bad: "border-rose-200 bg-rose-50/50 text-rose-900" };
  return (
    <div className={`space-y-1 rounded-xl border p-4 text-xs ${styles[tone]}`}>
      <p className="font-bold">{title}</p>
      <p className="opacity-90">{text}</p>
      <p className="text-[11px] font-semibold">{verdict}</p>
    </div>
  );
}

function WizardBody({ step, version, selected, docs, issues, onToggle, onToggleAll, onViewBad, onDropBad }) {
  const candidates = CANDIDATE_DOC_IDS.map((id) => docs.find((d) => d.id === id)).filter(Boolean);
  const Title = ({ children, sub }) => (<div><h3 className="text-sm font-bold text-slate-900">{children}</h3><p className="mt-1 text-xs text-slate-500">{sub}</p></div>);
  const status = (count, okText, badText, badTone) => (count > 0
    ? { tone: badTone, text: badText(count), verdict: "✕ Không đạt" } : { tone: "ok", text: okText, verdict: "✓ Đạt chuẩn" });

  return (
    <div className="space-y-5">
      <ol className="flex items-center justify-between gap-2" aria-label="Các bước">
        {STEPS.map((name, i) => {
          const n = i + 1;
          const state = n < step ? "bg-emerald-500 text-white" : n === step ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-500";
          return (
            <li key={name} aria-current={n === step ? "step" : undefined} className="flex items-center gap-1.5">
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${state}`}>{n < step ? "✓" : n}</span>
              <span className={`text-[11px] ${n === step ? "font-semibold text-slate-800" : "text-slate-500"}`}>{name}</span>
            </li>
          );
        })}
      </ol>

      {step === 1 && (
        <div className="space-y-4">
          <Title sub="Lựa chọn các bản ghi tài liệu ứng viên đưa vào corpus freeze. Hệ thống sẽ thẩm định tính hợp lệ ở các bước tiếp theo.">Bước 1: Chọn các record hợp lệ</Title>
          <div className="flex items-center justify-between rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-xs">
            <span className="font-medium text-blue-900">Đã chọn: <strong>{selected.size} / {candidates.length}</strong> tài liệu ứng viên</span>
            <button type="button" onClick={onToggleAll} className="font-semibold text-blue-600 hover:text-blue-800">{selected.size === candidates.length ? "Bỏ chọn tất cả" : "Chọn tất cả"}</button>
          </div>
          <ul className="space-y-2">
            {candidates.map((d) => (
              <li key={d.id}>
                <label className={`flex cursor-pointer items-center justify-between gap-3 rounded-xl border p-3 ${selected.has(d.id) ? "border-slate-300 bg-white" : "border-slate-200 bg-slate-50 opacity-60"}`}>
                  <span className="flex items-center gap-3">
                    <input type="checkbox" checked={selected.has(d.id)} onChange={() => onToggle(d.id)} className="h-4 w-4 rounded border-slate-300 text-blue-600" />
                    <span>
                      <span className="block text-xs font-medium text-slate-900">{d.name}</span>
                      <span className="mt-0.5 flex items-center gap-2 text-[11px] text-slate-500"><span className="rounded bg-slate-100 px-1 font-mono">{d.co}</span>{d.type} · {d.period}</span>
                    </span>
                  </span>
                  <StatusBadge tone={validationTone(d.validation)}>{d.validation}</StatusBadge>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <Title sub="Đánh giá tính tuân thủ về danh sách doanh nghiệp trong phạm vi cho phép và kỳ báo cáo tương thích.">Bước 2: Kiểm tra phạm vi dữ liệu</Title>
          <Check tone="ok" title="Doanh nghiệp trong phạm vi (Company in scope)" text="Tất cả các tài liệu được chọn thuộc danh mục 10 doanh nghiệp được phê duyệt quản trị." verdict="✓ Đạt chuẩn" />
          <Check tone="ok" title="Kỳ dữ liệu hợp lệ (Period valid)" text="Kỳ báo cáo nằm trong phạm vi 3 năm tài chính gần nhất + 4 quý gần nhất theo quy định corpus." verdict="✓ Đạt chuẩn" />
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <Title sub="Xác thực trường thông tin bắt buộc và đối soát mã băm độc lập trên từng bản ghi được chọn.">Bước 3: Kiểm tra metadata &amp; integrity hash</Title>
          <Check title="Ngày công bố (Publication date)" {...status(issues.pubDate, "Tất cả tài liệu được chọn đã có ngày công bố hợp lệ.", (n) => `Phát hiện ${n} tài liệu thiếu ngày công bố chính thức.`, "warn")} />
          <Check title="Phạm vi báo cáo & Loại văn bản (Statement scope)" {...status(issues.scope, "Định danh báo cáo tài chính/thường niên chuẩn xác.", (n) => `Phát hiện ${n} tài liệu chưa có phạm vi báo cáo.`, "warn")} />
          <Check title="Kiểm tra integrity hash" {...status(issues.hash, "Tất cả mã băm tài liệu khớp 100% với tệp gốc nguồn.", (n) => `Phát hiện ${n} tài liệu hash verification không đạt.`, "bad")} />
        </div>
      )}

      {step === 4 && (issues.total > 0 ? (
        <div className="space-y-4">
          <Title sub="Kiểm toán tổng thể các điều kiện tiên quyết trước khi ký số tạo phiên bản bất biến.">Bước 4: Xác nhận đóng băng corpus (Freeze)</Title>
          <div role="alert" className="space-y-3 rounded-2xl border border-rose-200 bg-rose-50 p-5">
            <p className="text-sm font-bold text-rose-800">⛔ Không thể tạo phiên bản corpus</p>
            <p className="text-xs leading-relaxed text-rose-700">Các tài liệu được chọn không vượt qua bài kiểm tra toàn vẹn dữ liệu. Để tiếp tục đóng băng, hãy bỏ chọn các tài liệu bị lỗi hoặc kiểm tra sổ đăng ký.</p>
            <div className="space-y-1.5 rounded-xl border border-rose-200 bg-white/80 p-3 text-xs text-rose-800">
              <p className="font-semibold text-rose-900">Nguyên nhân từ chối freeze:</p>
              <ul className="list-disc space-y-1 pl-4">
                {issues.pubDate > 0 && <li>{issues.pubDate} tài liệu thiếu publication date</li>}
                {issues.scope > 0 && <li>{issues.scope} tài liệu chưa có statement scope</li>}
                {issues.hash > 0 && <li>{issues.hash} tài liệu hash verification không đạt</li>}
              </ul>
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button variant="danger" className="text-xs" onClick={onViewBad}>Xem bản ghi bị lỗi</Button>
              <Button variant="secondary" className="text-xs" onClick={onDropBad}>Bỏ chọn tài liệu lỗi &amp; kiểm tra lại</Button>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <Title sub={`Toàn bộ ${selected.size} tài liệu được chọn đã đạt chuẩn xác thực 100%. Xác nhận đóng băng phiên bản ${version}.`}>Bước 4: Xác nhận đóng băng corpus (Freeze)</Title>
          <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
            <p className="text-sm font-bold text-emerald-800">✓ Đủ điều kiện tạo Corpus {version}</p>
            <p className="text-xs leading-relaxed text-emerald-700">Phiên bản được đóng băng sẽ được cấp mã định danh bất biến, tự động tạo manifest và chuyển sang trạng thái <strong>Chưa kích hoạt</strong>.</p>
            <div className="rounded-xl border border-emerald-200 bg-white p-3">
              <InfoRows rows={[["Phiên bản mới:", `Corpus ${version}`], ["Số tài liệu hợp lệ:", `${selected.size} tài liệu`], ["Phạm vi doanh nghiệp:", "10 doanh nghiệp"], ["Trạng thái khởi tạo:", "Chưa kích hoạt"]]} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminCorpusPage() {
  const { version } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast, toastNode } = useToasts();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [pick, setPick] = useState({ a: "", b: "" });
  // overlay: null | { type: "wizard" } | { type: "doc", id } | { type: "compare", a, b } | { type: "confirm", kind, v }
  const [overlay, setOverlay] = useState(null);
  const [wizard, setWizard] = useState({ step: 1, selected: new Set(CANDIDATE_DOC_IDS) });

  const tab = searchParams.get("tab") === "registry" ? "registry" : "corpora";
  const manifestVersion = version || searchParams.get("corpus");

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getCorpusData()
      .then(setData)
      .catch((e) => { setData(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const corpora = data?.corpora ?? [];
  const docs = data?.documents ?? [];
  const activeCorpus = corpora.find((c) => c.status === "Đang hoạt động") ?? null;
  const manifestCorpus = corpora.find((c) => c.v === manifestVersion) ?? null;
  const docOverlay = overlay?.type === "doc" ? docs.find((d) => d.id === overlay.id) : null;
  const compareOverlay = overlay?.type === "compare"
    ? { a: corpora.find((c) => c.v === overlay.a), b: corpora.find((c) => c.v === overlay.b) } : null;
  const confirmCorpus = overlay?.type === "confirm" ? corpora.find((c) => c.v === overlay.v) : null;

  const defaultA = pick.a || activeCorpus?.v || corpora[0]?.v || "";
  const defaultB = pick.b || corpora.find((c) => c.v !== defaultA)?.v || defaultA;

  const closeOverlay = useCallback(() => setOverlay(null), []);
  const openManifest = useCallback((v) => navigate(`${ADMIN_LINKS.corpus}/${v}`), [navigate]);
  const closeManifest = useCallback(() => navigate(ADMIN_LINKS.corpus), [navigate]);
  const goTab = (id) => navigate(id === "registry" ? `${ADMIN_LINKS.corpus}?tab=registry` : ADMIN_LINKS.corpus);

  const copyHash = useCallback(async (hash) => {
    try { await navigator.clipboard.writeText(hash); } catch { /* clipboard bị chặn: vẫn báo như mockup */ }
    toast(`Đã sao chép hash: ${hash}`, "success");
  }, [toast]);

  const patchCorpus = (v, patch) => setData((d) => ({ ...d, corpora: d.corpora.map((c) => (c.v === v ? { ...c, ...patch } : c)) }));

  function runConfirm() {
    const { kind, v } = overlay;
    if (kind === "activate") {
      setData((d) => ({ ...d, corpora: d.corpora.map((c) => (c.status === "Đang hoạt động" ? { ...c, status: "Đã lưu trữ" } : c.v === v ? { ...c, status: "Đang hoạt động", activatedAt: todayLabel() } : c)) }));
      toast(`Đã kích hoạt Corpus ${v}. Hệ thống đang điều hướng truy vấn mới sang phiên bản này.`, "success");
    } else {
      patchCorpus(v, { status: "Đã lưu trữ" });
      toast(`Đã lưu trữ Corpus ${v}. Dữ liệu được bảo toàn phục vụ kiểm toán.`, "success");
    }
    setOverlay(null);
  }

  // ── Wizard ──
  const newVersion = corpora.length ? nextVersion(corpora) : "v1.0";
  const selectedDocs = [...wizard.selected].map((id) => docs.find((d) => d.id === id)).filter(Boolean);
  const issues = wizardIssues(selectedDocs);
  const blocked = wizard.step === 4 && issues.total > 0;
  const setStep = (step) => setWizard((w) => ({ ...w, step }));
  const setSelected = (fn) => setWizard((w) => { const next = new Set(w.selected); fn(next); return { ...w, selected: next }; });

  function openWizard() {
    setWizard({ step: 1, selected: new Set(CANDIDATE_DOC_IDS) });
    setOverlay({ type: "wizard" });
  }

  function freeze() {
    setData((d) => ({ ...d, corpora: [{
      v: newVersion, status: "Chưa kích hoạt", created: todayLabel(), companies: "10 doanh nghiệp", period: "3 năm + 4 quý gần nhất",
      by: "FinMind Admin", config: "CFG-DEMO", manifest: true, docs: [...wizard.selected],
    }, ...d.corpora] }));
    setOverlay(null);
    toast(`Đã tạo Corpus ${newVersion}. Phiên bản đã freeze và không thể chỉnh sửa.`, "success");
  }

  function viewBadRecords() {
    setOverlay(null);
    setFilters(EMPTY_FILTERS);
    goTab("registry");
    toast("Đã chuyển sang Sổ đăng ký tài liệu để rà soát.", "info");
  }

  const registryFilters = [
    { key: "q", type: "text", label: "Tìm tài liệu", placeholder: "Tìm tài liệu..." },
    { key: "company", type: "select", label: "Doanh nghiệp", options: options("Tất cả mã", unique(docs, (d) => d.co)) },
    { key: "period", type: "select", label: "Kỳ", options: options("Tất cả kỳ", unique(docs, (d) => d.period)) },
    { key: "source", type: "select", label: "Nguồn", options: options("Tất cả nguồn", unique(docs, (d) => d.source)) },
    { key: "type", type: "select", label: "Loại báo cáo", options: options("Tất cả loại", unique(docs, (d) => d.type)) },
    { key: "validation", type: "select", label: "Validation state", options: options("Tất cả trạng thái", unique(docs, (d) => d.validation)) },
    { key: "corpus", type: "select", label: "Corpus version", options: options("Tất cả corpus", corpora.map((c) => c.v), (v) => `Corpus ${v}`) },
  ];
  const registryRows = filterDocuments(docs, corpora, filters);

  const confirmText = confirmCorpus && (overlay.kind === "activate"
    ? "Các truy vấn mới đủ điều kiện sẽ sử dụng phiên bản corpus này."
    : `Bạn có chắc chắn muốn chuyển Corpus ${confirmCorpus.v} sang trạng thái lưu trữ? Bản ghi và manifest sẽ vẫn được giữ nguyên vẹn trong danh sách.`);

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200/70 pb-3 md:flex-row md:items-center">
        <div>
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link>
            <span aria-hidden="true">/</span>
            <span className="font-medium text-slate-800">Phiên bản kho dữ liệu</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Phiên bản kho dữ liệu</h1>
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">Dữ liệu minh họa</span>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">Theo dõi tài liệu, provenance và các phiên bản corpus được sử dụng trong FinMind.</p>
        </div>
        <Button className="shrink-0 self-start text-xs" disabled={!data} onClick={openWizard}>＋ Tạo phiên bản corpus</Button>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && data && (
        <>
          <Card>
            <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
              <div className="space-y-2">
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Corpus đang hoạt động</p>
                {activeCorpus ? (
                  <>
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="text-lg font-bold tracking-tight text-slate-900">Corpus {activeCorpus.v}</span>
                      <StatusBadge tone="success">Đang hoạt động</StatusBadge>
                    </div>
                    <dl className="flex flex-wrap items-center gap-x-6 gap-y-1 pt-1 text-xs text-slate-600">
                      <div><dt className="inline text-slate-400">Phạm vi:</dt> <dd className="ml-1 inline font-medium text-slate-800">{activeCorpus.companies}</dd></div>
                      <div><dt className="inline text-slate-400">Kỳ:</dt> <dd className="ml-1 inline font-medium text-slate-800">{activeCorpus.period === "3 năm + 4 quý gần nhất" ? "3 năm tài chính gần nhất + 4 quý gần nhất" : activeCorpus.period}</dd></div>
                      <div><dt className="inline text-slate-400">Ngày kích hoạt:</dt> <dd className="ml-1 inline font-medium text-slate-800">{activeCorpus.activatedAt || activeCorpus.created}</dd></div>
                    </dl>
                  </>
                ) : <p className="text-sm text-slate-500">Chưa có corpus nào đang hoạt động.</p>}
              </div>
              {activeCorpus && <Button variant="secondary" className="shrink-0 text-xs" onClick={() => openManifest(activeCorpus.v)}>Xem manifest</Button>}
            </div>
          </Card>

          <Tabs tab={tab} counts={{ corpora: corpora.length, registry: docs.length }} onChange={goTab} />

          {tab === "corpora" ? (
            <section className="space-y-4">
              <div className="flex flex-col justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:flex-row md:items-end">
                <div className="flex flex-wrap items-end gap-3">
                  <span className="pb-2 text-xs font-semibold text-slate-700">So sánh phiên bản:</span>
                  <Select label="Phiên bản A" className="min-w-36" value={defaultA} onChange={(e) => setPick((p) => ({ ...p, a: e.target.value, b: defaultB }))}
                    options={corpora.map((c) => ({ value: c.v, label: `Corpus ${c.v}` }))} />
                  <span className="pb-2 text-slate-400">với</span>
                  <Select label="Phiên bản B" className="min-w-36" value={defaultB} onChange={(e) => setPick((p) => ({ ...p, b: e.target.value, a: defaultA }))}
                    options={corpora.map((c) => ({ value: c.v, label: `Corpus ${c.v}` }))} />
                </div>
                <Button variant="secondary" className="text-xs" onClick={() => setOverlay({ type: "compare", a: defaultA, b: defaultB })}>So sánh phiên bản</Button>
              </div>

              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-800">Danh sách phiên bản corpus</h2>
                <span className="text-xs text-slate-500">Tổng cộng {corpora.length} phiên bản</span>
              </div>
              {corpora.length === 0 ? <EmptyState title="Chưa có phiên bản corpus nào" /> : (
                <CorporaTable corpora={corpora} onOpen={openManifest}
                  onActivate={(v) => setOverlay({ type: "confirm", kind: "activate", v })}
                  onArchive={(v) => setOverlay({ type: "confirm", kind: "archive", v })}
                  onCompare={(v) => setOverlay({ type: "compare", a: defaultA, b: v })} />
              )}
            </section>
          ) : (
            <section className="space-y-4">
              <FilterBar filters={registryFilters} values={filters}
                onChange={(key, value) => setFilters((f) => ({ ...f, [key]: value }))} onReset={() => setFilters(EMPTY_FILTERS)} />
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-800">Danh mục tài liệu đăng ký</h2>
                <span className="text-xs text-slate-500">Hiển thị {registryRows.length} / {docs.length} tài liệu</span>
              </div>
              {registryRows.length === 0
                ? <EmptyState title="Không tìm thấy tài liệu phù hợp." description="Vui lòng điều chỉnh lại bộ lọc." action={<Button variant="ghost" onClick={() => setFilters(EMPTY_FILTERS)}>Đặt lại bộ lọc</Button>} />
                : <RegistryTable rows={registryRows} corpora={corpora} onOpen={(id) => setOverlay({ type: "doc", id })} onCopy={copyHash} />}
            </section>
          )}
        </>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-xs text-slate-500">Chỉ dùng cho quản trị vận hành FinMind. Dữ liệu minh họa.</footer>

      <Drawer open={Boolean(manifestCorpus)} onClose={closeManifest} title={manifestCorpus ? `Manifest Corpus ${manifestCorpus.v}` : ""}
        footer={<div className="flex w-full items-center justify-between text-xs text-slate-500"><span className="italic">Phiên bản chỉ đọc, không thể chỉnh sửa hoặc ghi đè.</span><Button variant="secondary" onClick={closeManifest}>Đóng</Button></div>}>
        {manifestCorpus && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {manifestCorpus.manifest && <StatusBadge tone="success">Bất biến (đã freeze)</StatusBadge>}
              <Link to={`${ADMIN_LINKS.audit}?corpus=${manifestCorpus.v}`} className="text-xs font-medium text-blue-600 hover:underline">Xem nhật ký liên quan →</Link>
            </div>
            <ManifestBody corpus={manifestCorpus} corpora={corpora} docs={docs} />
          </div>
        )}
      </Drawer>

      <Drawer open={Boolean(docOverlay)} onClose={closeOverlay} title={docOverlay ? docOverlay.name : ""}
        footer={<Button variant="secondary" onClick={closeOverlay}>Đóng</Button>}>
        {docOverlay && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">Mã định danh: {docRef(docOverlay)}</p>
            <DocDetailBody doc={docOverlay} corpora={corpora} docs={docs} onCopy={copyHash} />
          </div>
        )}
      </Drawer>

      <Drawer open={overlay?.type === "wizard"} onClose={closeOverlay} title={`Tạo phiên bản corpus mới (Corpus ${newVersion})`}
        footer={
          <div className="flex w-full items-center justify-between">
            {wizard.step > 1 ? <Button variant="secondary" onClick={() => setStep(wizard.step - 1)}>Quay lại</Button> : <span />}
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={closeOverlay}>Hủy</Button>
              <Button disabled={(wizard.step === 1 && wizard.selected.size === 0) || blocked} onClick={() => (wizard.step === 4 ? freeze() : setStep(wizard.step + 1))}>
                {wizard.step === 4 ? "Xác nhận freeze" : "Tiếp tục"}
              </Button>
            </div>
          </div>
        }>
        <WizardBody step={wizard.step} version={newVersion} selected={wizard.selected} docs={docs} issues={issues}
          onToggle={(id) => setSelected((s) => (s.has(id) ? s.delete(id) : s.add(id)))}
          onToggleAll={() => setSelected((s) => { if (s.size === CANDIDATE_DOC_IDS.length) s.clear(); else CANDIDATE_DOC_IDS.forEach((id) => s.add(id)); })}
          onViewBad={viewBadRecords}
          onDropBad={() => setSelected((s) => docs.filter((d) => d.issue).forEach((d) => s.delete(d.id)))} />
      </Drawer>

      <Modal open={Boolean(compareOverlay?.a && compareOverlay?.b)} onClose={closeOverlay}
        title={compareOverlay?.a && compareOverlay?.b ? `So sánh Corpus ${compareOverlay.a.v} với Corpus ${compareOverlay.b.v}` : ""}
        footer={<Button variant="secondary" onClick={closeOverlay}>Đóng so sánh</Button>}>
        {compareOverlay?.a && compareOverlay?.b && <CompareBody a={compareOverlay.a} b={compareOverlay.b} docs={docs} />}
      </Modal>

      <Modal open={Boolean(confirmCorpus)} onClose={closeOverlay}
        title={confirmCorpus ? `${overlay.kind === "activate" ? "Kích hoạt" : "Lưu trữ"} Corpus ${confirmCorpus.v}?` : ""}
        footer={<><Button variant="secondary" onClick={closeOverlay}>Hủy</Button><Button onClick={runConfirm}>{overlay?.kind === "activate" ? "Kích hoạt" : "Lưu trữ"}</Button></>}>
        {confirmText}
      </Modal>

      {toastNode}
    </AdminLayout>
  );
}
