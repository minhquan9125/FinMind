import './finmindMark.css';

/** The supplied logo, framed around its FM monogram without altering the asset. */
export default function FinMindMark() {
  return <span className="finmind-logo-mark" aria-hidden="true">
    <img src="/images/finmind-logo.png" alt="" width="1254" height="1254" decoding="async" />
  </span>;
}
