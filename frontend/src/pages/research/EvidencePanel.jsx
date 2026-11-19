import AppIcon from '../../shared/ui/AppIcon.jsx';
import { citationView } from './citationView.js';

export default function EvidencePanel({ result, question }) {
  const sources = citationView(result);
  return <div className="desk-evidence-content">
    <header><div className="desk-preview-kicker">Đối chiếu bằng chứng</div><h2>Nguồn tham khảo <span>{sources.length}</span></h2><p>{question || 'Nguồn của câu trả lời sẽ xuất hiện tại đây.'}</p></header>
    {sources.length ? <div className="desk-evidence-list">{sources.map(source => <article key={source.id} className="desk-evidence-card">
      <div className="desk-evidence-number"><span>{source.citationNumber ? `[${source.citationNumber}]` : '—'}</span><small>{source.used ? 'Được trích dẫn' : 'Nguồn ứng viên'}</small></div>
      <h3>{source.title}</h3>{source.location && <p className="desk-evidence-location">{source.location}</p>}
      {source.passage && <details><summary>Xem đoạn bằng chứng</summary><blockquote>{source.passage}</blockquote></details>}
      {source.rows.length > 0 && <details className="desk-source-locator"><summary>Vị trí dữ liệu</summary><p>{source.rows.join(', ')}</p></details>}
      {source.url && <a href={source.url} target="_blank" rel="noopener noreferrer">Mở nguồn gốc <AppIcon name="external" /></a>}
    </article>)}</div> : <div className="desk-evidence-empty"><AppIcon name="document" /><h3>Đọc câu trả lời cùng nguồn</h3><p>Khi câu trả lời có tài liệu tham khảo, chọn “Xem nguồn” để đối chiếu nội dung, vị trí và liên kết gốc.</p></div>}
    <footer><AppIcon name="shield" /><p>Nguồn ứng viên chưa đồng nghĩa với thông tin đã được xác minh.</p></footer>
  </div>;
}
