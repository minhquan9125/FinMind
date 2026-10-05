/* bridge.js - loaded at the end of every Stitch page (inside the app shell iframe).
 * It does NOT change the Stitch UI. It only:
 *   1. turns cross-screen links (#a01 / #a02?source=... ) and programmatic hash jumps into app navigation
 *   2. receives deep-link hashes from the shell (keep-alive pages)
 *   3. wires the profile menu ("Thông tin tài khoản" / "Đăng xuất")
 *   4. supports ?focus=budget on the configuration screen */
(function () {
  'use strict';
  var R = window.FM_ROUTES;
  var me = document.body.getAttribute('data-fm-screen');
  var inShell = window.parent !== window;
  var lastHash = location.hash;

  function go(screen, innerParams, fromSidebar) {
    var route = R.screens[screen].route;
    var q = R.toOuter(screen, innerParams).toString();
    if (inShell) {
      window.parent.postMessage({ fm: 'nav', screen: screen, query: q, sidebar: !!fromSidebar }, '*');
    } else { // page opened on its own -> hand over to the shell
      location.href = '../index.html#/' + route + (q ? '?' + q : '');
    }
  }

  // 1a. clicks on <a href="#a0X..."> that point to another screen
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#a0"]');
    if (!a) return;
    var p = R.parseInner(a.getAttribute('href'));
    if (R.screens[p.screen] && p.screen !== me) {
      e.preventDefault();
      e.stopPropagation();
      go(p.screen, p.params, !!a.closest('aside'));
    }
  }, true);

  // 1b. programmatic jumps such as onclick="window.location.hash='a01?trace=...'"
  window.addEventListener('hashchange', function (e) {
    var p = R.parseInner(location.hash);
    if (R.screens[p.screen] && p.screen !== me) {
      e.stopImmediatePropagation();
      history.replaceState(null, '', lastHash || ('#' + me));
      go(p.screen, p.params);
      return;
    }
    lastHash = location.hash;
    applyFocus();
  }, true);

  // 2. deep link from the shell
  // the shell keeps pages alive; when leaving a screen close its open drawers/modals so they are not stale on return
  var CLOSERS = ['closeDetailPanel', 'closeDrawer', 'closeCompareModal', 'closeConfirmModal', 'closeDocDetail', 'closeFreezeWizard', 'closeManifest',
    'closeActivateModal', 'closeDetailDrawer', 'closeEditDrawer', 'closeHistoryDrawer', 'closeRestoreModal', 'closeExportModal'];
  function closeOverlays() {
    CLOSERS.forEach(function (n) { if (typeof window[n] === 'function') { try { window[n](); } catch (err) {} } });
    document.querySelectorAll('.fm-overlay, .fm-menu').forEach(function (n) { n.remove(); });
  }
  window.addEventListener('message', function (e) {
    var d = e.data;
    if (d && d.fm === 'leave') { closeOverlays(); return; }
    if (d && d.fm === 'back') { renderBack(d.back); return; }
    if (!d || d.fm !== 'hash') return;
    if (location.hash === d.hash) {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    } else {
      location.hash = d.hash;
    }
  });

  // 5. contextual back pill ("Quay lại: <screen>") above the breadcrumb, only after a cross-screen jump
  function renderBack(back) {
    var old = document.querySelector('.fm-back'); if (old) old.remove();
    if (!back) return;
    var crumb = null, links = document.querySelectorAll('a[href="#a00"]');
    for (var i = 0; i < links.length; i++) { if (!links[i].closest('aside')) { crumb = links[i].parentElement; break; } }
    var host = crumb || document.querySelector('main h1, h1');
    if (!host) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'fm-back';
    b.innerHTML = '<span class="material-symbols-outlined">arrow_back</span>Quay lại: ' + back.label;
    b.addEventListener('click', function () { b.remove(); window.parent.postMessage({ fm: 'goBack', hash: back.hash }, '*'); });
    host.parentElement.insertBefore(b, host);
  }

  // 4. focus a section (A04: ?focus=budget)
  function applyFocus() {
    var p = R.parseInner(location.hash);
    var f = p.params.get('focus');
    if (!f) return;
    var needle = f === 'budget' ? 'Ngân sách API' : null;
    if (!needle) return;
    var hs = document.querySelectorAll('h1,h2,h3,h4');
    for (var i = 0; i < hs.length; i++) {
      if (hs[i].textContent.indexOf(needle) > -1 && !hs[i].closest('[id$="Drawer"],[id$="Modal"]')) {
        var card = hs[i].closest('section') || hs[i].closest('div[class*="rounded"]') || hs[i].parentElement;
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('fm-focus-ring');
        setTimeout(function () { card.classList.remove('fm-focus-ring'); }, 2400);
        return;
      }
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(applyFocus, 150); });
  else setTimeout(applyFocus, 150);

  // ---- tiny UI helpers (toast / modal / menu) styled by css/admin.css -------------------------
  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; }
  function toast(msg) {
    var t = el('div', 'fm-toast', msg); document.body.appendChild(t);
    setTimeout(function () { t.classList.add('fm-toast-out'); setTimeout(function () { t.remove(); }, 300); }, 3200);
  }
  function modal(title, bodyHtml, buttons) {
    var ov = el('div', 'fm-overlay'); var box = el('div', 'fm-modal');
    box.appendChild(el('div', 'fm-modal-title', title)); box.appendChild(el('div', 'fm-modal-body', bodyHtml));
    var row = el('div', 'fm-modal-actions');
    buttons.forEach(function (b) {
      var btn = el('button', 'fm-btn ' + (b.primary ? 'fm-btn-primary' : ''), b.label);
      btn.addEventListener('click', function () { ov.remove(); if (b.onClick) b.onClick(); });
      row.appendChild(btn);
    });
    box.appendChild(row); ov.appendChild(box);
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.remove(); });
    document.body.appendChild(ov);
  }

  // 3. profile menu
  function findProfile() {
    var aside = document.querySelector('aside'); if (!aside) return null;
    var nodes = aside.querySelectorAll('*'); var leaf = null;
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].children.length === 0 && nodes[i].textContent.trim() === 'Quản trị viên') { leaf = nodes[i]; break; }
    }
    if (!leaf) return null;
    var c = leaf;
    while (c.parentElement && c.parentElement !== aside && c.parentElement.textContent.indexOf('Quản trị viên') > -1 && c.parentElement.textContent.length < 140) c = c.parentElement;
    return c;
  }
  var menu = null;
  function closeMenu() { if (menu) { menu.remove(); menu = null; } }
  function openMenu(anchor) {
    closeMenu();
    var r = anchor.getBoundingClientRect();
    menu = el('div', 'fm-menu');
    menu.style.left = Math.max(8, r.left) + 'px';
    menu.style.width = Math.max(200, r.width) + 'px';
    menu.style.bottom = (window.innerHeight - r.top + 6) + 'px';
    var i1 = el('button', 'fm-menu-item', '<span class="material-symbols-outlined">person</span>Thông tin tài khoản');
    var i2 = el('button', 'fm-menu-item fm-menu-danger', '<span class="material-symbols-outlined">logout</span>Đăng xuất');
    i1.addEventListener('click', function () {
      closeMenu();
      modal('Thông tin tài khoản',
        '<div class="fm-kv"><span>Tên hiển thị</span><b>Quản trị viên</b></div>' +
        '<div class="fm-kv"><span>Vai trò</span><b>System Admin</b></div>' +
        '<div class="fm-note">Dữ liệu minh họa</div>',
        [{ label: 'Đóng', primary: true }]);
    });
    i2.addEventListener('click', function () {
      closeMenu();
      modal('Đăng xuất', 'Bạn muốn đăng xuất khỏi FinMind Admin Console?', [
        { label: 'Hủy' },
        { label: 'Đăng xuất', primary: true, onClick: function () { toast('Đã đăng xuất (minh họa). Project Admin chưa có màn đăng nhập.'); } }
      ]);
    });
    menu.appendChild(i1); menu.appendChild(i2); document.body.appendChild(menu);
  }
  function initProfile() {
    var p = findProfile(); if (!p) return;
    p.classList.add('fm-profile');
    p.addEventListener('click', function (e) { e.stopPropagation(); menu ? closeMenu() : openMenu(p); });
    document.addEventListener('click', closeMenu);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeMenu(); });
  }
  initProfile();

  window.FinMindNav = { go: go, toast: toast, modal: modal };
})();
