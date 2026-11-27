export default function Card({ title, description, action, children, className = "", id }) {
  return (
    <section id={id} className={`fm-card rounded-xl border border-[#E2E8F0] bg-white shadow-sm ${className}`}>
      {(title || description || action) && (
        <div className="fm-card-heading flex flex-wrap items-start justify-between gap-3 border-b border-[#F1F5F9] px-5 py-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-[#0F172A]">{title}</h2>}
            {description && <p className="mt-1 text-xs text-[#64748B]">{description}</p>}
          </div>
          {action}
        </div>
      )}
      <div className="fm-card-body p-5">{children}</div>
    </section>
  );
}
