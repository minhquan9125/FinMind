export default function AppIcon({ name = 'document', className = '', ...props }) {
  const paths = {
    pin: 'M8 3h8 M9 3v6l-3 5h12l-3-5V3 M12 14v7',
    search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    close: 'M6 6l12 12 M6 18 18 6',
    check: 'M5 12l4 4L19 6',
    chevron: 'M9 5l7 7-7 7',
    down: 'M5 9l7 7 7-7',
    arrow: 'M4 12h16 M13 5l7 7-7 7',
    external: 'M14 3h7v7 M21 3l-10 10 M10 3H3v18h18v-7',
    database: 'M21 6c0 2-4 3-9 3S3 8 3 6s4-3 9-3 9 1 9 3 M3 6v12c0 2 4 3 9 3s9-1 9-3V6 M3 12c0 2 4 3 9 3s9-1 9-3',
    calendar: 'M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16',
    shield: 'M12 3l9 4v5c0 5-9 10-9 10S3 17 3 12V7z M8 12l3 3 5-6',
    lock: 'M5 10h14v11H5z M8 10V7a4 4 0 0 1 8 0v3',
    eye: 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    link: 'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',
    chart: 'M12 3v9h9 M21 15a9 9 0 1 1-12-12',
    help: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5 M12 17h.01',
    settings: 'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6',
    profile: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-2a8 8 0 0 1 16 0v2',
    logout: 'M10 3H3v18h7 M8 12h13 M16 7l5 5-5 5',
    download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
    alert: 'M12 3 2 21h20z M12 9v5 M12 17h.01',
    document: 'M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6',
    copilot: 'M4 4h16v12H9l-5 4z M8 8h8 M8 12h5',
    compare: 'M5 20V10 M12 20V4 M19 20v-7',
    history: 'M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2',
    plus: 'M12 5v14 M5 12h14',
    dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    companies: 'M5 21V5h14v16 M9 9h1 M14 9h1 M9 13h1 M14 13h1 M10 21v-4h4v4',
    watchlist: 'M6 3h12v18l-6-4-6 4z',
    graph: 'M8 6h8 M6 8v8 M8 18h8 M18 8v8 M3 3h5v5H3z M16 3h5v5h-5z M3 16h5v5H3z M16 16h5v5h-5z',
    send: 'M12 20V4 M5 11l7-7 7 7',
    stop: 'M5 5h14v14H5z',
  };
  const aliases = { overview:'dashboard', sources:'link', ingestion:'download', jobs:'document', corpus:'database', traces:'compare', evaluation:'check', configuration:'settings', audit:'history', add:'plus', arrow_forward:'arrow', bookmark:'watchlist', bookmark_border:'watchlist', calendar_today:'calendar', check_circle:'check', chevron_right:'chevron', description:'document', expand_more:'down', explore:'graph', filter_alt_off:'settings', open_in_new:'external', pie_chart:'chart', verified:'shield', verified_user:'shield', visibility:'eye', inventory_2:'database' };
  const icon = aliases[name] || name;
  return <svg className={`fm-icon ${className}`} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[icon] || paths.document} /></svg>;
}
