export default function Spinner({ size = "normal", label = "Đang tải" }) {
  const sizeClass = size === "small" ? "h-4 w-4" : "h-6 w-6";
  return (
    <span role="status" aria-label={label || "Đang tải"} className="inline-flex items-center gap-2">
      <span aria-hidden="true" className={`${sizeClass} animate-spin rounded-full border-2 border-current border-r-transparent`} />
      {label && <span className="text-sm">{label}</span>}
    </span>
  );
}
