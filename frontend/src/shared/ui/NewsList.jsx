import AppIcon from "./AppIcon.jsx";

export default function NewsList({ articles = [], descriptions = false }) {
  return (
    <div className="approved-news-list">
      {articles.map((article, index) => {
        const url = /^https?:\/\//i.test(article.url || "")
          ? article.url
          : null;
        const title = url ? (
          <a href={url} target="_blank" rel="noopener noreferrer">
            {article.title}
          </a>
        ) : (
          article.title
        );
        return (
          <article
            key={article.id || `${article.title}-${index}`}
            className="approved-article"
          >
            <div className="approved-article-category">
              {article.category || "Thị trường & doanh nghiệp"}
            </div>
            <h3>{title}</h3>
            {descriptions && article.description && (
              <p className="approved-article-description">
                {article.description}
              </p>
            )}
            <p>
              {article.source || "FireAnt"} ·{" "}
              {article.published_at
                ? new Date(article.published_at).toLocaleString("vi-VN")
                : "Chưa rõ ngày công bố"}
              {article.marker === "check" && <> · Có bài tương đồng</>}
              {url && (
                <a
                  className="approved-news-source"
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Mở bài gốc: ${article.title}`}
                >
                  <AppIcon name="external" />
                </a>
              )}
            </p>
          </article>
        );
      })}
    </div>
  );
}
