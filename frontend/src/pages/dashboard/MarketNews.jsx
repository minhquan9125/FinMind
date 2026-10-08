import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorState, Skeleton } from "../../shared/ui/index.js";
import { getMarketNews } from "../companies/marketDataApi.js";

export default function MarketNews() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getMarketNews(controller.signal)
      .then((result) => { if (!controller.signal.aborted) setData(result); })
      .catch((caught) => { if (!controller.signal.aborted) setError(caught.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);
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
