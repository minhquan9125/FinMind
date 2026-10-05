const colors = {
  success: "bg-[#DCFCE7] text-[#166534]",
  warning: "bg-[#FEF3C7] text-[#92400E]",
  error: "bg-[#FEE2E2] text-[#B91C1C]",
  info: "bg-[#DBEAFE] text-[#1D4ED8]",
  neutral: "bg-[#F1F5F9] text-[#475569]",
};

export default function StatusBadge({ children, tone = "neutral" }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${colors[tone] || colors.neutral}`}>{children}</span>;
}
