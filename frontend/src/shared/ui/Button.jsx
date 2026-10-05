import Spinner from "./Spinner.jsx";

const styles = {
  primary: "border-[#2563EB] bg-[#2563EB] text-white hover:bg-[#1D4ED8]",
  secondary: "border-[#E2E8F0] bg-white text-[#334155] hover:bg-[#F8FAFC]",
  danger: "border-[#DC2626] bg-[#DC2626] text-white hover:bg-[#B91C1C]",
  ghost: "border-transparent bg-transparent text-[#2563EB] hover:bg-[#EFF6FF]",
};

export default function Button({ children, variant = "primary", loading = false, disabled = false, className = "", type = "button", ...props }) {
  return (
    <button type={type} disabled={disabled || loading}
      className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2563EB] disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant] || styles.primary} ${className}`}
      {...props}>
      {loading && <Spinner size="small" label="" />}
      {children}
    </button>
  );
}
