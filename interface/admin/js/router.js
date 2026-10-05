/* router.js - hash router of the app shell (index.html).
 *   #/overview  #/traces  #/sources  #/corpus  #/configuration  #/audit   (+ ?query)
 * Each screen is a Stitch page kept alive in its own iframe, so demo state (paused source,
 * new config candidate, selected trace ...) survives sidebar navigation without a full reload. */
(function () {
  'use strict';
  var R = window.FM_ROUTES;
  var host = document.getElementById('views');
  var frames = {};   // screenId -> { el, ready, queue }
  var current = null;
  var pendingBack = null;   // { hash, label } set when a page link jumps to another screen

  function parseOuter() {
    var h = location.hash.replace(/^#\/?/, '');
    var i = h.indexOf('?');
    return { name: (i < 0 ? h : h.slice(0, i)) || 'overview', params: new URLSearchParams(i < 0 ? '' : h.slice(i + 1)) };
  }

  function ensureFrame(screen, innerHash) {
    if (frames[screen]) return frames[screen];
    var f = { ready: false, queue: [] };
    var ifr = document.createElement('iframe');
    ifr.className = 'view';
    ifr.setAttribute('title', R.screens[screen].label);
    ifr.addEventListener('load', function () {
      f.ready = true;
      f.queue.forEach(function (m) { ifr.contentWindow.postMessage(m, '*'); });
      f.queue = [];
    });
    ifr.src = R.screens[screen].page + innerHash;
    host.appendChild(ifr);
    f.el = ifr; frames[screen] = f;
    return f;
  }

  function render() {
    var o = parseOuter();
    var screen = R.byRoute[o.name];
    if (!screen) { location.replace('#/overview'); return; }
    var innerHash = R.toInner(screen, o.params);
    if (current && current !== screen && frames[current] && frames[current].ready) frames[current].el.contentWindow.postMessage({ fm: 'leave' }, '*');
    current = screen;
    var existed = !!frames[screen];
    var f = ensureFrame(screen, innerHash);
    Object.keys(frames).forEach(function (k) { frames[k].el.style.display = (k === screen) ? 'block' : 'none'; });
    document.title = 'FinMind Admin Console – ' + R.screens[screen].label;
    // an already-loaded page only needs the new deep link (when there is one)
    if (existed && (o.params.toString() || R.plainReset.indexOf(screen) > -1)) {
      var msg = { fm: 'hash', hash: innerHash };
      if (f.ready) f.el.contentWindow.postMessage(msg, '*'); else f.queue.push(msg);
    }
    // contextual back link: only right after a jump from another screen, cleared on sidebar / normal navigation
    var back = (pendingBack && pendingBack.screen !== screen && screen !== 'a00') ? pendingBack : null;  // overview is home: no back pill there
    pendingBack = null;
    var bmsg = { fm: 'back', back: back ? { hash: back.hash, label: back.label } : null };
    if (f.ready) f.el.contentWindow.postMessage(bmsg, '*'); else f.queue.push(bmsg);
  }

  function navigate(screen, query) {
    var target = '#/' + R.screens[screen].route + (query ? '?' + query : '');
    if (location.hash === target) render(); else location.hash = target;
  }

  window.addEventListener('message', function (e) {
    var d = e.data;
    if (d && d.fm === 'nav' && R.screens[d.screen]) {
      pendingBack = (current && !d.sidebar) ? { screen: current, hash: location.hash, label: R.screens[current].label } : null;
      navigate(d.screen, d.query);
    }
    if (d && d.fm === 'goBack' && d.hash) location.hash = d.hash;
  });
  window.addEventListener('hashchange', render);
  if (!location.hash || location.hash === '#') location.replace('#/overview');
  render();

  window.FinMindApp = { navigate: navigate };
})();
