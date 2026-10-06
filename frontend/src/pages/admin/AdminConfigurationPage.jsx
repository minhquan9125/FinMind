// Trang A04: Ngưỡng & ngân sách API (route /admin/configuration và /admin/configuration/:configId).
// Mở chi tiết một phiên bản bằng :configId (vd. v2.4) hoặc ?cfg=v2.4; ?usage=82 mô phỏng mức dùng ngân sách;
// ?focus=budget cuộn tới khối ngân sách. Dữ liệu minh họa lấy từ ./configurationMock.js;
// mọi thay đổi (tạo, kích hoạt, khôi phục phiên bản) chỉ lưu trong bộ nhớ trang, chưa gọi backend.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "../../app/router.jsx";
import { Button, Card, Drawer, ErrorState, Input, Modal, Select, Skeleton, StatusBadge } from "../../shared/ui";
import AdminLayout, { ADMIN_LINKS } from "./AdminLayout.jsx";
import { getConfigurationData } from "./configurationMock.js";
import useToasts from "./useToasts.jsx";

// ─── Định nghĩa tham số (dùng chung cho thẻ hiển thị, form, chi tiết và kiểm tra) ───

const FIELDS = {
  relevance: { label: "Ngưỡng relevance", unit: "%", min: 60, max: 90, desc: "Mức liên quan tối thiểu để một đoạn được đưa vào bước chọn bằng chứng." },
  evidence: { label: "Ngưỡng bằng chứng", unit: "%", min: 60, max: 90, desc: "Mức tối thiểu để bằng chứng được xem là đủ điều kiện cho bước tiếp theo." },
  verifier: { label: "Ngưỡng xác minh (Verifier)", unit: "%", min: 70, max: 95, desc: "Mức hỗ trợ tối thiểu mà câu trả lời phải đạt trước khi được phát hành." },
  minEvidence: { label: "Số bằng chứng tối thiểu", unit: "", min: 1, max: 10, desc: "Số bằng chứng hợp lệ tối thiểu mà Evidence Gate yêu cầu." },
  freshness: { label: "Giới hạn độ mới của nguồn", unit: "ngày", min: 30, max: 730, desc: "Giới hạn độ mới của nguồn theo chính sách nguồn." },
  vectorLimit: { label: "Giới hạn ứng viên Vector", unit: "", min: 5, max: 50, desc: "Số lượng đoạn văn bản tối đa thu hồi từ kho lưu trữ Vector." },
  graphLimit: { label: "Giới hạn quan hệ Graph", unit: "", min: 3, max: 30, desc: "Số thực thể và liên kết tri thức tối đa thu thập từ sơ đồ tri thức Graph." },
  fusionTopK: { label: "Giới hạn kết quả sau fusion", unit: "", min: 3, max: 20, desc: "Số lượng ứng viên tốt nhất được giữ lại sau bước hợp nhất Vector & Graph." },
  rerankLimit: { label: "Rerank limit", unit: "", min: 3, max: 15, desc: "Số tài liệu tối đa được chuyển vào bộ xếp hạng lại (Reranker) trước khi đưa vào ngữ cảnh." },
  contextCeiling: { label: "Context ceiling", unit: "token", min: 2000, max: 8000, desc: "Giới hạn tổng ngữ cảnh tài liệu đính kèm. Min retrieval context: 1,500 token." },
  inputCeiling: { label: "Input token ceiling", unit: "token", min: 1000, max: 8000, desc: "Giới hạn token đầu vào (prompt + tài liệu trích dẫn) cho một request." },
  outputCeiling: { label: "Output token ceiling", unit: "token", min: 500, max: 4000, desc: "Giới hạn token câu trả lời do mô hình sinh ra." },
  totalCeiling: { label: "Tổng token tối đa / request", unit: "token", min: 2000, max: 8000, desc: "Giới hạn tuyệt đối cho tổng số token trên mỗi chu trình pipeline." },
  warningThreshold: { label: "Warning threshold", unit: "%", min: 50, max: 95, desc: "Mức sử dụng ngân sách bắt đầu hiện cảnh báo." },
};

const GROUPS = [
  { id: "evidence", title: "Ngưỡng bằng chứng (Evidence Gate)", bar: "bg-blue-600", keys: ["relevance", "evidence", "verifier", "minEvidence", "freshness"] },
  { id: "retrieval", title: "Truy xuất & hợp nhất", bar: "bg-indigo-600", keys: ["vectorLimit", "graphLimit", "fusionTopK", "rerankLimit"] },
  { id: "tokens", title: "Giới hạn ngữ cảnh & Token", bar: "bg-teal-600", keys: ["contextCeiling", "inputCeiling", "outputCeiling", "totalCeiling"] },
  { id: "budget", title: "Ngưỡng cảnh báo ngân sách", bar: "bg-amber-500", keys: ["warningThreshold"] },
];

