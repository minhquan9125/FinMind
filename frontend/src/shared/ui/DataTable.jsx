import EmptyState from "./EmptyState.jsx";
import ErrorState from "./ErrorState.jsx";
import Skeleton from "./Skeleton.jsx";

// columns: [{ key: "name", label: "Tên" }, { key: "status", label: "Trạng thái", render: (row) => ... }]
export default function DataTable({ columns = [], rows = [], loading = false, error = null, emptyMessage = "Chưa có dữ liệu", onRetry }) {
  if (loading) return <Skeleton rows={4} />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (rows.length === 0) return <EmptyState title={emptyMessage} />;

  return (
    <div className="overflow-x-auto rounded-xl border border-[#E2E8F0] bg-white">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-[#F8FAFC] text-[#64748B]">
          <tr>{columns.map((column) => <th key={column.key} scope="col" className="whitespace-nowrap px-4 py-3 font-semibold">{column.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-[#F1F5F9]">
          {rows.map((row, index) => (
            <tr key={row.id ?? index} className="hover:bg-[#F8FAFC]">
              {columns.map((column) => (
                <td key={column.key} className="px-4 py-3 text-[#334155]">
                  {column.render ? column.render(row) : row[column.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
