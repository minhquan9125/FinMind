import { useEffect, useState } from "react";
import { useNavigate, useSearchParams, useAuth } from "../../app/router.jsx";
import { Button, Sidebar } from "../../shared/ui/index.js";
import { userMenu } from "../../shared/navigation.js";
import ResearchIcon from "./ResearchIcon.jsx";
import ResearchChat from "./ResearchChat.jsx";
import "./researchLayout.css";

const menuPaths = { dashboard: "/dashboard", companies: "/companies", copilot: "/research", watchlist: "/watchlist", graph: "/graph" };

export default function ResearchPage() {
  const navigate = useNavigate();
  const { userProfile, logout } = useAuth();
  const [params, setParams] = useSearchParams();
  const [resetKey, setResetKey] = useState(0);
  const [historyCount, setHistoryCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(() => params.get("history") === "1");
  useEffect(() => { if (params.get("history") === "1") setHistoryOpen(true); }, [params]);
  function closeHistory() {
    setHistoryOpen(false);
    setParams(previous => { const next = new URLSearchParams(previous); next.delete("history"); return next; }, { replace: true });
  }
  function newResearch() {
    if (busy) return;
    setHistoryOpen(false);
    setParams(previous => {
      const next = new URLSearchParams(previous);
      for (const key of ["question", "autosubmit", "history", "mode"]) next.delete(key);
      return next;
    }, { replace: true });
    setResetKey(value => value + 1);
  }
  return (
    <div className="fm-workspace fm-research research-page flex h-screen overflow-hidden bg-[#F8FAFC] text-[#0F172A]">
      <Sidebar groups={userMenu} renderIcon={item => <ResearchIcon name={item.id} />} activeId="copilot"
        onSelect={id => navigate(menuPaths[id] || "/dashboard")} profile={userProfile}
        onProfile={() => navigate("/profile")} onLogout={async () => { await logout(); navigate("/login"); }} />
      <main className="research-page-main flex h-screen min-w-0 flex-1 flex-col overflow-hidden bg-[#F8FAFC]">
        <header className="research-page-header z-10 shrink-0 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-md sm:px-6">
          <div className="research-header-inner mx-auto flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-slate-900">Trợ lý nghiên cứu</h1>
              <span className="research-header-caption">Tra cứu doanh nghiệp có nguồn</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" size="sm" disabled={busy} onClick={() => setHistoryOpen(true)} className="gap-1.5 text-xs"><ResearchIcon name="history" />Lịch sử ({historyCount})</Button>
              <Button size="sm" disabled={busy} aria-label="Nghiên cứu mới" onClick={newResearch} className="gap-1 text-xs"><ResearchIcon name="plus" /><span>Nghiên cứu mới</span></Button>
            </div>
          </div>
        </header>
        <div className="research-canvas research-canvas-chat flex min-h-0 min-w-0 flex-1 flex-col px-3 py-3 sm:px-6">
          <div className="research-content mx-auto flex min-h-0 w-full flex-1 flex-col">
            <ResearchChat historyOpen={historyOpen} onHistoryClose={closeHistory} resetKey={resetKey} onHistoryCount={setHistoryCount} onBusyChange={setBusy} />
          </div>
        </div>
      </main>
    </div>
  );
}
