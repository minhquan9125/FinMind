import { useEffect, useState } from "react";
import {
  Button, Card, DataTable, Drawer, EmptyState, ErrorState, ErrorText,
  FilterBar, Input, Modal, Select, Sidebar, Skeleton, Spinner, Stat, StatusBadge,
} from "../shared/ui/index.js";
import { adminMenu, getMockRows, mockDatasets, userMenu } from "../mocks/componentMock.js";

const datasetOptions = [
  { value: "companies", label: "User · Doanh nghiệp" },
  { value: "watchlist", label: "User · Watchlist" },
  { value: "sources", label: "Admin · Sources" },
  { value: "traces", label: "Admin · Traces" },
  { value: "corpora", label: "Admin · Corpus" },
  { value: "configs", label: "Admin · Cấu hình" },
];

const statusColumn = { key: "status", label: "Trạng thái", render: (row) => <StatusBadge tone={row.tone}>{row.status}</StatusBadge> };
const columnsByDataset = {
  companies: [{ key: "id", label: "Mã" }, { key: "name", label: "Doanh nghiệp" }, { key: "sector", label: "Ngành" }, statusColumn],
  watchlist: [{ key: "id", label: "Mã" }, { key: "name", label: "Doanh nghiệp" }, { key: "sector", label: "Ngành" }, statusColumn],
  sources: [{ key: "name", label: "Tên nguồn" }, { key: "type", label: "Loại nguồn" }, statusColumn],
  traces: [{ key: "id", label: "Mã trace" }, { key: "company", label: "Doanh nghiệp" }, statusColumn],
  corpora: [{ key: "id", label: "Phiên bản" }, { key: "name", label: "Tên" }, statusColumn],
  configs: [{ key: "id", label: "Phiên bản cấu hình" }, statusColumn],
};