const MIN_RETRIEVAL_CONTEXT = 1500; // cố định, không sửa trong form
const HARD_CEILING = 100; // % cố định
const KIND_OPTIONS = [
  { value: "PRODUCTION", label: "PRODUCTION (áp dụng sau khi kích hoạt)" },
  { value: "CALIBRATION", label: "CALIBRATION (cấu hình thử nghiệm, không áp dụng cho production)" },
];
const STATUS_TONE = { "Đang hoạt động": "success", "Đang chờ kích hoạt": "info", "Cấu hình thử nghiệm": "neutral", "Đã thay thế": "neutral" };

// ─── Hàm thuần ──────────────────────────────────────────────────────────────

const fmtNum = (n) => Number(n).toLocaleString("en-US");
function fmtVal(key, value) {
  const { unit } = FIELDS[key];
  if (unit === "%") return `${value}%`;
  if (unit) return `${fmtNum(value)} ${unit}`;
  return String(value);
}

const parseVer = (name) => { const m = /v(\d+)\.(\d+)/.exec(name); return m ? [Number(m[1]), Number(m[2])] : [0, 0]; };
function nextVersionName(versions) {
  const [major, minor] = versions.map((v) => parseVer(v.v)).reduce((a, b) => (b[0] > a[0] || (b[0] === a[0] && b[1] > a[1]) ? b : a), [2, 0]);
  return `CFG v${major}.${minor + 1}`;
}
const todayLabel = () => new Date().toLocaleDateString("en-GB"); // dd/mm/yyyy
const cfgId = (name) => name.replace(/^CFG\s*/i, ""); // "CFG v2.4" -> "v2.4"

function formFromParams(params) {
  return Object.fromEntries(Object.keys(FIELDS).map((k) => [k, String(params[k])]));
}

function validate(values) {
  const fieldErrors = {};
  const errors = [];
  for (const [key, meta] of Object.entries(FIELDS)) {
    const v = values[key];
    if (Number.isNaN(v)) {
      fieldErrors[key] = "Giá trị không hợp lệ";
      errors.push(`${meta.label}: Bắt buộc phải là số hợp lệ.`);
    } else if (v < meta.min || v > meta.max) {
      const range = `${meta.min}${meta.unit === "%" ? "%" : ""} – ${meta.max}${meta.unit === "%" ? "%" : ""}`;
      fieldErrors[key] = `Giá trị cho phép: ${range}${meta.unit && meta.unit !== "%" ? ` ${meta.unit}` : ""}`;
      errors.push(`${meta.label}: giá trị không hợp lệ. ${fieldErrors[key]}`);
    }
  }
  const rules = [
    [values.inputCeiling > values.totalCeiling, "Input token ceiling không thể lớn hơn tổng token tối đa / request."],
    [values.outputCeiling > values.totalCeiling, "Output token ceiling không thể lớn hơn tổng token tối đa / request."],
    [values.rerankLimit > values.fusionTopK, "Rerank limit không thể lớn hơn Fusion Top-K."],
    [values.fusionTopK > values.vectorLimit, "Fusion Top-K không thể lớn hơn giới hạn ứng viên Vector."],
    [values.minEvidence > values.fusionTopK, "Số bằng chứng tối thiểu không thể lớn hơn Fusion Top-K."],
  ];
  rules.forEach(([broken, message]) => broken && errors.push(message));
  return { fieldErrors, errors };
}

function changedFields(base, values) {
  return Object.keys(FIELDS).filter((k) => !Number.isNaN(values[k]) && values[k] !== base[k]);
}

function describeImpact(key, oldV, newV) {
  const label = FIELDS[key].label;
  const up = newV > oldV;
  switch (key) {
    case "verifier":
      return up
        ? `Ngưỡng xác minh tăng (${oldV}% → ${newV}%): yêu cầu xác minh nghiêm ngặt hơn; một số request trước đây đạt có thể không đạt; chỉ áp dụng cho request mới.`
        : `Ngưỡng xác minh giảm (${oldV}% → ${newV}%): giảm độ ngặt xác thực; phản hồi nhanh hơn nhưng tiềm ẩn rủi ro bằng chứng lỏng hơn.`;
    case "relevance":
    case "evidence":
      return up ? `${label} tăng: lọc bằng chứng chặt hơn, giảm số lượng đoạn nhiễu.` : `${label} giảm: chấp nhận nhiều bằng chứng biên hơn.`;
    case "totalCeiling":
    case "contextCeiling":
      return up ? `${label} tăng: mở rộng dung lượng cho request phân tích tài liệu phức tạp.` : `${label} giảm (${fmtNum(oldV)} → ${fmtNum(newV)}): request dài có thể bị dừng sớm hơn.`;
    case "warningThreshold":
      return up ? "Warning threshold tăng: cảnh báo xuất hiện muộn hơn." : `Warning threshold giảm (${oldV}% → ${newV}%): cảnh báo ngân sách xuất hiện sớm hơn.`;
    default:
      return `${label} thay đổi từ ${fmtVal(key, oldV)} sang ${fmtVal(key, newV)}.`;
  }
}

