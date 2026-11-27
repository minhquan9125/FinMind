import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "../../app/router.jsx";
import AppIcon from "./AppIcon.jsx";

export default function WorkspaceBar({ admin = false }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const search = useRef(null);
  useEffect(() => {
    const shortcut = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  return (
    <header className="approved-workspace-bar">
      <Link
        className="approved-workspace-name"
        to={admin ? "/admin" : "/dashboard"}
      >
        FinMind <span>/ {admin ? "Quản trị" : "Workspace"}</span>
      </Link>
      <form
        className="approved-global-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          if (query.trim())
            navigate(`/companies?search=${encodeURIComponent(query.trim())}`);
        }}
      >
        <button type="submit" aria-label="Tìm doanh nghiệp">
          <AppIcon name="search" />
        </button>
        <input
          ref={search}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          type="search"
          aria-label="Tìm mã cổ phiếu hoặc doanh nghiệp"
          placeholder="Tìm mã cổ phiếu hoặc doanh nghiệp…"
        />
        <kbd>Ctrl K</kbd>
      </form>
      <div className="approved-workspace-actions">
        <Link
          className="approved-quick-research"
          to={admin ? "/dashboard" : "/research"}
        >
          <AppIcon name={admin ? "dashboard" : "copilot"} />
          <span>{admin ? "Về workspace" : "Hỏi FinMind"}</span>
        </Link>
      </div>
    </header>
  );
}
