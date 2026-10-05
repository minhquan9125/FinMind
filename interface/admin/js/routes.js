/* Shared route map + query translation between
 *  - outer app routes   : index.html#/traces?trace=TRC-DEMO-004
 *  - inner Stitch hashes: pages/A01-traces.html#a01?trace=TRC-DEMO-004
 * Used by js/router.js (shell) and js/bridge.js (inside every page). */
(function (g) {
  var screens = {
    a00: { route: 'overview', page: 'pages/A00-overview.html', label: 'Tổng quan vận hành' },
    a01: { route: 'traces', page: 'pages/A01-traces.html', label: 'Theo dõi truy vấn' },
    a02: { route: 'sources', page: 'pages/A02-sources.html', label: 'Cấu hình nguồn' },
    a03: { route: 'corpus', page: 'pages/A03-corpus.html', label: 'Phiên bản kho dữ liệu' },
    a04: { route: 'configuration', page: 'pages/A04-configuration.html', label: 'Ngưỡng & ngân sách API' },
    a05: { route: 'audit', page: 'pages/A05-audit.html', label: 'Nhật ký kiểm toán' }
  };
  var byRoute = {};
  Object.keys(screens).forEach(function (k) { byRoute[screens[k].route] = k; });

  // "v2.4" | "CFG v2.4" | "CFG-v2.4" -> "v2.4"
  function cfgShort(x) { return String(x || '').replace(/^CFG[\s-]*/i, '').replace(/^V/, 'v'); }
  // "v2.4" -> "CFG-v2.4"
  function cfgLong(x) { return 'CFG-' + cfgShort(x); }
  function corpusShort(x) { return String(x || '').replace(/^Corpus[\s-]*/i, '').replace(/^V/, 'v'); }

  function copy(p) { var o = new URLSearchParams(); p.forEach(function (v, k) { o.set(k, v); }); return o; }

  // inner params (Stitch page hash) -> outer params
  function toOuter(screen, p) {
    var o = copy(p);
    if (screen === 'a04' && o.has('cfg')) { o.set('config', cfgLong(o.get('cfg'))); o.delete('cfg'); }
    if (screen === 'a05' && o.has('config')) { o.set('config', cfgLong(o.get('config'))); }
    if ((screen === 'a03' || screen === 'a05') && o.has('corpus')) { o.set('corpus', corpusShort(o.get('corpus'))); }
    return o;
  }
  // outer params -> inner hash for the Stitch page
  function toInner(screen, p) {
    var o = copy(p);
    if (screen === 'a04' && o.has('config')) { o.set('cfg', cfgShort(o.get('config'))); o.delete('config'); }
    if (screen === 'a05' && o.has('config')) { o.set('config', cfgShort(o.get('config'))); }
    var q = o.toString();
    return '#' + screen + (q ? '?' + q : '');
  }
  function parseInner(hash) {
    var h = String(hash || '').replace(/^#\/?/, '');
    var i = h.indexOf('?');
    return { screen: (i < 0 ? h : h.slice(0, i)), params: new URLSearchParams(i < 0 ? '' : h.slice(i + 1)) };
  }

  // screens whose deep-link filter must be cleared when the sidebar is used without parameters
  var plainReset = ['a05'];

  g.FM_ROUTES = { plainReset: plainReset, screens: screens, byRoute: byRoute, toOuter: toOuter, toInner: toInner, parseInner: parseInner, cfgShort: cfgShort, cfgLong: cfgLong };
})(window);
