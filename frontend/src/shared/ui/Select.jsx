import { useId } from "react";
import ErrorText from "./ErrorText.jsx";

export default function Select({ label, options = [], error, id, className = "", ...props }) {
  const generatedId = useId();
  const selectId = id || generatedId;
  const errorId = `${selectId}-error`;
  return (
    <div className={className}>
      {label && <label htmlFor={selectId} className="mb-1 block text-xs font-semibold text-[#334155]">{label}</label>}
      <select id={selectId} aria-invalid={Boolean(error)} aria-describedby={error ? errorId : undefined}
        className={`w-full rounded-lg border bg-white px-3 py-2 text-sm text-[#0F172A] focus:border-[#2563EB] focus:outline-none focus:ring-1 focus:ring-[#2563EB] disabled:bg-[#F1F5F9] ${error ? "border-[#DC2626]" : "border-[#CBD5E1]"}`}
        {...props}>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <ErrorText id={errorId}>{error}</ErrorText>
    </div>
  );
}
