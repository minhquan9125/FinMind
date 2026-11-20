import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getMarketNews } from "../companies/marketDataApi.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";

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
  useEffect(() => {
    const cached = newsCache.get(user?.id);
    if (retry === 0 && cached && Date.now() - cached.at < NEWS_CACHE_MS) {
      setData(cached.data); setError(null); setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getMarketNews(controller.signal)
      .then((result) => { if (!controller.signal.aborted) setData(result); })
      .catch((caught) => { if (!controller.signal.aborted) setError(caught.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry, user?.id]);
  useEffect(() => {
    if (data && !loading && !error && newsCache.get(user?.id)?.data !== data) newsCache.set(user?.id, { data, at: Date.now() });
  }, [data, loading, error, user?.id]);
  return <Card title="Tin tức thị trường" description="Tin FireAnt đã thu thập · Ngày đăng hiển thị trên từng bài"
    action={<button type="button" className="text-xs text-blue-700" onClick={() => setRetry((value) => value + 1)}>Làm mới tin</button>}>
    {loading ? <Skeleton rows={3} /> : error ? <ErrorState message={error} onRetry={() => setRetry((value) => value + 1)} /> : data?.articles?.length ? <div className="grid gap-3 md:grid-cols-2">
      {data.articles.map((article) => <article key={article.id} className="rounded-lg border border-slate-200 p-4">
        <p className="mb-2 text-xs text-slate-500">FireAnt · {article.published_at ? new Date(article.published_at).toLocaleString("vi-VN") : "Chưa rõ ngày"}</p>
        <h3 className="text-sm font-semibold">{article.title}</h3>
        {article.description && <p className="mt-2 text-xs text-slate-600">{article.description}</p>}
        {article.url && <a href={article.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-xs text-blue-700">Xem bài gốc →</a>}
      </article>)}
    </div> : <EmptyState title="Chưa có tin thị trường đã lưu" />}
  </Card>;
}
