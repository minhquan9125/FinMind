export default function Stat({ label, value, note }) {
  return (
    <div className="rounded-xl border border-[#E2E8F0] bg-white p-4">
      <p className="text-xs text-[#64748B]">{label}</p>
      <strong className="mt-2 block text-xl text-[#0F172A]">{value}</strong>
      {note && <p className="mt-1 text-xs text-[#64748B]">{note}</p>}
    </div>
  );
}