function budgetState(usedPct, warnAt) {
  if (usedPct >= HARD_CEILING) return "hard";
  if (usedPct >= warnAt) return "warning";
  return "normal";
}

// ─── Thành phần nhỏ ─────────────────────────────────────────────────────────

function KindBadge({ kind }) {
  const style = kind === "CALIBRATION" ? "border-purple-200 bg-purple-100 text-purple-800" : "border-slate-200 bg-slate-100 text-slate-700";
  return <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${style}`}>{kind}</span>;
}

function ParamRow({ field, value }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50/70 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold text-slate-800">{field.label}</span>
        <span className="flex items-baseline gap-1.5">
          <span className="text-sm font-bold text-slate-900">{value}</span>
          <span className="text-[11px] font-normal text-slate-400">[{field.min}–{field.max}]</span>
        </span>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">{field.desc}</p>
    </div>
  );
}

function GroupCard({ group, params, footer }) {
  return (
    <section className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <div className="mb-4 flex items-center gap-2 border-b border-slate-100 pb-3">
          <span aria-hidden="true" className={`h-4 w-2 rounded-full ${group.bar}`} />
          <h2 className="text-sm font-bold text-slate-900">{group.title}</h2>
        </div>
        <div className="space-y-3.5">
          {group.keys.map((k) => <ParamRow key={k} field={FIELDS[k]} value={fmtVal(k, params[k])} />)}
        </div>
      </div>
      {footer && <div className="mt-4 border-t border-slate-100 pt-3 text-[11px] text-slate-400">{footer}</div>}
    </section>
  );
}

const STATE_ROWS = (warnAt) => [
  { id: "normal", dot: "bg-blue-600", text: `< ${warnAt}% → Bình thường`, example: `Ví dụ: ${warnAt - 1}/100 = ${warnAt - 1}%`, on: "border-blue-200 bg-blue-50 text-blue-900" },
  { id: "warning", dot: "bg-amber-500", text: `≥ ${warnAt}% và < ${HARD_CEILING}% → Cảnh báo`, example: `Ví dụ: ${warnAt + 2}/100 = ${warnAt + 2}%`, on: "border-amber-200 bg-amber-50 text-amber-900" },
  { id: "hard", dot: "bg-red-600", text: `${HARD_CEILING}% → Đã đạt hard ceiling`, example: "Ví dụ: 100/100 = 100%", on: "border-red-200 bg-red-50 text-red-900" },
];
const BAR_COLOR = { normal: "bg-blue-600", warning: "bg-amber-500", hard: "bg-red-600" };

function BudgetCard({ budget, usage, warnAt, onSimulate, onViewConfig }) {
  const state = budgetState(usage, warnAt);
  const used = Math.round((usage / 100) * budget.limit);
  return (
    <section className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <div className="mb-4 flex items-center gap-2 border-b border-slate-100 pb-3">
          <span aria-hidden="true" className="h-4 w-2 rounded-full bg-amber-500" />
          <h2 className="text-sm font-bold text-slate-900">Ngân sách API</h2>
        </div>

        <div className="mb-4 grid grid-cols-3 gap-3">
          {[["Ngân sách kỳ", `${budget.limit} đơn vị`, "text-slate-900"], ["Đã sử dụng", used, "text-slate-900"], ["Còn lại", Math.max(0, budget.limit - used), "text-emerald-600"]].map(([label, value, tone]) => (
            <div key={label} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-center">
              <span className="mb-1 block text-[11px] text-slate-400">{label}</span>
              <span className={`text-sm font-bold ${tone}`}>{value}</span>
            </div>
          ))}
        </div>

        <div className="mb-4">
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="font-medium text-slate-700">Tỷ lệ tiêu thụ: <strong>{usage}%</strong></span>
            <span className="text-[11px] text-slate-400">Hard ceiling: {HARD_CEILING}%</span>
          </div>
          <div role="progressbar" aria-label="Tỷ lệ tiêu thụ ngân sách API" aria-valuemin={0} aria-valuemax={100} aria-valuenow={usage}
            className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
            <div className={`h-full rounded-full transition-all duration-300 ${BAR_COLOR[state]}`} style={{ width: `${Math.min(100, usage)}%` }} />
          </div>
          <div className="relative mt-1 h-4 text-[10px] text-slate-400">
            <span className="absolute left-0">0%</span>
            <span className="absolute font-semibold text-amber-600" style={{ left: `${warnAt}%`, transform: "translateX(-100%)" }}>{warnAt}% (Cảnh báo) ▲</span>
            <span className="absolute right-0 font-semibold text-red-600">{HARD_CEILING}% (Hard)</span>
          </div>
        </div>

        <ul className="mb-4 space-y-1.5">
          {STATE_ROWS(warnAt).map((r) => (
            <li key={r.id} className={`flex items-center justify-between rounded border p-2 text-xs ${state === r.id ? `${r.on} font-semibold` : "border-slate-200 bg-slate-50 text-slate-600"}`}>
              <span className="flex items-center gap-1.5"><span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${r.dot}`} />{r.text}</span>
              <span className="text-[11px]">{r.example}</span>
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
          <span className="text-[11px] text-slate-400">Mô phỏng mức dùng:</span>
          {[[61, "61% (Chuẩn)"], [82, "82% (Cảnh báo)"], [100, "100% (Hard ceiling)"]].map(([v, label]) => (
            <button key={v} type="button" onClick={() => onSimulate(v)} aria-pressed={usage === v}
              className={`rounded border px-2 py-0.5 text-[11px] ${usage === v ? "border-slate-700 bg-slate-100 font-semibold text-slate-900" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
        <p className="font-semibold text-slate-800">Khi đạt giới hạn cứng:</p>
        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-600">Request sẽ dừng an toàn. Không tự động vượt budget. Hệ thống áp dụng nguyên tắc fail closed để bảo vệ ngân sách.</p>
        {state === "hard" && (
          <div role="alert" className="mt-2 border-t border-red-200 pt-2">
            <p className="mb-1 text-xs font-semibold text-red-700">Trạng thái: Đã đạt giới hạn ngân sách</p>
            <p className="mb-2 text-[11px] text-red-600">Request mới liên quan đến API bị fail closed theo policy.</p>
            <div className="flex items-center gap-2">
              <Button variant="secondary" className="min-h-8 px-2.5 py-1 text-[11px]" onClick={onViewConfig}>Xem cấu hình</Button>
              <Link to={ADMIN_LINKS.overview} className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50">Xem usage</Link>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

// ─── Panel chi tiết, lịch sử, form ──────────────────────────────────────────

function DetailBody({ version }) {
  return (
    <div className="space-y-5 text-xs">
      <p className="flex flex-wrap items-center gap-2 text-slate-500">
        <KindBadge kind={version.kind} /><StatusBadge tone={STATUS_TONE[version.status]}>{version.status}</StatusBadge>
        <span>Tạo bởi: {version.by}</span>
      </p>
      <Link to={`${ADMIN_LINKS.audit}?config=${cfgId(version.v)}`} className="inline-block font-medium text-blue-600 hover:underline">Xem nhật ký liên quan →</Link>
      {version.traceExample && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3.5">
          <p className="mb-0.5 font-semibold text-amber-900">Ví dụ kiểm chứng thực tế:</p>
          <p className="text-amber-800">{version.traceExample.text}</p>
          <Link to={`${ADMIN_LINKS.traces}/${version.traceExample.id}`} className="mt-2 inline-block font-semibold text-blue-700 hover:underline">Xem trace chi tiết →</Link>
        </div>
      )}
      {version.reason && <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-600"><strong className="text-slate-800">Lý do thay đổi:</strong> {version.reason}</p>}
      {GROUPS.map((g) => (
        <section key={g.id} className="rounded-lg border border-slate-200 bg-slate-50/50 p-3">
          <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-800">{g.id === "budget" ? "Ngân sách & Cảnh báo" : g.title}</h3>
          <div className="grid grid-cols-2 gap-2">
            {g.keys.map((k) => (
              <div key={k} className="flex items-center justify-between gap-2 rounded border border-slate-100 bg-white p-2">
                <span className="text-slate-500">{FIELDS[k].label}:</span>
                <span className="font-bold text-slate-900">{fmtVal(k, version.params[k])}</span>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function HistoryBody({ versions, onOpen }) {
  return (
    <ul className="space-y-3">
      {versions.map((v) => (
        <li key={v.v} className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="flex items-center gap-2"><span className="text-sm font-bold text-slate-900">{v.v}</span><KindBadge kind={v.kind} /></span>
            <span className="text-xs text-slate-500">{v.status}</span>
          </div>
          <p className="mb-2 text-xs text-slate-600"><strong>Thay đổi:</strong> {v.changes.length ? v.changes.join(", ") : "Cấu hình gốc"}</p>
          <div className="flex items-center justify-between border-t border-slate-200 pt-2 text-[11px] text-slate-400">
            <span>Tạo bởi: {v.by} ({v.created})</span>
            <button type="button" onClick={() => onOpen(v.v)} className="font-semibold text-blue-600 hover:underline">Xem chi tiết</button>
          </div>
        </li>
      ))}
    </ul>
  );
}

const textareaClass = "w-full rounded-lg border border-[#CBD5E1] bg-white px-3 py-2 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB]";

function EditForm({ form, kind, reason, analysis, onField, onKind, onReason }) {
  const { errors, fieldErrors, impacts, summary } = analysis;
  return (
    <form id="config-form" onSubmit={(e) => e.preventDefault()} noValidate className="space-y-6">
      {errors.length > 0 && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3.5">
          <p className="mb-1 text-xs font-semibold text-red-800">Không thể lưu cấu hình</p>
          <ul className="list-inside list-disc space-y-0.5 pl-1 text-[11px] text-red-700">{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
      <Select label="Loại cấu hình" options={KIND_OPTIONS} value={kind} onChange={(e) => onKind(e.target.value)} />
      <div>
        <label htmlFor="config-reason" className="mb-1 block text-xs font-semibold text-[#334155]">Lý do thay đổi (tùy chọn)</label>
        <textarea id="config-reason" rows={2} className={textareaClass} value={reason} onChange={(e) => onReason(e.target.value)}
          placeholder="Ví dụ: Siết chặt ngưỡng Verifier để nâng cao độ tin cậy..." />
      </div>

      {GROUPS.map((g, i) => (
        <fieldset key={g.id} className="border-t border-slate-200 pt-4">
          <legend className="sr-only">{g.title}</legend>
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-900">{i + 1}. {g.title}</h3>
          <div className="grid grid-cols-2 gap-3">
            {g.keys.map((k) => (
              <Input key={k} type="number" label={`${FIELDS[k].label}${FIELDS[k].unit === "%" ? " (%)" : FIELDS[k].unit ? ` (${FIELDS[k].unit})` : ""} [${FIELDS[k].min}–${FIELDS[k].max}]`}
                value={form[k]} onChange={(e) => onField(k, e.target.value)} error={fieldErrors[k]} />
            ))}
            {g.id === "tokens" && <Input type="number" label="Min retrieval context (cố định)" value={MIN_RETRIEVAL_CONTEXT} disabled readOnly />}
            {g.id === "budget" && <Input type="number" label="Hard ceiling (%) (cố định)" value={HARD_CEILING} disabled readOnly />}
          </div>
        </fieldset>
      ))}

      <section className="border-t border-slate-200 pt-4">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">Ảnh hưởng của thay đổi</h3>
        {impacts.length === 0 ? <p className="text-xs italic text-slate-400">Chưa có thay đổi nào so với cấu hình đang hoạt động.</p> : (
          <ul className="space-y-2">{impacts.map((t) => <li key={t} className="rounded-lg border border-blue-100 bg-blue-50/70 p-2.5 text-xs text-slate-700">{t}</li>)}</ul>
        )}
      </section>
      <section className="border-t border-slate-200 pb-2 pt-4">
        <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-900">Tóm tắt thay đổi</h3>
        {summary.length === 0 ? <p className="text-xs italic text-slate-400">Không có trường nào bị sửa đổi.</p> : (
          <ul className="space-y-1 font-mono text-xs text-slate-800">{summary.map((t) => <li key={t}>• {t}</li>)}</ul>
        )}
      </section>
    </form>
  );
}

// ─── Trang ──────────────────────────────────────────────────────────────────

export default function AdminConfigurationPage() {
  const { configId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast, toastNode } = useToasts();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [usageOverride, setUsageOverride] = useState(null);
  // overlay: null | { type: "edit" | "history" } | { type: "activate" | "restore", v }
  const [overlay, setOverlay] = useState(null);
  const [form, setForm] = useState({});
  const [kind, setKind] = useState("PRODUCTION");
  const [reason, setReason] = useState("");
  const budgetRef = useRef(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return getConfigurationData()
      .then(setData)
      .catch((e) => { setData(null); setError(e.message); })
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const versions = data?.versions ?? [];
  const active = versions.find((v) => v.status === "Đang hoạt động") ?? null;
  const detailKey = (configId || searchParams.get("cfg") || "").replace(/^CFG\s*/i, "").toLowerCase();
  const detail = detailKey ? versions.find((v) => cfgId(v.v).toLowerCase() === detailKey) ?? null : null;
  const target = overlay?.v ? versions.find((v) => v.v === overlay.v) : null;

  const usageParam = Number(searchParams.get("usage"));
  const usage = usageOverride ?? (searchParams.get("usage") !== null && usageParam >= 0 && usageParam <= 100 ? Math.round(usageParam) : data?.budget.used ?? 0);

  const focusBudget = searchParams.get("focus") === "budget";
  useEffect(() => { if (data && focusBudget) budgetRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); }, [data, focusBudget]);

  const closeOverlay = useCallback(() => setOverlay(null), []);
  const openDetail = useCallback((name) => { setOverlay(null); navigate(`${ADMIN_LINKS.configuration}/${cfgId(name)}`); }, [navigate]);
  const closeDetail = useCallback(() => navigate(ADMIN_LINKS.configuration), [navigate]);

  // Kiểm tra và phân tích thay đổi của form so với cấu hình đang hoạt động.
  const analysis = useMemo(() => {
    if (!active) return { errors: [], fieldErrors: {}, impacts: [], summary: [], changed: [], canSubmit: false, values: {} };
    const values = Object.fromEntries(Object.keys(FIELDS).map((k) => [k, form[k] === undefined || form[k] === "" ? NaN : Number(form[k])]));
    const { errors, fieldErrors } = validate(values);
    const changed = changedFields(active.params, values);
    return {
      errors, fieldErrors, changed, values,
      impacts: changed.map((k) => describeImpact(k, active.params[k], values[k])),
      summary: changed.map((k) => `${FIELDS[k].label}: ${fmtVal(k, active.params[k])} → ${fmtVal(k, values[k])}`),
      canSubmit: errors.length === 0 && changed.length > 0,
    };
  }, [form, active]);

  function openEdit() {
    setForm(formFromParams(active.params));
    setKind("PRODUCTION");
    setReason("");
    setOverlay({ type: "edit" });
  }

  function submitNewVersion() {
    if (!analysis.canSubmit) return;
    const name = nextVersionName(versions);
    const production = kind === "PRODUCTION";
    setData((d) => ({ ...d, versions: [{
      v: name, kind, status: production ? "Đang chờ kích hoạt" : "Cấu hình thử nghiệm", created: todayLabel(), by: "System Admin",
      activated: "—", reason: reason.trim(), params: analysis.values,
      changes: analysis.changed.map((k) => `${FIELDS[k].label} ${fmtVal(k, active.params[k])} → ${fmtVal(k, analysis.values[k])}`),
    }, ...d.versions] }));
    setOverlay(null);
    toast(`Đã tạo ${name}. Cấu hình đang hoạt động ${active.v} không bị thay đổi.`, "success");
  }

  function confirmActivation() {
    if (!target) return;
    setData((d) => ({ ...d, versions: d.versions.map((v) => (v.status === "Đang hoạt động" ? { ...v, status: "Đã thay thế" }
      : v.v === target.v ? { ...v, status: "Đang hoạt động", activated: todayLabel(), activatedBy: "System Admin" } : v)) }));
    setOverlay(null);
    toast(`Đã kích hoạt thành công ${target.v}. Toàn bộ request mới sẽ áp dụng cấu hình này.`, "success");
  }

  function confirmRestore() {
    if (!target) return;
    const name = nextVersionName(versions);
    setData((d) => ({ ...d, versions: [{
      v: name, kind: target.kind, status: "Đang chờ kích hoạt", created: todayLabel(), by: "System Admin", activated: "—",
      changes: [`Khôi phục cấu hình từ ${target.v}`], params: { ...target.params },
    }, ...d.versions] }));
    setOverlay(null);
    toast(`Đã tạo ${name} dựa trên giá trị của ${target.v}. Phiên bản đang ở trạng thái chờ kích hoạt.`, "success");
  }

  const small = "min-h-8 px-2.5 py-1 text-xs";

  return (
    <AdminLayout>
      <header className="flex flex-col justify-between gap-3 border-b border-slate-200/70 pb-3 md:flex-row md:items-start">
        <div>
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1.5 text-xs text-slate-500">
            <Link to={ADMIN_LINKS.overview} className="hover:text-blue-600">Tổng quan vận hành</Link>
            <span aria-hidden="true">/</span>
            <span className="font-medium text-slate-900">Ngưỡng &amp; ngân sách API</span>
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Ngưỡng &amp; ngân sách API</h1>
            {active && <StatusBadge tone="success">Cấu hình đang hoạt động: {active.v}</StatusBadge>}
            <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-500">Dữ liệu minh họa</span>
          </div>
          <p className="mt-1 text-[13px] text-slate-500">Quản lý các giới hạn bằng chứng, ngữ cảnh và tài nguyên được FinMind sử dụng khi xử lý truy vấn.</p>
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          <Button variant="secondary" className="text-xs" disabled={!data} onClick={() => setOverlay({ type: "history" })}>Xem lịch sử phiên bản</Button>
          <Button className="text-xs" disabled={!active} onClick={openEdit}>Chỉnh cấu hình</Button>
        </div>
      </header>

      {loading && <Skeleton rows={6} />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}

      {!loading && data && !active && <ErrorState title="Không có cấu hình đang hoạt động" message="Cần kích hoạt một phiên bản cấu hình để hiển thị các ngưỡng." />}

      {!loading && data && active && (
        <>
          <Card>
            <div className="flex flex-col justify-between gap-4 border-b border-slate-100 pb-4 lg:flex-row lg:items-center">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Cấu hình đang hoạt động</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-3">
                  <span className="text-2xl font-bold text-slate-900">{active.v}</span>
                  <StatusBadge tone="success">Đang hoạt động</StatusBadge>
                  <KindBadge kind={active.kind} />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className={small} onClick={() => setOverlay({ type: "history" })}>Xem lịch sử phiên bản</Button>
                <Button variant="ghost" className={small} onClick={() => openDetail(active.v)}>Xem chi tiết {active.v}</Button>
              </div>
            </div>
            <dl className="grid grid-cols-2 gap-4 pt-4 text-xs md:grid-cols-4">
              <div><dt className="mb-0.5 text-slate-400">Ngày kích hoạt:</dt><dd className="font-medium text-slate-700">{active.activated}</dd></div>
              <div><dt className="mb-0.5 text-slate-400">Người kích hoạt:</dt><dd className="font-medium text-slate-700">{active.activatedBy || "—"}</dd></div>
              <div>
                <dt className="mb-0.5 text-slate-400">Corpus tương thích:</dt>
                <dd>{active.corpus ? <Link to={`${ADMIN_LINKS.corpus}?corpus=${active.corpus}`} className="font-medium text-blue-600 hover:underline">Corpus {active.corpus} ↗</Link> : <span className="text-slate-500">—</span>}</dd>
              </div>
              <div><dt className="mb-0.5 text-slate-400">Chế độ áp dụng:</dt><dd className="text-slate-600">Áp dụng trực tiếp cho tất cả request mới</dd></div>
            </dl>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <GroupCard group={GROUPS[0]} params={active.params} />
            <GroupCard group={GROUPS[1]} params={active.params} footer={
              <span className="flex items-center justify-between gap-3">
                <span>Ràng buộc: Rerank limit ≤ Fusion Top-K ≤ Vector limit</span>
                {active.params.rerankLimit <= active.params.fusionTopK && active.params.fusionTopK <= active.params.vectorLimit
                  ? <span className="font-medium text-emerald-600">Hợp lệ</span> : <span className="font-medium text-red-600">Không hợp lệ</span>}
              </span>
            } />
            <GroupCard group={GROUPS[2]} params={active.params} footer={
              <span className="grid grid-cols-2 gap-2 text-xs text-slate-600">
                <span><span className="text-slate-400">Sử dụng trung bình:</span> <span className="font-medium">{fmtNum(data.budget.avgTokens)} token</span></span>
                <span className="text-right"><span className="text-slate-400">Hard ceiling:</span> <span className="font-bold text-slate-900">{fmtNum(active.params.totalCeiling)}</span></span>
              </span>
            } />
            <div ref={budgetRef} className="flex flex-col">
              <BudgetCard budget={data.budget} usage={usage} warnAt={active.params.warningThreshold}
                onSimulate={setUsageOverride} onViewConfig={() => openDetail(active.v)} />
            </div>
          </div>

          <Card title="Lịch sử phiên bản cấu hình" description="Danh sách các phiên bản đã tạo, đang chờ kích hoạt hoặc đã được thay thế."
            action={<span className="text-xs text-slate-400">Tổng cộng: <strong className="text-slate-700">{versions.length}</strong> phiên bản</span>}>
            <div className="-m-1 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-slate-200 bg-slate-50/50 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <tr>
                    {["Phiên bản", "Loại", "Trạng thái", "Ngày tạo", "Người tạo", "Thay đổi", "Ngày kích hoạt", "Thao tác"].map((h) => (
                      <th key={h} scope="col" className={`px-3 py-3 ${h === "Thao tác" ? "text-right" : ""}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {versions.map((v) => (
                    <tr key={v.v} className="hover:bg-slate-50/80">
                      <td className="whitespace-nowrap px-3 py-3 font-bold text-slate-900">{v.v}</td>
                      <td className="whitespace-nowrap px-3 py-3"><KindBadge kind={v.kind} /></td>
                      <td className="whitespace-nowrap px-3 py-3"><StatusBadge tone={STATUS_TONE[v.status]}>{v.status}</StatusBadge></td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-500">{v.created}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-600">{v.by}</td>
                      <td className="max-w-xs truncate px-3 py-3 text-slate-600" title={v.changes.join("; ")}>{v.changes.length ? v.changes.join(", ") : "—"}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-slate-500">{v.activated}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <Button variant="ghost" className={small} onClick={() => openDetail(v.v)}>Xem chi tiết</Button>
                          {v.status === "Đang chờ kích hoạt" && <Button variant="secondary" className={small} onClick={() => setOverlay({ type: "activate", v: v.v })}>Kích hoạt</Button>}
                          {v.status !== "Đang chờ kích hoạt" && v.status !== "Đang hoạt động" && <Button variant="secondary" className={small} onClick={() => setOverlay({ type: "restore", v: v.v })}>Khôi phục</Button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      <footer className="mt-auto border-t border-slate-200 pb-4 pt-4 text-center text-xs text-slate-400">Chỉ dùng cho quản trị vận hành FinMind.</footer>

      <Drawer open={Boolean(detail)} onClose={closeDetail} title={detail ? `Chi tiết cấu hình ${detail.v}` : ""}
        footer={<Button variant="secondary" onClick={closeDetail}>Đóng</Button>}>
        {detail && <DetailBody version={detail} />}
      </Drawer>

      <Drawer open={overlay?.type === "history"} onClose={closeOverlay} title="Lịch sử toàn bộ phiên bản cấu hình"
        footer={<Button variant="secondary" onClick={closeOverlay}>Đóng</Button>}>
        <HistoryBody versions={versions} onOpen={openDetail} />
      </Drawer>

      <Drawer open={overlay?.type === "edit"} onClose={closeOverlay} title="Chỉnh cấu hình hệ thống"
        footer={
          <div className="flex w-full items-center justify-between">
            <Button variant="ghost" onClick={closeOverlay}>Hủy bỏ</Button>
            <Button disabled={!analysis.canSubmit} onClick={submitNewVersion}>Xác nhận và tạo phiên bản mới</Button>
          </div>
        }>
        <p className="mb-4 text-xs text-slate-500">Tạo phiên bản ứng viên kế tiếp. Cấu hình đang hoạt động sẽ không thay đổi.</p>
        <EditForm form={form} kind={kind} reason={reason} analysis={analysis}
          onField={(k, v) => setForm((f) => ({ ...f, [k]: v }))} onKind={setKind} onReason={setReason} />
      </Drawer>

      <Modal open={overlay?.type === "activate" && Boolean(target)} onClose={closeOverlay} title={target ? `Kích hoạt ${target.v}?` : ""}
        footer={<><Button variant="secondary" onClick={closeOverlay}>Hủy</Button><Button onClick={confirmActivation}>Kích hoạt</Button></>}>
        <p className="leading-relaxed">Các request mới đủ điều kiện sẽ sử dụng cấu hình này ngay sau khi kích hoạt. Phiên bản hiện tại sẽ chuyển sang trạng thái "Đã thay thế".</p>
        <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-[11px] text-slate-500">Người kích hoạt: <strong className="text-slate-700">System Admin</strong> (ghi nhận nhật ký kiểm toán bất biến).</p>
      </Modal>

      <Modal open={overlay?.type === "restore" && Boolean(target)} onClose={closeOverlay} title={target ? `Bạn muốn sử dụng lại các giá trị của ${target.v}?` : ""}
        footer={<><Button variant="secondary" onClick={closeOverlay}>Hủy</Button><Button onClick={confirmRestore}>Tạo phiên bản từ giá trị này</Button></>}>
        <p className="leading-relaxed">Hệ thống sẽ sao chép toàn bộ giá trị của phiên bản này và tạo ra một phiên bản mới ở trạng thái "Đang chờ kích hoạt". Các phiên bản trước đó được giữ nguyên, không bị ghi đè.</p>
      </Modal>

      {toastNode}
    </AdminLayout>
  );
}
