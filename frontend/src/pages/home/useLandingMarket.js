import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../shared/context/AuthContext.jsx';
import { getCompanyFinancials } from '../companies/financials.js';
import { startPricePolling } from '../companies/pricePolling.js';
import { LANDING_SYMBOL } from './landingMarketData.js';

export function useLandingVisibility() {
  const host = useRef(null);
  const [inView, setInView] = useState(false);
  const [pageVisible, setPageVisible] = useState(() => !document.hidden);
  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), { rootMargin: '200px' });
    observer.observe(host.current);
    const update = () => setPageVisible(!document.hidden);
    document.addEventListener('visibilitychange', update);
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', update); };
  }, []);
  return { host, active: inView && pageVisible };
}

export function useLandingCompany(active) {
  const { user, isLoading } = useAuth();
  const owner = user?.id;
  const [retry, setRetry] = useState(0);
  const [company, setCompany] = useState({});
  const [price, setPrice] = useState({});
  useEffect(() => {
    if (!owner || !active) return;
    const abort = new AbortController();
    setCompany((previous) => ({ ...previous, owner, loading: true, error: null, data: previous.owner === owner ? previous.data : null }));
    getCompanyFinancials(LANDING_SYMBOL, abort.signal)
      .then((data) => { if (!abort.signal.aborted) setCompany({ owner, data, loading: false }); })
      .catch((error) => { if (!abort.signal.aborted) setCompany({ owner, loading: false, error: error.message }); });
    return () => abort.abort();
  }, [owner, active, retry]);
  useEffect(() => {
    if (!owner || !active) return;
    setPrice((previous) => ({ ...previous, owner, loading: true, error: null, data: previous.owner === owner ? previous.data : null }));
    return startPricePolling({
      symbol: LANDING_SYMBOL,
      canPrepare: false,
      onResult: (data) => setPrice((previous) => ({ ...previous, owner, data, loading: false })),
      onError: (error) => setPrice((previous) => ({ ...previous, owner, error })),
      onChecked: () => setPrice((previous) => ({ ...previous, owner, error: null })),
      onSettled: () => setPrice((previous) => ({ ...previous, owner, loading: false })),
    });
  }, [owner, active, retry]);
  return {
    signedIn: Boolean(owner),
    checkingAuth: isLoading,
    company: owner && company.owner === owner ? company : {},
    price: owner && price.owner === owner ? price : {},
    retry: () => setRetry((value) => value + 1),
  };
}
