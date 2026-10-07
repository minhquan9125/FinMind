import { useEffect, useRef, useState } from "react";
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
import { userMenu } from "../../mocks/componentMock.js";
import { researcherMock } from "../dashboard/mock.js";
import {
  companyDirectory,
  comparisonMetricsList,
  companyFinancialFacts,
  evaluateResearchQuery,
  getCompanyMeta,
  getStoredFeedback,
  getStoredResearchHistory,
  researchCompanyCatalog,
  researchPeriods,
  saveFeedbackItem,
  saveStoredResearchHistory,
} from "./mock.js";

const menuPaths = {
  dashboard: "/dashboard",
  companies: "/companies",
  copilot: "/research",
  watchlist: "/watchlist",
  graph: "/graph",
};

export default function ResearchPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const messagesEndRef = useRef(null);

  // Mode: "copilot" (Trợ lý hỏi đáp) hoặc "compare" (So sánh chỉ tiêu)
  const initialMode = params.get("mode") === "compare" ? "compare" : "copilot";
  const [activeTab, setActiveTab] = useState(initialMode);

  // Filter context
  const rawCompany = (params.get("company") || "FPT").toUpperCase();
  const validTicker = researchCompanyCatalog.some((c) => c.id === rawCompany)
    ? rawCompany
    : "FPT";
  const [company, setCompany] = useState(validTicker);

  const rawPeriod = params.get("period") || "FY2025";
  const validPeriod = researchPeriods.some((p) => p.value === rawPeriod)
    ? rawPeriod
    : "FY2025";
  const [period, setPeriod] = useState(validPeriod);

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

  // Evidence Drawer
  const [evidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(false);

  // History State (Mô phỏng theo user qua localStorage)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(
    params.get("history") === "1"
  );
  const [historyList, setHistoryList] = useState(getStoredResearchHistory);
  const [historySearch, setHistorySearch] = useState("");
  const [historyFilter, setHistoryFilter] = useState("all");

  // Delete History Modal State
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);

  // Feedback State (Đánh giá hữu ích / cần cải thiện bằng mock)
  const [feedbackRating, setFeedbackRating] = useState(null);
  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackReason, setFeedbackReason] = useState("Số liệu chưa chính xác");
  const [feedbackNote, setFeedbackNote] = useState("");
  const [feedbackToast, setFeedbackToast] = useState(null);

  // Synchronize context when URL query params change
  useEffect(() => {
    const pCompany = (params.get("company") || "").toUpperCase();
    if (pCompany && researchCompanyCatalog.some((c) => c.id === pCompany)) {
      setCompany(pCompany);
    }
    const pPeriod = params.get("period");
    if (pPeriod && researchPeriods.some((p) => p.value === pPeriod)) {
      setPeriod(pPeriod);
    }
    const pQuestion = params.get("question");
    if (pQuestion) {
      setCurrentQuestion(pQuestion);
    }
    if (params.get("history") === "1") {
      setHistoryDrawerOpen(true);
    }
    if (params.get("mode") === "compare") {
      setActiveTab("compare");
    }
  }, [params]);

  // Evaluate query when question or filter context changes
  useEffect(() => {
    if (!currentQuestion) {
      setEvaluation(null);
      return;
    }
    setIsLoading(true);
    setFeedbackRating(null); // Reset feedback for new question

    const timer = setTimeout(() => {
      const res = evaluateResearchQuery(currentQuestion, company, period);
      setEvaluation(res);
      setIsLoading(false);

      // Tự động ghi nhận vào Lịch sử nghiên cứu (theo user)
      const compMeta = getCompanyMeta(company);
      setHistoryList((prev) => {
        if (
          prev.length > 0 &&
          prev[0].question === currentQuestion &&
          prev[0].company === company
        ) {
          return prev;
        }
        const newItem = {
          id: `h_${Date.now()}`,
          company,
          companyName: compMeta.fullName,
          period,
          question: currentQuestion,
          time: "Vừa xong",
          status: res.status,
          statusLabel:
            res.status === "verified"
              ? "Đã kiểm chứng"
              : res.status === "partial"
              ? "Bằng chứng một phần"
              : res.status === "insufficient"
              ? "Chưa đủ dữ liệu"
              : res.status === "refusal"
              ? "Tuân thủ FinMind"
              : "Chưa kiểm chứng",
          isPinned: false,
        };
        const updated = [
          newItem,
          ...prev.filter((item) => item.question !== currentQuestion),
        ];
        saveStoredResearchHistory(updated);
        return updated;
      });
    }, 400);

    return () => clearTimeout(timer);
  }, [currentQuestion, company, period]);

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
    setCurrentQuestion("");
    setQueryInput("");
    setEvaluation(null);
  };

  // Open Evidence Drawer for a given source
  const handleOpenSource = (sourceId) => {
    const meta = getCompanyMeta(company);
    const src =
      meta.sources?.find((s) => s.id === String(sourceId)) ||
      meta.sources?.[0] || {
        id: sourceId,
        title: `Báo cáo kiểm toán ${company} ${period}`,
        publisher: `${company} Corporation`,
        type: "Báo cáo tài chính",
        status: "Đã đối soát",
        locator: `Trang 48 – Thuyết minh báo cáo tài chính ${company}`,
        fact: `Số liệu đối chiếu tài chính hợp nhất ${company} theo chuẩn mực kiểm toán.`,
        provenance: `Hồ sơ CBTT HOSE · Ý kiến kiểm toán chấp nhận toàn phần · Hash SHA-256 #std_${company.toLowerCase()}`,
        location: "Thuyết minh báo cáo kết quả hoạt động kinh doanh",
        url: "#",
      };
    setSelectedSource({ ...src, displayId: sourceId });
    setEvidenceDrawerOpen(true);
  };

  const handleCopyLink = () => {
    setCopyFeedback(true);
    setTimeout(() => setCopyFeedback(false), 2000);
  };

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

  // Feedback Actions
  const handleRateHelpful = () => {
    setFeedbackRating("helpful");
    saveFeedbackItem({
      question: currentQuestion,
      company,
      period,
      rating: "helpful",
      timestamp: new Date().toISOString(),
    });
    setFeedbackToast("Cảm ơn bạn! Đã ghi nhận đánh giá hữu ích.");
    setTimeout(() => setFeedbackToast(null), 3500);
  };

  const handleOpenFeedbackModal = () => {
    setFeedbackRating("unhelpful");
    setFeedbackModalOpen(true);
  };

  const handleSubmitFeedbackModal = () => {
    saveFeedbackItem({
      question: currentQuestion,
      company,
      period,
      rating: "unhelpful",
      reason: feedbackReason,
      note: feedbackNote,
      timestamp: new Date().toISOString(),
    });
    setFeedbackModalOpen(false);
    setFeedbackNote("");
    setFeedbackToast("Cảm ơn bạn! FinMind đã tiếp nhận góp ý để hoàn thiện.");
    setTimeout(() => setFeedbackToast(null), 3500);
  };

  const compMeta = getCompanyMeta(company);
  const compareMeta = getCompanyMeta(compareCompany);

  // Prepare options for Selects
  const companyOptions = researchCompanyCatalog.map((c) => ({
    value: c.id,
    label: `${c.id} · ${c.name}`,
  }));

  const periodOptions = researchPeriods.map((p) => ({
    value: p.value,
    label: p.label,
  }));

  // Prepare rows for comparison DataTable
  const comp1Facts =
    companyFinancialFacts[company]?.[period] ||
    companyFinancialFacts[company]?.["FY2025"] ||
    {};
  const comp2Facts =
    companyFinancialFacts[compareCompany]?.[period] ||
    companyFinancialFacts[compareCompany]?.["FY2025"] ||
    {};

  const compareRows = comparisonMetricsList.map((metric) => {
    const val1 = comp1Facts[metric.key] ?? "—";
    const val2 = comp2Facts[metric.key] ?? "—";

    let tone1 = "neutral";
    let tone2 = "neutral";

    if (metric.key === "evidenceStatus") {
      tone1 = comp1Facts.evidenceStatus === "verified" ? "success" : "warning";
      tone2 = comp2Facts.evidenceStatus === "verified" ? "success" : "warning";
    }

    return {
      id: metric.key,
      metricName: metric.label,
      val1:
        metric.key === "evidenceStatus" ? (
          <StatusBadge tone={tone1}>
            {comp1Facts.evidenceLabel || "Chưa có dữ liệu"}
          </StatusBadge>
        ) : (
          val1
        ),
      val2:
        metric.key === "evidenceStatus" ? (
          <StatusBadge tone={tone2}>
            {comp2Facts.evidenceLabel || "Chưa có dữ liệu"}
          </StatusBadge>
        ) : (
          val2
        ),
      note:
        metric.key === "evidenceStatus"
          ? "Đối chiếu chéo BCTC"
          : val1 !== "—" && val2 !== "—"
          ? "Đã chuẩn hóa đơn vị"
          : "Cần bổ sung nguồn",
    };
  });

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
      title: `${company} (${period})`,
      render: (r) => (
        <span className="font-mono font-medium text-slate-800">{r.val1}</span>
      ),
    },
    {
      key: "val2",
      title: `${compareCompany} (${period})`,
      render: (r) => (
        <span className="font-mono font-medium text-slate-800">{r.val2}</span>
      ),
    },
    {
      key: "note",
      title: "Ghi chú kiểm chứng",
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
    <div className="flex h-screen bg-[#F8FAFC] text-[#0F172A] overflow-hidden">
      {/* 1. Shared Researcher Sidebar */}
      <Sidebar
        groups={userMenu}
        activeId="copilot"
        onSelect={(id) => navigate(menuPaths[id] || "/dashboard")}
        profile={researcherMock}
        onProfile={() => navigate("/profile")}
        onLogout={() => navigate("/login")}
      />

      {/* 2. Main Research Viewport */}
      <main className="flex-1 min-w-0 flex flex-col h-screen overflow-hidden bg-[#F8FAFC]">
        {/* Top Header */}
        <header className="shrink-0 bg-white/95 backdrop-blur-md border-b border-slate-200 px-6 py-3 z-10">
          <div className="max-w-5xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold tracking-tight text-slate-900">
                Trợ lý nghiên cứu & So sánh
              </h1>
              <StatusBadge tone="neutral">R01 · Chuỗi dữ liệu</StatusBadge>
            </div>

            {/* Quick Actions & Tab Switcher */}
            <div className="flex items-center gap-2">
              <div className="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                <button
                  type="button"
                  onClick={() => setActiveTab("copilot")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    activeTab === "copilot"
                      ? "bg-white text-blue-600 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  💬 Hỏi FinMind
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("compare")}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
                    activeTab === "compare"
                      ? "bg-white text-blue-600 shadow-xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  ⚖️ Bảng so sánh
                </button>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => setHistoryDrawerOpen(true)}
                className="gap-1.5 text-xs"
              >
                <span>🕒</span>
                <span>Lịch sử ({historyList.length})</span>
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={handleNewResearch}
                className="gap-1 text-xs"
              >
                <span>➕</span>
                <span className="hidden sm:inline">Nghiên cứu mới</span>
              </Button>
            </div>
          </div>
        </header>

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

            {/* Evidence Drawer Quick Link */}
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span>✓</span>
                <span>2 nguồn kiểm chứng sẵn sàng</span>
              </span>
              <button
                type="button"
                onClick={() => handleOpenSource("1")}
                className="text-xs text-blue-600 font-semibold hover:underline"
              >
                Xem bằng chứng →
              </button>
            </div>
          </div>
        </section>

        {/* ─── SCROLLABLE MIDDLE CONVERSATION & ANALYSIS CANVAS ─── */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* TAB 1: COPILOT CONVERSATION CONTENT */}
            {activeTab === "copilot" && (
              <div className="space-y-5">
                {/* 0. WELCOME EMPTY STATE (Khi chưa có câu hỏi nào) */}
                {!currentQuestion && (
                  <div className="py-12 px-4 text-center max-w-lg mx-auto space-y-4">
                    <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center mx-auto text-2xl text-blue-600 shadow-2xs">
                      💬
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900 tracking-tight">
                        Bắt đầu nghiên cứu về {compMeta.code}
                      </h2>
                      <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                        Đặt câu hỏi về tài chính, biên lợi nhuận hoặc kỳ báo cáo{" "}
                        <strong>{period}</strong> ở thanh nhập liệu bên dưới.
                      </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left pt-2">
                      <button
                        type="button"
                        onClick={() =>
                          setCurrentQuestion(
                            `Doanh thu ${company} ${period} thay đổi như thế nào?`
                          )
                        }
                        className="p-3 rounded-xl border border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50/30 transition-all text-xs shadow-2xs cursor-pointer"
                      >
                        <span className="font-bold text-blue-700 block">
                          {company} · {period}
                        </span>
                        <span className="text-slate-500 mt-0.5 block">
                          Tăng trưởng doanh thu & TOI?
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          setCurrentQuestion(
                            `So sánh doanh thu ${company} và ${compareCompany} trong cùng kỳ`
                          )
                        }
                        className="p-3 rounded-xl border border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50/30 transition-all text-xs shadow-2xs cursor-pointer"
                      >
                        <span className="font-bold text-amber-700 block">
                          {company} vs {compareCompany}
                        </span>
                        <span className="text-slate-500 mt-0.5 block">
                          Đối chiếu chéo chỉ tiêu trong kỳ?
                        </span>
                      </button>
                    </div>
                  </div>
                )}

                {/* 1. CURRENT USER QUESTION BUBBLE */}
                {currentQuestion && (
                  <div className="flex items-center justify-between bg-blue-50/80 border border-blue-200 rounded-xl px-4 py-3 shadow-2xs">
                    <div className="flex items-center gap-2.5">
                      <span className="w-6 h-6 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-xs shrink-0">
                        Q
                      </span>
                      <span className="text-sm font-semibold text-blue-950">
                        {currentQuestion}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500 font-medium hidden sm:inline shrink-0">
                      {compMeta.fullName} · {period}
                    </span>
                  </div>
                )}

                {/* 2. LOADING SKELETON */}
                {isLoading && (
                  <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
                    <div className="flex items-center gap-3">
                      <Spinner size="sm" />
                      <span className="text-xs font-semibold text-slate-600">
                        FinMind đang truy xuất dữ liệu công bố và đối soát bằng chứng...
                      </span>
                    </div>
                    <Skeleton className="h-4 w-3/4 rounded" />
                    <Skeleton className="h-4 w-5/6 rounded" />
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                      <Skeleton className="h-16 rounded-lg" />
                      <Skeleton className="h-16 rounded-lg" />
                      <Skeleton className="h-16 rounded-lg" />
                      <Skeleton className="h-16 rounded-lg" />
                    </div>
                  </div>
                )}

                {/* 3. ETHICAL REFUSAL / COMPLIANCE STATE */}
                {!isLoading && evaluation?.status === "refusal" && (
                  <div className="bg-white rounded-xl border border-rose-200 p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2 text-rose-700">
                        <span className="text-lg">🛡️</span>
                        <h3 className="font-bold text-sm tracking-tight text-rose-900">
                          {evaluation.title}
                        </h3>
                      </div>
                      <StatusBadge tone="danger">Quy định từ chối</StatusBadge>
                    </div>

                    <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 leading-relaxed font-medium">
                      {evaluation.warningText}
                    </div>

                    <div>
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-2">
                        ĐỀ XUẤT CHUYỂN HƯỚNG CÂU HỎI NGHIÊN CỨU:
                      </span>
                      <div className="space-y-1.5">
                        {evaluation.suggestions.map((sug, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setCurrentQuestion(sug)}
                            className="w-full text-left p-2.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 hover:border-blue-400 text-xs text-slate-800 transition-colors flex items-center justify-between cursor-pointer"
                          >
                            <span>{sug}</span>
                            <span className="text-blue-600 text-xs font-medium">
                              Áp dụng →
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* 4. UNVERIFIED / PROJECTION REFUSAL */}
                {!isLoading && evaluation?.status === "unverified" && (
                  <div className="bg-white rounded-xl border border-amber-200 p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2 text-amber-700">
                        <span className="text-lg">⚠</span>
                        <h3 className="font-bold text-sm tracking-tight text-slate-900">
                          {evaluation.title}
                        </h3>
                      </div>
                      <StatusBadge tone="warning">Không thể xác minh</StatusBadge>
                    </div>

                    <p className="text-xs text-slate-700 leading-relaxed">
                      {evaluation.errorText}
                    </p>

                    <div className="flex gap-2 pt-2 border-t border-slate-100">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenSource("1")}
                      >
                        Xem nguồn hiện có
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() =>
                          setCurrentQuestion(
                            `Doanh thu ${company} ${period} thay đổi như thế nào?`
                          )
                        }
                      >
                        Đặt câu hỏi khác
                      </Button>
                    </div>
                  </div>
                )}

                {/* 5. VERIFIED STATE (KẾT QUẢ ĐÃ ĐƯỢC ĐỐI SOÁT KIỂM TOÁN) */}
                {!isLoading && evaluation?.status === "verified" && (
                  <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-5">
                    {/* Header */}
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded bg-blue-600 text-white flex items-center justify-center font-bold text-xs">
                          FM
                        </span>
                        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                          KẾT QUẢ NGHIÊN CỨU
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge tone="success">✓ Đã kiểm chứng</StatusBadge>
                        <button
                          type="button"
                          onClick={() => handleOpenSource("1")}
                          className="text-xs font-semibold text-blue-600 hover:underline cursor-pointer"
                        >
                          2 trích dẫn
                        </button>
                      </div>
                    </div>

                    {/* Copilot Natural Language Answer */}
                    <p className="text-sm text-slate-800 leading-relaxed font-medium">
                      {evaluation.summary}
                    </p>

                    {/* Fact Metric Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {evaluation.facts.map((fact, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg border border-slate-100 bg-slate-50/70"
                        >
                          <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                            {fact.label}
                          </span>
                          <span className="text-base font-bold text-slate-900 font-mono mt-0.5 block">
                            {fact.value}
                          </span>
                          <span className="text-[11px] text-slate-500 font-medium">
                            {fact.sub}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Accordion: Analysis Metadata & Scope */}
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setIsAccordionOpen(!isAccordionOpen)}
                        className="w-full flex items-center justify-between p-3 bg-slate-50 hover:bg-slate-100 text-xs font-semibold text-slate-700 transition-colors cursor-pointer"
                      >
                        <span>Thông tin kỳ dữ liệu & phạm vi đối soát</span>
                        <span>{isAccordionOpen ? "▲" : "▼"}</span>
                      </button>
                      {isAccordionOpen && (
                        <div className="p-3 bg-white text-xs text-slate-600 space-y-1.5 border-t border-slate-200">
                          <div>
                            Kỳ báo cáo:{" "}
                            <strong className="text-slate-800">
                              {evaluation.analysis.period}
                            </strong>
                          </div>
                          <div>
                            Phạm vi dữ liệu:{" "}
                            <strong className="text-slate-800">
                              {evaluation.analysis.scope}
                            </strong>
                          </div>
                          <div>
                            Số lượng nguồn đối soát:{" "}
                            <strong className="text-slate-800">
                              {evaluation.analysis.sourcesCount} nguồn chính thức
                            </strong>
                          </div>
                          <div>
                            Thời điểm cập nhật:{" "}
                            <strong className="text-slate-800">
                              {evaluation.analysis.updatedAt}
                            </strong>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Clickable Citations */}
                    <div>
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-2">
                        Nguồn trích dẫn tham chiếu (Click để mở chi tiết Locator / Fact / Provenance)
                      </span>
                      <div className="space-y-2">
                        {evaluation.sources.map((src) => (
                          <button
                            key={src.id}
                            type="button"
                            onClick={() => handleOpenSource(src.id)}
                            className="w-full flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:bg-blue-50/30 text-left transition-colors shadow-2xs cursor-pointer"
                          >
                            <div className="flex items-center gap-2.5">
                              <span className="w-5 h-5 rounded bg-blue-50 text-blue-700 font-bold text-xs flex items-center justify-center border border-blue-200">
                                [{src.id}]
                              </span>
                              <span className="text-xs font-semibold text-slate-800">
                                {src.title}
                              </span>
                              <span className="text-[11px] text-slate-400 hidden sm:inline">
                                · {src.locator || src.location}
                              </span>
                            </div>
                            <span className="text-xs text-blue-600 font-medium">
                              Xem bằng chứng →
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* FEEDBACK SECTION */}
                    <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2 text-slate-500">
                        <span className="font-semibold text-slate-600">
                          Đánh giá câu trả lời này:
                        </span>
                        <button
                          type="button"
                          onClick={handleRateHelpful}
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors cursor-pointer ${
                            feedbackRating === "helpful"
                              ? "bg-emerald-50 border-emerald-300 text-emerald-700 font-semibold"
                              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <span>👍</span>
                          <span>Hữu ích</span>
                        </button>
                        <button
                          type="button"
                          onClick={handleOpenFeedbackModal}
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors cursor-pointer ${
                            feedbackRating === "unhelpful"
                              ? "bg-amber-50 border-amber-300 text-amber-700 font-semibold"
                              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <span>👎</span>
                          <span>Cần cải thiện</span>
                        </button>
                      </div>

                      {feedbackToast && (
                        <span className="text-emerald-600 font-semibold text-[11px] bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          {feedbackToast}
                        </span>
                      )}
                    </div>

                    {/* Follow-up Chips */}
                    <div className="pt-3 border-t border-slate-100">
                      <span className="text-xs font-bold text-slate-500 uppercase tracking-wider block mb-2">
                        Bạn có thể tìm hiểu tiếp
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {evaluation.followUps.map((chip, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setCurrentQuestion(chip)}
                            className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-700 hover:border-blue-300 hover:bg-blue-50/50 transition-colors shadow-2xs cursor-pointer"
                          >
                            {chip}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* 6. PARTIAL STATE (BẰNG CHỨNG MỘT PHẦN) */}
                {!isLoading && evaluation?.status === "partial" && (
                  <div className="bg-white rounded-xl border border-amber-200 p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded bg-blue-600 text-white flex items-center justify-center font-bold text-xs">
                          FM
                        </span>
                        <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                          KẾT QUẢ NGHIÊN CỨU
                        </span>
                      </div>
                      <StatusBadge tone="warning">⚠ Bằng chứng một phần</StatusBadge>
                    </div>

                    <p className="text-sm text-slate-800 leading-relaxed font-medium">
                      {evaluation.desc}
                    </p>

                    <div className="bg-amber-50/80 border border-amber-200 rounded-lg p-3 text-xs space-y-2">
                      <div className="flex items-center gap-2 text-emerald-800 font-medium">
                        <span>✓</span>
                        <span>{evaluation.check1}</span>
                      </div>
                      <div className="flex items-center gap-2 text-amber-800 font-medium">
                        <span>⚠</span>
                        <span>{evaluation.check2}</span>
                      </div>
                    </div>

                    <div className="flex gap-2 pt-2 border-t border-slate-100">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleOpenSource("1")}
                      >
                        Xem nguồn của {company}
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setActiveTab("compare")}
                      >
                        Chuyển sang Bảng so sánh đầy đủ →
                      </Button>
                    </div>

                    {/* Feedback bar */}
                    <div className="pt-2 border-t border-slate-100 flex items-center gap-2 text-xs">
                      <span className="text-slate-500 font-medium">
                        Phản hồi về kết quả:
                      </span>
                      <button
                        type="button"
                        onClick={handleRateHelpful}
                        className="px-2 py-0.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                      >
                        👍 Hữu ích
                      </button>
                      <button
                        type="button"
                        onClick={handleOpenFeedbackModal}
                        className="px-2 py-0.5 rounded border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                      >
                        👎 Cần bổ sung
                      </button>
                    </div>
                  </div>
                )}

                {/* 7. INSUFFICIENT STATE (THIẾU SỐ LIỆU ĐÃ KIỂM ĐỊNH) */}
                {!isLoading && evaluation?.status === "insufficient" && (
                  <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2 text-slate-700">
                        <span className="text-lg">ℹ️</span>
                        <h3 className="font-bold text-sm tracking-tight text-slate-900">
                          {evaluation.title}
                        </h3>
                      </div>
                      <StatusBadge tone="neutral">Chưa đủ dữ liệu</StatusBadge>
                    </div>

                    <p className="text-xs text-slate-700 leading-relaxed font-medium">
                      {evaluation.desc}
                    </p>

                    <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 space-y-1">
                      <strong className="text-slate-800 block">Lý do kỹ thuật:</strong>
                      <p>{evaluation.reason}</p>
                    </div>

                    <p className="text-[11px] text-slate-400 italic">
                      {evaluation.evidence}
                    </p>

                    <div className="pt-2 border-t border-slate-100">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setPeriod("FY2025")}
                      >
                        Xem kỳ FY2025 có số liệu kiểm toán
                      </Button>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}

            {/* TAB 2: BẢNG SO SÁNH CHỈ TIÊU (COMPARE VIEW) */}
            {activeTab === "compare" && (
              <div className="space-y-6">
                <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
                    <div>
                      <h2 className="text-base font-bold text-slate-900">
                        Đối chiếu chỉ tiêu: {company} vs {compareCompany}
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Kỳ báo cáo: {period} · Báo cáo tài chính hợp nhất kiểm toán
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500 font-medium">
                        Chuẩn mực đơn vị: VNĐ / Tỷ lệ %
                      </span>
                    </div>
                  </div>

                  <div className="mt-4">
                    <DataTable columns={compareColumns} rows={compareRows} />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ─── 3. STICKY BOTTOM INPUT BAR (THANH CÂU HỎI NẰM DƯỚI CÙNG) ─── */}
        <div className="shrink-0 bg-white border-t border-slate-200 p-3 sm:p-4 z-20 shadow-[0_-2px_10px_rgba(0,0,0,0.02)]">
          <div className="max-w-4xl mx-auto space-y-2">
            {activeTab === "copilot" ? (
              <>
                {/* Context Badges Bar */}
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    <span>{company}</span>
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                    <span>{period}</span>
                  </span>
                  <span className="text-[11px] text-slate-400">
                    Ngữ cảnh nghiên cứu đang khóa
                  </span>
                </div>

                {/* Question Input Form with Send Button */}
                <form onSubmit={handleSubmitQuery} className="relative flex items-center">
                  <input
                    type="text"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder={`Hỏi thêm về ${company} (${period}) (ví dụ: cơ cấu doanh thu theo mảng, biên lợi nhuận, chi phí)...`}
                    className="w-full h-11 pl-4 pr-24 rounded-lg bg-white border border-slate-200 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition-all shadow-2xs"
                  />
                  <button
                    type="submit"
                    disabled={!queryInput.trim()}
                    className="absolute right-1.5 h-8 px-3.5 rounded-md bg-blue-600 text-white font-semibold text-xs flex items-center gap-1 hover:bg-blue-700 disabled:opacity-40 transition-colors shadow-xs cursor-pointer"
                  >
                    <span>Gửi</span>
                    <span className="text-xs">➔</span>
                  </button>
                </form>

                {/* Quick Sample Prompt Chips */}
                <div className="flex flex-wrap items-center gap-1.5 pt-0.5 text-xs">
                  <span className="text-[11px] text-slate-400 font-medium">
                    Thử câu hỏi mẫu:
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentQuestion(
                        `Doanh thu ${company} ${period} thay đổi như thế nào?`
                      )
                    }
                    className="px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-medium transition-colors cursor-pointer"
                  >
                    📊 Doanh thu chuẩn
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentQuestion(
                        `So sánh doanh thu ${company} và ${compareCompany} trong cùng kỳ`
                      )
                    }
                    className="px-2 py-0.5 rounded bg-amber-50 hover:bg-amber-100 text-amber-800 text-[11px] border border-amber-200 font-medium transition-colors cursor-pointer"
                  >
                    ⚠ So sánh 2 bên
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentQuestion(
                        `Dự báo doanh thu ${company} quý tới đạt bao nhiêu?`
                      )
                    }
                    className="px-2 py-0.5 rounded bg-purple-50 hover:bg-purple-100 text-purple-800 text-[11px] border border-purple-200 font-medium transition-colors cursor-pointer"
                  >
                    🔮 Dự đoán
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentQuestion(
                        `Có nên mua cổ phiếu ${company} vào lúc này không?`
                      )
                    }
                    className="px-2 py-0.5 rounded bg-rose-50 hover:bg-rose-100 text-rose-800 text-[11px] border border-rose-200 font-medium transition-colors cursor-pointer"
                  >
                    ⛔ Hỏi đầu tư
                  </button>
                </div>
              </>
            ) : (
              <div className="text-center py-1">
                <span className="text-xs text-slate-500 font-medium">
                  Đang xem Bảng đối chiếu chỉ tiêu tài chính giữa {company} và {compareCompany} ({period})
                </span>
              </div>
            )}

            {/* Footer Disclaimer */}
            <div className="text-center pt-1">
              <span className="text-[11px] text-slate-400 tracking-tight">
                Chỉ hỗ trợ mục đích nghiên cứu · Không phải khuyến nghị đầu tư
              </span>
            </div>
          </div>
        </div>

        {/* ───────────────────────────────────────────────────────────── */}
        {/* 4. EVIDENCE DRAWER (HIỂN THỊ LOCATOR / FACT / PROVENANCE)    */}
        {/* ───────────────────────────────────────────────────────────── */}
        <Drawer
          open={evidenceDrawerOpen}
          title={`BẰNG CHỨNG NGUỒN [${selectedSource?.displayId || selectedSource?.id || "1"}]`}
          onClose={() => setEvidenceDrawerOpen(false)}
        >
          {selectedSource && (
            <div className="space-y-4 text-xs">
              {/* Header Status */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div>
                  <span className="text-[11px] font-bold text-slate-400 uppercase block">
                    TÀI LIỆU CÔNG BỐ
                  </span>
                  <h3 className="font-bold text-sm text-slate-900 mt-0.5">
                    {selectedSource.title}
                  </h3>
                </div>
                <StatusBadge tone="success">
                  ✓ {selectedSource.status || "Đã đối soát"}
                </StatusBadge>
              </div>

              {/* General Metadata */}
              <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">
                    Đơn vị phát hành
                  </span>
                  <span className="font-semibold text-slate-800 text-xs mt-0.5 block">
                    {selectedSource.publisher}
                  </span>
                </div>
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase block">
                    Loại văn bản
                  </span>
                  <span className="font-semibold text-slate-800 text-xs mt-0.5 block">
                    {selectedSource.type}
                  </span>
                </div>
              </div>

              {/* SECTION 1: LOCATOR */}
              <div className="p-3.5 rounded-xl bg-blue-50/60 border border-blue-200 space-y-1.5">
                <div className="flex items-center gap-1.5 text-blue-800 font-bold text-xs">
                  <span>📍</span>
                  <span>LOCATOR (Vị trí bằng chứng)</span>
                </div>
                <p className="text-xs font-semibold text-slate-900 bg-white/90 p-2.5 rounded-lg border border-blue-100 leading-relaxed">
                  {selectedSource.locator || selectedSource.location}
                </p>
              </div>

              {/* SECTION 2: FACT */}
              <div className="p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-200 space-y-1.5">
                <div className="flex items-center gap-1.5 text-emerald-800 font-bold text-xs">
                  <span>📑</span>
                  <span>FACT (Dữ kiện / Số liệu trích xuất nguyên văn)</span>
                </div>
                <blockquote className="text-xs text-slate-800 italic bg-white/90 p-2.5 rounded-lg border border-emerald-100 leading-relaxed">
                  "{selectedSource.fact || "Số liệu tài chính được ghi nhận nguyên văn từ văn bản công bố chính thức."}"
                </blockquote>
              </div>

              {/* SECTION 3: PROVENANCE */}
              <div className="p-3.5 rounded-xl bg-slate-100/70 border border-slate-200 space-y-1.5">
                <div className="flex items-center gap-1.5 text-slate-700 font-bold text-xs">
                  <span>🔒</span>
                  <span>PROVENANCE (Chuỗi truy xuất nguồn gốc kiểm chứng)</span>
                </div>
                <p className="text-[11px] font-mono text-slate-600 bg-white/90 p-2.5 rounded-lg border border-slate-200 leading-relaxed">
                  {selectedSource.provenance || "Hồ sơ công bố thông tin đã qua đối soát kiểm toán độc lập · Xác thực Corpus FinMind"}
                </p>
              </div>

              {/* Institutional Safety Notice */}
              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                <span>Văn bản đối soát FinMind Corpus</span>
                <button
                  type="button"
                  onClick={handleCopyLink}
                  className="text-blue-600 hover:underline font-medium cursor-pointer"
                >
                  {copyFeedback ? "✓ Đã sao chép liên kết" : "Sao chép mã trích dẫn"}
                </button>
              </div>
            </div>
          )}
        </Drawer>

        {/* ───────────────────────────────────────────────────────────── */}
        {/* 5. HISTORY DRAWER (XEM / XÓA / PIN / UNPIN)                  */}
        {/* ───────────────────────────────────────────────────────────── */}
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

        {/* ───────────────────────────────────────────────────────────── */}
        {/* 7. MODAL GÓP Ý PHẢN HỒI (FEEDBACK FORM)                      */}
        {/* ───────────────────────────────────────────────────────────── */}
        <Modal
          open={feedbackModalOpen}
          title="Góp ý chất lượng câu trả lời Copilot"
          onClose={() => setFeedbackModalOpen(false)}
          footer={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setFeedbackModalOpen(false)}>
                Đóng
              </Button>
              <button
                type="button"
                onClick={handleSubmitFeedbackModal}
                className="px-4 py-2 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors cursor-pointer"
              >
                Gửi góp ý
              </button>
            </div>
          }
        >
          <div className="space-y-3.5">
            <p className="text-xs text-slate-600">
              Phản hồi của bạn giúp hệ thống kiểm định tính chuẩn xác của mô hình và trích xuất tài liệu đối soát:
            </p>

            <div className="space-y-2 text-xs text-slate-700">
              {[
                "Số liệu chưa chính xác",
                "Thiếu trích dẫn bằng chứng kiểm toán",
                "Chưa so sánh đúng kỳ đối ứng",
                "Văn bản trích xuất chưa đầy đủ",
              ].map((reason) => (
                <label
                  key={reason}
                  className="flex items-center gap-2 cursor-pointer p-1.5 rounded hover:bg-slate-50 border border-slate-100"
                >
                  <input
                    type="radio"
                    name="feedbackReason"
                    checked={feedbackReason === reason}
                    onChange={() => setFeedbackReason(reason)}
                    className="text-blue-600 focus:ring-blue-500"
                  />
                  <span>{reason}</span>
                </label>
              ))}
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Ghi chú chi tiết (tùy chọn):
              </label>
              <textarea
                rows={3}
                value={feedbackNote}
                onChange={(e) => setFeedbackNote(e.target.value)}
                placeholder="Ví dụ: Cần đối soát lại dòng doanh thu hợp nhất sau khi trừ thuế..."
                className="w-full p-2.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:border-blue-600 resize-none"
              />
            </div>
          </div>
        </Modal>
      </main>
    </div>
  );
}
