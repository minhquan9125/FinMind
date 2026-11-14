import React, { useState, useEffect, useCallback } from "react";
import { getDocumentsAdapter } from "../services/apiAdapter";

export default function DocumentList() {
  const [documents, setDocuments] = useState([]);
  const [meta, setMeta] = useState({ traceId: null, citationId: null, total: 0 });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Bộ lọc tìm kiếm trên client
  const [searchTerm, setSearchTerm] = useState("");

  // Hàm gọi API thông qua Adapter
  const loadDocuments = useCallback(async ({ simulateError = false, errorCode = 500 } = {}) => {
    setIsLoading(true);
    setError(null);

    const result = await getDocumentsAdapter({
      shouldFail: simulateError,
      errorCode: errorCode
    });

    if (result.success) {
      setDocuments(result.data.items);
      setMeta({
        traceId: result.data.traceId,
        citationId: result.data.citationId,
        total: result.data.total
      });
      setError(null);
    } else {
      setError(result.error);
      setDocuments([]);
    }

    setIsLoading(false);
  }, []);

  // Tải dữ liệu lần đầu khi mount component
  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Lọc tài liệu theo từ khóa
  const filteredDocuments = documents.filter((doc) => {
    const term = searchTerm.toLowerCase();
    return (
      doc.title.toLowerCase().includes(term) ||
      doc.author.toLowerCase().includes(term) ||
      doc.category.toLowerCase().includes(term)
    );
  });

  return (
    <div className="w-full max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Tiêu đề trang & Thanh điều khiển thử nghiệm (Mock Testing Toolbar) */}
      <div className="bg-white rounded-xl shadow-sm border border-border p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-ink">
              Tài Liệu & Báo Cáo Tài Chính
            </h1>
            <p className="text-sm text-muted mt-1">
              Dữ liệu được xử lý qua <strong>Mock API</strong> và chuẩn hóa bởi <strong>API Adapter</strong>
            </p>
          </div>

          {/* Công cụ giả lập kiểm thử giao diện */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => loadDocuments()}
              disabled={isLoading}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-brand text-white hover:bg-opacity-90 disabled:opacity-50 transition shadow-sm"
              title="Gọi lại API bình thường"
            >
              {isLoading ? "Đang tải..." : "Làm mới dữ liệu"}
            </button>

            <button
              onClick={() => loadDocuments({ simulateError: true, errorCode: 400 })}
              disabled={isLoading}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 disabled:opacity-50 transition"
              title="Giả lập HTTP 400"
            >
              Test Lỗi 400
            </button>

            <button
              onClick={() => loadDocuments({ simulateError: true, errorCode: 500 })}
              disabled={isLoading}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100 disabled:opacity-50 transition"
              title="Giả lập HTTP 500"
            >
              Test Lỗi 500
            </button>
          </div>
        </div>

        {/* Thanh tìm kiếm & Thông tin tracking (trace_id, citation_id) */}
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 pt-3 border-t border-border/60">
          <input
            type="text"
            placeholder="Tìm theo tiêu đề, tác giả hoặc danh mục..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full md:w-80 px-3 py-2 text-sm border border-border rounded-lg bg-bg focus:outline-none focus:ring-2 focus:ring-brand"
          />

          {meta.traceId && !error && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              <span className="bg-gray-100 px-2 py-1 rounded border border-gray-200">
                Trace ID: <code className="text-ink font-mono">{meta.traceId}</code>
              </span>
              {meta.citationId && (
                <span className="bg-emerald-50 text-emerald-800 px-2 py-1 rounded border border-emerald-200">
                  Citation: <code className="font-mono font-semibold">{meta.citationId}</code>
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* TRẠNG THÁI 1: ĐANG TẢI DỮ LIỆU (LOADING SKELETON) */}
      {isLoading && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-brand font-medium">
            <div className="spinner" />
            <span>Đang nạp dữ liệu từ Mock API (delay 500ms - 1000ms)...</span>
          </div>

          {[1, 2, 3].map((skeletonId) => (
            <div
              key={skeletonId}
              className="bg-white rounded-xl p-5 border border-border animate-pulse space-y-3"
            >
              <div className="flex justify-between items-center">
                <div className="h-5 bg-gray-200 rounded w-2/5"></div>
                <div className="h-5 bg-gray-200 rounded w-16"></div>
              </div>
              <div className="h-4 bg-gray-100 rounded w-4/5"></div>
              <div className="h-3 bg-gray-100 rounded w-1/3"></div>
            </div>
          ))}
        </div>
      )}

      {/* TRẠNG THÁI 2: XỬ LÝ LỖI MẠNG (ERROR STATE) */}
      {!isLoading && error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-rose-900 space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-rose-200 text-rose-800 flex items-center justify-center font-bold text-sm shrink-0">
              {error.status || "!"}
            </div>
            <div>
              <h3 className="font-semibold text-base">
                Không thể tải danh sách tài liệu (Mã lỗi HTTP: {error.status})
              </h3>
              <p className="text-sm text-rose-700 mt-1">{error.message}</p>
              <div className="mt-2 text-xs text-rose-600 font-mono">
                Tracking ID: <code>{error.traceId}</code>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-2">
            <button
              onClick={() => loadDocuments()}
              className="px-4 py-2 bg-rose-700 hover:bg-rose-800 text-white rounded-lg text-sm font-medium transition"
            >
              Thử lại ngay
            </button>
          </div>
        </div>
      )}

      {/* TRẠNG THÁI 3: HIỂN THỊ DANH SÁCH TÀI LIỆU (SUCCESS STATE) */}
      {!isLoading && !error && (
        <>
          {filteredDocuments.length === 0 ? (
            <div className="bg-white rounded-xl p-10 text-center border border-border text-muted">
              Không tìm thấy tài liệu phù hợp với từ khóa "{searchTerm}".
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {filteredDocuments.map((doc) => (
                <article
                  key={doc.id}
                  className="bg-white rounded-xl p-5 border border-border hover:shadow-md transition space-y-3 group"
                >
                  {/* Hàng 1: Mã tài liệu, Trạng thái & Thể loại */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-semibold px-2 py-0.5 bg-gray-100 text-gray-700 rounded border border-gray-200">
                        {doc.id}
                      </span>
                      <span className="text-xs font-medium px-2 py-0.5 rounded bg-brand.light text-brand">
                        {doc.category}
                      </span>
                    </div>

                    <span
                      className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                        doc.statusVariant === "green"
                          ? "bg-emerald-100 text-emerald-800"
                          : doc.statusVariant === "yellow"
                          ? "bg-amber-100 text-amber-800"
                          : doc.statusVariant === "blue"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {doc.status}
                    </span>
                  </div>

                  {/* Hàng 2: Tiêu đề tài liệu */}
                  <h2 className="text-lg font-bold text-ink group-hover:text-brand transition">
                    {doc.title}
                  </h2>

                  {/* Hàng 3: Tóm tắt nội dung (đã có fallback từ adapter) */}
                  <p className="text-sm text-muted leading-relaxed line-clamp-2">
                    {doc.summary}
                  </p>

                  {/* Hàng 4: Tags */}
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {doc.tags.map((tag, idx) => (
                      <span
                        key={idx}
                        className="text-xs px-2 py-0.5 bg-bg text-muted rounded border border-border"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>

                  {/* Hàng 5: Footer meta thông tin chuẩn hóa */}
                  <div className="flex flex-wrap items-center justify-between text-xs text-muted pt-3 border-t border-border/60 gap-y-2">
                    <div className="flex items-center gap-4">
                      <span>
                        Tác giả: <strong className="text-ink">{doc.author}</strong>
                      </span>
                      <span>Ngày tạo: {doc.createdAt}</span>
                      <span>Dung lượng: {doc.fileSize}</span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span>Nguồn: {doc.citationSource}</span>
                      <span>Lượt xem: {doc.viewCount.toLocaleString()}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
