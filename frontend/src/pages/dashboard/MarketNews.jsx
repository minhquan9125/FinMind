import { useEffect, useState } from "react";
import {
  Card,
  EmptyState,
  ErrorState,
  Skeleton,
} from "../../shared/ui/index.js";
import { getMarketNews } from "../companies/marketDataApi.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import NewsList from "../../shared/ui/NewsList.jsx";

// Loaded news kept in memory per user, so leaving the dashboard and coming back shows it at once.
// "Làm mới tin" always fetches again; an entry older than NEWS_CACHE_MS is fetched again too.
const newsCache = new Map();
const NEWS_CACHE_MS = 10 * 60 * 1000;

export default function MarketNews() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [category, setCategory] = useState("Tất cả");
  useEffect(() => {
    const cached = newsCache.get(user?.id);
    if (retry === 0 && cached && Date.now() - cached.at < NEWS_CACHE_MS) {
      setData(cached.data);
      setError(null);
      setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getMarketNews(controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((caught) => {
        if (!controller.signal.aborted) setError(caught.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [retry, user?.id]);
  useEffect(() => {
    if (data && !loading && !error && newsCache.get(user?.id)?.data !== data)
      newsCache.set(user?.id, { data, at: Date.now() });
  }, [data, loading, error, user?.id]);
  const categories = [
    "Tất cả",
    ...new Set(
      (data?.articles || []).map((article) => article.category).filter(Boolean),
    ),
  ];
  const selectedCategory = categories.includes(category) ? category : "Tất cả";
  const articles = (data?.articles || []).filter(
    (article) =>
      selectedCategory === "Tất cả" || article.category === selectedCategory,
  );
  return (
    <Card
      id="market-news"
      className="approved-news-card"
      title="Tin thị trường"
      action={
        <button
          type="button"
          className="text-xs text-blue-700"
          onClick={() => setRetry((value) => value + 1)}
        >
          Làm mới tin
        </button>
      }
    >
      {loading ? (
        <Skeleton rows={3} />
      ) : error ? (
        <ErrorState
          message={error}
          onRetry={() => setRetry((value) => value + 1)}
        />
      ) : data?.articles?.length ? (
        <>
          {categories.length > 1 && (
            <div
              className="approved-news-filters"
              aria-label="Lọc tin thị trường"
            >
              {categories.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={selectedCategory === value}
                  onClick={() => setCategory(value)}
                >
                  {value}
                </button>
              ))}
            </div>
          )}
          <NewsList articles={articles} />
        </>
      ) : (
        <EmptyState title="Chưa có tin thị trường đã lưu" />
      )}
    </Card>
  );
}
