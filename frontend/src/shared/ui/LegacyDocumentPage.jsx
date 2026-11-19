import { Link } from "../../app/router.jsx";
import UserShell from "./UserShell.jsx";
import Card from "./Card.jsx";
import EmptyState from "./EmptyState.jsx";
import StatusBadge from "./StatusBadge.jsx";

// These routes previously contained comments only. Do not present a working
// uploader or search form before their document APIs have been implemented.
export default function LegacyDocumentPage({ title, description }) {
  return <UserShell className="fm-legacy">
    <main>
      <Link to="/dashboard" className="text-sm text-blue-700">← Về tổng quan</Link>
      <header className="my-6 space-y-2">
        <StatusBadge tone="neutral">Luồng tài liệu thử nghiệm</StatusBadge>
        <h1>{title}</h1>
        <p className="text-sm text-slate-600">{description}</p>
      </header>
      <Card>
        <EmptyState title="Chức năng chưa được triển khai"
          description="Luồng tài liệu riêng này chưa có phần xử lý trong phiên bản hiện tại. Bạn có thể dùng Hỏi FinMind để tra cứu kho dữ liệu đã được nạp."
          action={<Link to="/research" className="inline-flex min-h-10 items-center rounded-lg bg-blue-700 px-4 text-sm text-white">Mở Hỏi FinMind</Link>} />
      </Card>
    </main>
  </UserShell>;
}
