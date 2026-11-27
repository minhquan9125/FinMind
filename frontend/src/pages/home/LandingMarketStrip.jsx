import { useEffect, useId, useState } from 'react';
import { AlertCircle, ArrowUpRight } from 'lucide-react';
import { useAuth } from '../../shared/context/AuthContext.jsx';
import { getIndexHistory } from '../companies/marketDataApi.js';
import { loadMarketIndices } from '../dashboard/marketIndices.js';
import { LANDING_INDICES, summarizeMarket, readMarketNumber } from './landingMarketData.js';

const number = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sessionDate = (value) => value ? new Date(value).toLocaleDateString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : null;
const api = { cached: (symbol, signal) => getIndexHistory(symbol, signal, { cached: true }), refresh: getIndexHistory };

function Sparkline({ bars = [] }) {
  const id = useId().replace(/:/g, '');
  const values = bars.slice(-30).map((bar) => readMarketNumber(bar.close)).filter((value) => value !== null && value > 0);
  if (values.length < 2) return null;
  const min = Math.min(...values), span = Math.max(...values) - min;
  const points = values.map((value, index) => `${index / (values.length - 1) * 100},${span ? 35 - (value - min) / span * 30 : 20}`).join(' ');
  return <svg viewBox="0 0 100 42" className="landing-index-spark" aria-hidden="true">
    <defs><linearGradient id={id} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".16" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
    <polygon points={`0,42 ${points} 100,42`} fill={`url(#${id})`} />
    <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" />
  </svg>;
}

export default function LandingMarketStrip({ active }) {
  const { user } = useAuth();
  const owner = user?.id;
  const [state, setState] = useState({});
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!owner || !active) return;
    const abort = new AbortController();
    let timer;
    setState((previous) => previous.owner === owner ? previous : { owner, entries: {} });
    const update = (symbol, patch) => {
      if (!abort.signal.aborted) setState((previous) => ({ owner, entries: { ...previous.entries, [symbol]: { ...previous.entries?.[symbol], ...patch } } }));
    };
    const load = async () => {
      await loadMarketIndices({
        symbols: LANDING_INDICES.map(([symbol]) => symbol), signal: abort.signal, api,
        onResult: (symbol, data) => update(symbol, { data }),
        onError: (symbol, error) => update(symbol, { error: error?.message || null }),
        onPending: (symbol, pending) => update(symbol, { pending }),
      });
      if (!abort.signal.aborted) timer = setTimeout(load, 60000);
    };
    void load();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [owner, active, retry]);
  const entries = owner && state.owner === owner ? state.entries || {} : {};
  const failed = owner && LANDING_INDICES.every(([symbol]) => entries[symbol]?.error && !entries[symbol]?.data?.bars?.length);
  return <section className="landing-market-strip" aria-label="Chỉ số thị trường">
    <div className="landing-index-grid">
      {LANDING_INDICES.map(([symbol, label]) => {
        const entry = entries[symbol], quote = summarizeMarket(entry?.data);
        const tone = quote?.change > 0 ? 'is-up' : quote?.change < 0 ? 'is-down' : 'is-flat';
        const stale = entry?.error || entry?.data?.refresh?.stale;
        const empty = entry?.data && !entry.data.bars?.length;
        const missingLabel = entry?.pending?.loading && !empty ? 'Đang tải…' : 'Chưa có dữ liệu';
        return <a href="/dashboard" className={`landing-index-item ${tone}`} key={symbol}>
          <div><span className="landing-index-name">{label}</span><strong>{quote ? number.format(quote.close) : '—'}</strong>
            <span className="landing-index-change">{quote?.change != null ? `${quote.change > 0 ? '+' : ''}${number.format(quote.change)} (${quote.percent > 0 ? '+' : ''}${number.format(quote.percent)}%)` : owner ? missingLabel : ''}</span>
            {quote?.date && <small title={entry?.error || (stale ? 'Bản đã lưu từ nguồn dữ liệu' : undefined)}>{stale && <AlertCircle size={10} aria-hidden="true" />}Phiên {sessionDate(quote.date)}</small>}
          </div>
          {quote && <Sparkline bars={entry.data.bars} />}
        </a>;
      })}
    </div>
    {!owner && <a className="landing-market-signin" href="/login">Đăng nhập để theo dõi thị trường<ArrowUpRight size={13} aria-hidden="true" /></a>}
    {failed && <button type="button" className="landing-market-retry" onClick={() => setRetry((value) => value + 1)}>Tải lại chỉ số</button>}
  </section>;
}
