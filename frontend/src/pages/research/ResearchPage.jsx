import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "../../app/router.jsx";
import {
  Button,
  Card,
  DataTable,
  Drawer,
  EmptyState,
  Input,
  Modal,
  Select,
  Sidebar,
  Skeleton,
  Spinner,
  StatusBadge,
} from "../../shared/ui/index.js";
import ResearchIcon from "./ResearchIcon.jsx";
import ResearchChat from "./ResearchChat.jsx";
import './researchLayout.css';
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { userMenu } from "../../mocks/componentMock.js";
import { researcherMock } from "../dashboard/mock.js";
import { getStoredResearchHistory, saveStoredResearchHistory } from "./mock.js";
import {
  FACTS,
  formatFact,
  getCompanyCatalog,
  getCompanyFinancials,
  toPeriodCode,
  verification,
} from "../companies/financials.js";

const TICKER = /^[A-Z0-9]{1,10}$/;

const menuPaths = {
  dashboard: "/dashboard",
  companies: "/companies",
  copilot: "/research",
  watchlist: "/watchlist",
  graph: "/graph",
};

export default function ResearchPage() {
  const navigate = useNavigate();
  const { userProfile, logout } = useAuth();
  const [chatResetKey, setChatResetKey] = useState(0);
  const [webHistoryCount, setWebHistoryCount] = useState(0);
  const [webBusy, setWebBusy] = useState(false);
  const [params, setParams] = useSearchParams();
  const messagesEndRef = useRef(null);

  // Mode: "copilot" (Trợ lý hỏi đáp) hoặc "compare" (So sánh chỉ tiêu)
  // The compare tab is hidden from the UI; old ?mode=compare links open the chat.
  const initialMode = "copilot";
  const [activeTab, setActiveTab] = useState(initialMode);

  // Filter context
  const rawCompany = (params.get("company") || "FPT").toUpperCase();
  const validTicker = TICKER.test(rawCompany) ? rawCompany : "FPT";
  const [company, setCompany] = useState(validTicker);

  // "" = chưa chọn; bảng so sánh tự chọn kỳ mới nhất có dữ liệu.
  const [period, setPeriod] = useState(toPeriodCode(params.get("period")));

  // Dữ liệu so sánh lấy từ backend
  const [catalog, setCatalog] = useState([]);
  const [compareData, setCompareData] = useState({});
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState(null);

  // Compare mode second company
  const [compareCompany, setCompareCompany] = useState(
    validTicker === "CMG" ? "FPT" : "CMG"
  );

  // Query and Evaluation State
  const initialQuestion =
    params.get("question") || "Doanh thu FPT FY2025 thay đổi như thế nào?";
  const [currentQuestion, setCurrentQuestion] = useState(initialQuestion);
  const [queryInput, setQueryInput] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAccordionOpen, setIsAccordionOpen] = useState(false);

  // History State (Mô phỏng theo user qua localStorage)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(
    params.get("history") === "1"
  );
  const closeChatHistory = useCallback(() => setHistoryDrawerOpen(false), []);
  const [historyList, setHistoryList] = useState(getStoredResearchHistory);
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState("all");

  // Delete History Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);


  // Synchronize context when URL query params change
  useEffect(() => {
    const pCompany = (params.get("company") || "").toUpperCase();
    if (TICKER.test(pCompany)) {
      setCompany(pCompany);
    }
    const pPeriod = toPeriodCode(params.get("period"));
    if (pPeriod) {
      setPeriod(pPeriod);
    }
    const pQuestion = params.get("question");
    if (pQuestion) {
      setCurrentQuestion(pQuestion);
    }
    if (params.get("history") === "1") {
      setHistoryDrawerOpen(true);
    }
  }, [params]);

  // Auto scroll to bottom when question or evaluation updates
  useEffect(() => {
    if (currentQuestion) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [currentQuestion, evaluation]);

  // Handle Form Submission
  const handleSubmitQuery = (e) => {
    e?.preventDefault();
    const q = queryInput.trim();
    if (!q) return;
    setCurrentQuestion(q);
    setQueryInput("");
  };

  // Switch to new research (empty prompt state)
  const handleNewResearch = () => {
    if (webBusy) return;
    setActiveTab("copilot");
    setChatResetKey((value) => value + 1);
    setCurrentQuestion("");
    setQueryInput("");
    setEvaluation(null);
  };

  // Danh mục doanh nghiệp cho bảng so sánh (chỉ mã đã có BCTC)
  useEffect(() => {
    if (activeTab !== "compare" || catalog.length) return;
    getCompanyCatalog()
      .then((items) => setCatalog(items.filter((item) => item.latestPeriod)))
      .catch((caught) => setCompareError(caught.message));
  }, [activeTab, catalog.length]);

  // Số liệu BCTC của hai doanh nghiệp đang so sánh
  useEffect(() => {
    if (activeTab !== "compare") return;
    let cancelled = false;
    setCompareLoading(true);
    setCompareError(null);
    Promise.all([company, compareCompany].map(getCompanyFinancials))
      .then(([first, second]) => {
        if (!cancelled) setCompareData({ [company]: first, [compareCompany]: second });
      })
      .catch((caught) => { if (!cancelled) setCompareError(caught.message); })
      .finally(() => { if (!cancelled) setCompareLoading(false); });
    return () => { cancelled = true; };
  }, [activeTab, company, compareCompany]);

  // History Pin / Unpin
  const handleTogglePin = (e, id) => {
    e.stopPropagation();
    setHistoryList((prev) => {
      const updated = prev.map((item) =>
        item.id === id ? { ...item, isPinned: !item.isPinned } : item
      );
      saveStoredResearchHistory(updated);
      return updated;
    });
  };

  // History Delete Request
  const handleRequestDelete = (e, item) => {
    e.stopPropagation();
    setItemToDelete(item);
    setDeleteModalOpen(true);
  };

  const handleRequestDeleteAll = () => {
    setItemToDelete("ALL");
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = () => {
    if (itemToDelete === "ALL") {
      setHistoryList([]);
      saveStoredResearchHistory([]);
    } else if (itemToDelete) {
      setHistoryList((prev) => {
        const updated = prev.filter((item) => item.id !== itemToDelete.id);
        saveStoredResearchHistory(updated);
        return updated;
      });
    }
    setDeleteModalOpen(false);
    setItemToDelete(null);
  };

  // Prepare options for Selects
  const companyOptions = [
    ...catalog,
    ...[company, compareCompany].filter((t) => !catalog.some((c) => c.id === t)).map((t) => ({ id: t, name: t })),
  ].map((c) => ({ value: c.id, label: `${c.id} · ${c.name}` }));

  const firstData = compareData[company];
  const secondData = compareData[compareCompany];
  const periodOptions = (firstData?.periods || secondData?.periods || []).map((p) => ({
    value: p.period,
    label: p.label,
  }));

  // Kỳ chưa chọn hoặc không có dữ liệu thì dùng kỳ mới nhất của doanh nghiệp thứ nhất.
  useEffect(() => {
    if (periodOptions.length && !periodOptions.some((p) => p.value === period)) {
      setPeriod(periodOptions[0].value);
    }
  }, [periodOptions, period]);

  const periodLabel = periodOptions.find((p) => p.value === period)?.label || period || "—";
  const firstPeriod = firstData?.periods.find((p) => p.period === period);
  const secondPeriod = secondData?.periods.find((p) => p.period === period);

  const statusBadge = (data) => {
    if (!data) return <StatusBadge tone="neutral">Không có số liệu kỳ này</StatusBadge>;
    const state = verification(data.status);
    return <StatusBadge tone={state.tone}>{state.label}</StatusBadge>;
  };

  const compareRows = [
    ...FACTS.map((fact) => {
      const val1 = formatFact(firstPeriod?.facts[fact.key], fact.kind);
      const val2 = formatFact(secondPeriod?.facts[fact.key], fact.kind);
      return {
        id: fact.key,
        metricName: fact.label,
        val1,
        val2,
        note: fact.key === "roe" || fact.key === "roa"
          ? "Chỉ số từ nguồn dữ liệu, chưa đối chiếu PDF"
          : fact.kind === "growth"
          ? "So với cùng kỳ năm trước"
          : val1 === "—" || val2 === "—"
          ? "Thiếu số liệu ở một bên"
          : "Theo trạng thái đối chiếu từng kỳ",
      };
    }),
    {
      id: "evidenceStatus",
      metricName: "Đối chiếu với BCTC gốc",
      val1: statusBadge(firstPeriod),
      val2: statusBadge(secondPeriod),
      note: "So số liệu với file PDF đã công bố",
    },
  ];

  // BCTC gốc của kỳ đang so sánh, để người đọc tự kiểm tra
  const compareReports = [[company, firstData], [compareCompany, secondData]].flatMap(([ticker, data]) =>
    (data?.reports || []).filter((r) => r.period === period && r.url).map((r) => ({ ...r, ticker })));

  const compareColumns = [
    {
      key: "metricName",
      title: "Chỉ tiêu tài chính",
      render: (r) => (
        <span className="font-semibold text-slate-900">{r.metricName}</span>
      ),
    },
    {
      key: "val1",
      title: `${company} (${periodLabel})`,
      render: (r) => (
        <span className="font-mono font-medium text-slate-800">{r.val1}</span>
      ),
    },
    {
      key: "val2",
      title: `${compareCompany} (${periodLabel})`,
      render: (r) => (
        <span className="font-mono font-medium text-slate-800">{r.val2}</span>
      ),
    },
    {
      key: "note",
      title: "Ghi chú",
      render: (r) => <span className="text-xs text-slate-500">{r.note}</span>,
    },
  ];

  // Filter history items & sort: Pinned items first
  const filteredHistory = historyList
    .filter((item) => {
      const matchComp =
        historyFilter === "all" || item.company === historyFilter;
      const query = historySearch.trim().toLowerCase();
      const matchSearch =
        !query ||
        item.question.toLowerCase().includes(query) ||
        item.company.toLowerCase().includes(query);
      return matchComp && matchSearch;
    })
    .sort((a, b) => (b.isPinned ? 1 : 0) - (a.isPinned ? 1 : 0));

  return (
    <div className="fm-workspace fm-research research-page flex h-screen bg-[#F8FAFC] text-[#0F172A] overflow-hidden">
      {/* 1. Shared Researcher Sidebar */}
      <Sidebar
        groups={userMenu}
        renderIcon={item => <ResearchIcon name={item.id} />}
        activeId="copilot"
        onSelect={(id) => navigate(menuPaths[id] || "/dashboard")}
        profile={userProfile}
        onProfile={() => navigate("/profile")}
        onLogout={async () => { await logout(); navigate("/login"); }}
      />

      {/* 2. Main Research Viewport */}
      <main className="research-page-main flex-1 min-w-0 flex flex-col h-screen overflow-hidden bg-[#F8FAFC]">
        {/* Top Header */}
        <header className="research-page-header shrink-0 bg-white/95 backdrop-blur-md border-b border-slate-200 px-4 sm:px-6 py-3 z-10">
          <div className="research-header-inner mx-auto flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-slate-900">
                Nghiên cứu
              </h1>
              <span className="research-header-caption">{activeTab === 'compare' ? 'So sánh BCTC' : 'Tra cứu doanh nghiệp có nguồn'}</span>
            </div>

            {/* Quick Actions & Tab Switcher */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex min-w-0 max-w-full flex-wrap bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                <button
                  type="button"
                  onClick={() => setActiveTab("copilot")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    activeTab === "copilot"
                      ? "bg-white text-blue-600 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <ResearchIcon name="copilot" /> Hỏi FinMind
                </button>
              </div>

              <Button
                variant="secondary"
                size="sm"
                disabled={webBusy}
                onClick={() => setHistoryDrawerOpen(true)}
                className="gap-1.5 text-xs"
              >
                <ResearchIcon name="history" />
                <span>Lịch sử ({activeTab === "copilot" ? webHistoryCount : historyList.length})</span>
              </Button>

              <Button
                variant="primary"
                size="sm"
                disabled={webBusy}
                aria-label="Nghiên cứu mới"
                onClick={handleNewResearch}
                className="gap-1 text-xs"
              >
                <ResearchIcon name="plus" />
                <span className="hidden sm:inline">Nghiên cứu mới</span>
              </Button>
            </div>
          </div>
        </header>

        {activeTab === "compare" && (<>
        {/* Global Context Bar: Company & Period Selector */}
        <section className="shrink-0 bg-white border-b border-slate-200 px-6 py-2.5 shadow-2xs z-10">
          <div className="max-w-5xl mx-auto flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  DOANH NGHIỆP:
                </span>
                <div className="w-52">
                  <Select
                    value={company}
                    onChange={(val) => setCompany(val)}
                    options={companyOptions}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  KỲ BÁO CÁO:
                </span>
                <div className="w-56">
                  <Select
                    value={period}
                    onChange={(val) => setPeriod(val)}
                    options={periodOptions}
                  />
                </div>
              </div>

              {activeTab === "compare" && (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    So sánh với:
                  </span>
                  <div className="w-52">
                    <Select
                      value={compareCompany}
                      onChange={(val) => setCompareCompany(val)}
                      options={companyOptions.filter((c) => c.value !== company)}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* BCTC gốc của kỳ đang so sánh */}
            {compareReports.length > 0 && (
              <div className="flex flex-wrap items-center gap-3">
                {compareReports.map((report) => (
                  <a
                    key={report.id}
                    href={report.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-blue-600 font-semibold hover:underline"
                  >
                    BCTC gốc {report.ticker} →
                  </a>
                ))}
              </div>
            )}
          </div>
        </section>

        </>)}

        {/* ─── SCROLLABLE MIDDLE CONVERSATION & ANALYSIS CANVAS ─── */}
        <div className={`research-canvas flex-1 min-w-0 min-h-0 px-3 sm:px-6 py-3 ${activeTab === "copilot" ? "research-canvas-chat flex flex-col" : "overflow-y-auto"}`}>
          <div className={`research-content mx-auto w-full ${activeTab === "copilot" ? "flex flex-1 min-h-0 flex-col" : "space-y-6"}`}>
            {activeTab === "copilot" && (
              <ResearchChat historyOpen={historyDrawerOpen}
                onHistoryClose={closeChatHistory} resetKey={chatResetKey}
                onHistoryCount={setWebHistoryCount} onBusyChange={setWebBusy} />
            )}

            {/* TAB 2: BẢNG SO SÁNH CHỈ TIÊU (COMPARE VIEW) */}
            {activeTab === "compare" && (
              <div className="space-y-6">
                {compareError && (
                  <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-800">
                    {compareError}
                  </p>
                )}
                {[firstPeriod, secondPeriod].some((p) => p?.status === "MISMATCH") && (
                  <p role="note" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900">
                    Có số liệu lệch so với BCTC gốc ở kỳ này. Hãy mở tài liệu gốc để kiểm tra trước khi dùng.
                  </p>
                )}
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
                    <div>
                      <h2 className="text-base font-bold text-slate-900">
                        Đối chiếu chỉ tiêu: {company} vs {compareCompany}
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Kỳ báo cáo: {periodLabel} · Số liệu BCTC đã lưu trong hệ thống
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 font-medium">
                        Đơn vị: tỷ đồng / %
                      </span>
                    </div>
                  </div>

                  <div className="mt-4">
                    {compareLoading ? <Skeleton rows={6} /> : <DataTable columns={compareColumns} rows={compareRows} />}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {activeTab === "compare" && (
          <div className="shrink-0 border-t border-slate-200 bg-white p-4 text-center text-xs text-slate-500">
            Số liệu từ BCTC đã thu thập · Không phải khuyến nghị đầu tư
          </div>
        )}

        {/* ───────────────────────────────────────────────────────────── */}
        {/* 5. HISTORY DRAWER (XEM / XÓA / PIN / UNPIN)                  */}
        {/* ───────────────────────────────────────────────────────────── */}
        {activeTab === "compare" && (
        <Drawer
          open={historyDrawerOpen}
          title="LỊCH SỬ NGHIÊN CỨU"
          onClose={() => setHistoryDrawerOpen(false)}
        >
          <div className="space-y-4">
            {/* Top Toolbar: Search & Clear All */}
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <Input
                  type="search"
                  placeholder="Tìm câu hỏi trong lịch sử..."
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                />
              </div>
              {historyList.length > 0 && (
                <button
                  type="button"
                  onClick={handleRequestDeleteAll}
                  className="px-2.5 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 border border-rose-200 rounded-lg transition-colors shrink-0 cursor-pointer"
                  title="Xóa toàn bộ lịch sử nghiên cứu"
                >
                  Xóa hết
                </button>
              )}
            </div>

            {/* Filter Chips */}
            <div className="flex gap-1.5 overflow-x-auto pb-1 text-xs">
              {["all", "FPT", "VCB", "MBB", "TCB", "CMG"].map((ticker) => (
                <button
                  key={ticker}
                  type="button"
                  onClick={() => setHistoryFilter(ticker)}
                  className={`px-2.5 py-1 rounded-full font-medium shrink-0 transition-colors cursor-pointer ${
                    historyFilter === ticker
                      ? "bg-blue-600 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                  }`}
                >
                  {ticker === "all" ? "Tất cả" : ticker}
                </button>
              ))}
            </div>

            {/* History Items List */}
            <div className="space-y-2">
              {filteredHistory.map((item) => (
                <div
                  key={item.id}
                  onClick={() => {
                    setCompany(item.company);
                    setPeriod(item.period || "FY2025");
                    setCurrentQuestion(item.question);
                    setHistoryDrawerOpen(false);
                  }}
                  className={`p-3 rounded-lg border transition-all cursor-pointer shadow-2xs group relative ${
                    item.isPinned
                      ? "bg-blue-50/40 border-blue-300"
                      : "bg-white border-slate-200 hover:border-blue-300 hover:bg-blue-50/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-bold text-slate-500 uppercase">
                      {item.company} · {item.period || "FY2025"}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={(e) => handleTogglePin(e, item.id)}
                        className={`p-1 rounded text-xs transition-colors cursor-pointer ${
                          item.isPinned
                            ? "text-blue-600 hover:bg-blue-100 font-bold"
                            : "text-slate-400 hover:text-blue-600 hover:bg-slate-100"
                        }`}
                        title={item.isPinned ? "Bỏ ghim phiên này" : "Ghim lên đầu"}
                      >
                        {item.isPinned ? "📌" : "📍"}
                      </button>

                      <button
                        type="button"
                        onClick={(e) => handleRequestDelete(e, item)}
                        className="p-1 rounded text-xs text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                        title="Xóa phiên này"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>

                  <p className="text-xs font-semibold text-slate-900 leading-snug">
                    {item.question}
                  </p>

                  <div className="flex items-center justify-between mt-2 text-[11px]">
                    <span className="text-slate-400">{item.time}</span>
                    <StatusBadge
                      tone={
                        item.status === "verified"
                          ? "success"
                          : item.status === "partial"
                          ? "warning"
                          : "neutral"
                      }
                    >
                      {item.statusLabel}
                    </StatusBadge>
                  </div>
                </div>
              ))}

              {filteredHistory.length === 0 && (
                <EmptyState title="Không tìm thấy phiên nghiên cứu phù hợp" />
              )}
            </div>
          </div>
        </Drawer>
        )}

        {/* ───────────────────────────────────────────────────────────── */}
        {/* 6. MODAL XÁC NHẬN XÓA LỊCH SỬ                                */}
        {/* ───────────────────────────────────────────────────────────── */}
        <Modal
          open={deleteModalOpen}
          title={
            itemToDelete === "ALL"
              ? "Xóa toàn bộ lịch sử nghiên cứu"
              : "Xác nhận xóa phiên nghiên cứu"
          }
          onClose={() => setDeleteModalOpen(false)}
          footer={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setDeleteModalOpen(false)}>
                Hủy
              </Button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white text-xs font-semibold hover:bg-rose-700 transition-colors cursor-pointer"
              >
                Xác nhận xóa
              </button>
            </div>
          }
        >
          <p className="text-sm text-slate-600">
            {itemToDelete === "ALL"
              ? "Bạn có chắc chắn muốn xóa toàn bộ lịch sử nghiên cứu? Hành động này sẽ dọn sạch danh sách và không thể hoàn tác."
              : `Bạn có chắc muốn xóa phiên nghiên cứu: "${itemToDelete?.question}" khỏi danh sách lịch sử?`}
          </p>
        </Modal>
      </main>
    </div>
  );
}