export default function ComponentPreview() {
  const [menuMode, setMenuMode] = useState("user");
  const [activeId, setActiveId] = useState("dashboard");
  const [fixtureState, setFixtureState] = useState("success");
  const [dataset, setDataset] = useState("sources");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({ search: "", status: "" });
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sampleInput, setSampleInput] = useState("");

  useEffect(() => {
    if (fixtureState === "loading") {
      setLoading(true);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMockRows(dataset, fixtureState)
      .then((data) => { if (!cancelled) setRows(data); })
      .catch((caught) => { if (!cancelled) setError(caught.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [dataset, fixtureState]);

  const statusOptions = [...new Set(mockDatasets[dataset].success.map((row) => row.status))];
  const filterFields = [
    { key: "search", label: "Tìm trong bảng", type: "text", placeholder: "Nhập từ khóa..." },
    { key: "status", label: "Trạng thái", type: "select", options: [
      { value: "", label: "Tất cả trạng thái" },
      ...statusOptions.map((status) => ({ value: status, label: status })),
    ] },
  ];
  const visibleRows = rows.filter((row) =>
    Object.values(row).some((value) => String(value).toLowerCase().includes(filters.search.toLowerCase())) &&
    (!filters.status || row.status === filters.status)
  );

  function changeDataset(value) {
    setDataset(value);
    setFilters({ search: "", status: "" });
  }

  function changeMenu(mode) {
    setMenuMode(mode);
    setActiveId(mode === "user" ? "dashboard" : "overview");
  }

  return (
    <div className="flex min-h-screen bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={menuMode === "user" ? userMenu : adminMenu} activeId={activeId} onSelect={setActiveId}
        badge={menuMode === "admin" ? "ADMIN" : undefined}
        profile={menuMode === "admin" ? { initials: "AD", name: "Quản trị viên", role: "System Admin" } : { initials: "NA", name: "Nguyễn Văn A", role: "Nhà nghiên cứu" }} />
      <main className="min-w-0 flex-1 space-y-5 p-4 md:p-8">
        <header>
          <p className="text-xs font-semibold uppercase tracking-wide text-[#2563EB]">Component preview · Dữ liệu minh họa</p>
          <h1 className="mt-1 text-2xl font-bold">Shared UI FinMind</h1>
          <p className="mt-1 text-sm text-[#64748B]">Thử component và trạng thái mock. Các mục menu chỉ đổi active, chưa chuyển page.</p>
        </header>

        <Card title="Sidebar và SidebarItem" description={`Mục đang chọn: ${activeId}`}>
          <div className="flex flex-wrap gap-2">
            <Button variant={menuMode === "user" ? "primary" : "secondary"} onClick={() => changeMenu("user")}>Menu User</Button>
            <Button variant={menuMode === "admin" ? "primary" : "secondary"} onClick={() => changeMenu("admin")}>Menu Admin</Button>
          </div>
        </Card>

        <Card title="Button, Input, Select, StatusBadge">
          <div className="flex flex-wrap gap-2">
            <Button>Chính</Button><Button variant="secondary">Phụ</Button><Button variant="ghost">Liên kết</Button>
            <Button variant="danger">Nguy hiểm</Button><Button disabled>Disabled</Button><Button loading>Đang xử lý</Button>
          </div>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <Input label="Tên nguồn" placeholder="Nhập tên nguồn..." value={sampleInput} onChange={(event) => setSampleInput(event.target.value)} />
            <Select label="Loại nguồn" defaultValue="website" options={[{ value: "website", label: "Website" }, { value: "file", label: "Tệp" }]} />
            <Input label="Ví dụ lỗi form" value="" readOnly error="Vui lòng nhập tên nguồn." />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone="success">Hoạt động</StatusBadge><StatusBadge tone="warning">Tạm dừng</StatusBadge>
            <StatusBadge tone="error">Thất bại</StatusBadge><StatusBadge tone="info">Đang xử lý</StatusBadge>
            <StatusBadge>Chưa kiểm tra</StatusBadge>
          </div>
        </Card>

        <Card title="FilterBar và DataTable" description="Chọn bộ mock từ giao diện tham khảo User/Admin. Đây là dữ liệu minh họa.">
          <div className="mb-4 max-w-sm">
            <Select label="Bộ dữ liệu mẫu" options={datasetOptions} value={dataset} onChange={(event) => changeDataset(event.target.value)} />
          </div>
          <FilterBar filters={filterFields} values={filters}
            onChange={(key, value) => setFilters((current) => ({ ...current, [key]: value }))}
            onReset={() => setFilters({ search: "", status: "" })} />
          <div className="my-4 flex flex-wrap gap-2">
            {["success", "empty", "error", "loading"].map((state) =>
              <Button key={state} variant={fixtureState === state ? "primary" : "secondary"} onClick={() => setFixtureState(state)}>{state}</Button>
            )}
          </div>
          <p className="mb-2 text-xs text-[#64748B]">{fixtureState === "success" ? `${visibleRows.length} / ${mockDatasets[dataset].success.length} bản ghi minh họa` : `Trạng thái: ${fixtureState}`}</p>
          <DataTable columns={columnsByDataset[dataset]} rows={visibleRows} loading={loading} error={error}
            emptyMessage="Không có dữ liệu phù hợp" onRetry={() => setFixtureState("success")} />
        </Card>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card title="EmptyState và ErrorState">
            <EmptyState title="Chưa có doanh nghiệp theo dõi" description="Thêm một doanh nghiệp để xem ở đây." />
            <div className="mt-3"><ErrorState title="Không thể tải dữ liệu" message="Lỗi minh họa từ fixture." /></div>
          </Card>
          <Card title="Spinner, Skeleton, Stat và ErrorText">
            <Spinner /><div className="mt-3"><Skeleton rows={2} /></div>
            <div className="mt-3"><Stat label="Bộ dữ liệu mẫu" value={datasetOptions.length} note="User và Admin" /></div>
            <ErrorText>Thông báo lỗi ngắn cho form.</ErrorText>
          </Card>
        </div>

        <Card title="Modal và Drawer">
          <div className="flex gap-2">
            <Button onClick={() => setModalOpen(true)}>Mở Modal</Button>
            <Button variant="secondary" onClick={() => setDrawerOpen(true)}>Mở Drawer</Button>
          </div>
        </Card>
      </main>

      <Modal open={modalOpen} title="Xác nhận thao tác" onClose={() => setModalOpen(false)}
        footer={<><Button variant="secondary" onClick={() => setModalOpen(false)}>Hủy</Button><Button onClick={() => setModalOpen(false)}>Xác nhận</Button></>}>
        Đây là nội dung minh họa. Không có dữ liệu nào được ghi.
      </Modal>
      <Drawer open={drawerOpen} title="Chi tiết nguồn dữ liệu" onClose={() => setDrawerOpen(false)}
        footer={<Button onClick={() => setDrawerOpen(false)}>Đóng</Button>}>
        <p>FPT Investor Relations</p><p className="mt-2 text-[#64748B]">Drawer dùng cho chi tiết nguồn, trace hoặc citation.</p>
      </Drawer>
    </div>
  );
}
