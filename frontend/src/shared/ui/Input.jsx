import { useId } from "react";
import ErrorText from "./ErrorText.jsx";

export default function Input({ label, error, hint, id, className = "", ...props }) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;
  return (
    <div className={className}>
      {label && <label htmlFor={inputId} className="mb-1 block text-xs font-semibold text-[#334155]">{label}</label>}
      <input id={inputId} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}
        className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-[#0F172A] placeholder:text-[#94A3B8] focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB] disabled:bg-[#F1F5F9] ${error ? "border-[#DC2626]" : "border-[#CBD5E1]"}`}
        {...props} />
      {hint && !error && <p className="mt-1 text-xs text-[#64748B]">{hint}</p>}
      <ErrorText id={errorId}>{error}</ErrorText>
    </div>
  );
}
