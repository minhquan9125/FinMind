/* One sidebar for the Researcher screens. Each static export mounts this file. */
(() => {
  const slot = document.querySelector('[data-finmind-sidebar]');
  if (!slot) return;

  const page = slot.dataset.finmindSidebar;
  const pages = {
    dashboard: '../finmind_dashboard_nghi_n_c_u_ng_b_watchlist_linh_ho_t/code.html',
    company: '../finmind_r04_chi_ti_t_doanh_nghi_p_li_n_k_t_kh_m_ph_quan_h_d_li_u/code.html',
    companyIndex: '../finmind_doanh_nghiep_duoc_ho_tro/code.html',
    research: '../finmind_r01_tr_l_nghi_n_c_u_b_n_chu_n_h_a_chu_i_d_li_u/code.html',
    watchlist: '../finmind_r05_danh_s_ch_theo_d_i_b_n_chu_n_h_a_kh_ng_seed_m_u/code.html',
    graph: '../finmind_r06_th_tri_th_c_chu_n_h_a_hub_and_spoke_b_c_c_100vh/code.html',
    profile: '../finmind_ho_so_ca_nhan_mau/code.html',
    login: '../finmind_p02_ng_nh_p_b_n_tinh_ch_nh_chu_n_h_a/code.html'
  };
  const icons = {
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    company: '<path d="M4 21V5h10v16M14 9h6v12M2 21h20M7 8h2M7 12h2M7 16h2M17 12h1M17 16h1"/>',
    research: '<path d="M4 5h16v12H9l-5 3V5z"/>',
    watchlist: '<path d="M5 4h14v17l-7-4-7 4V4z"/>',
    graph: '<circle cx="12" cy="4" r="2"/><circle cx="4" cy="12" r="2"/><circle cx="20" cy="12" r="2"/><circle cx="12" cy="20" r="2"/><path d="m10.5 5.5-5 5m8-5 5 5m-13 3 5 5m8-5-5 5"/>',
    profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    logout: '<path d="M10 17v3H4V4h6v3M14 8l4 4-4 4M18 12H9"/>',
    chevron: '<path d="m6 14 6-6 6 6"/>'
  };
  const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
  const hashParams = new URLSearchParams(window.location.hash.split('?')[1] || '');
  const queryParams = new URLSearchParams(window.location.search);
  let companyCode = (queryParams.get('company') || hashParams.get('company') || 'FPT').toUpperCase();
  if (!/^[A-Z0-9]{2,5}$/.test(companyCode)) companyCode = 'FPT';

  const links = {
    dashboard: pages.dashboard,
    company: '',
    research: '',
    watchlist: pages.watchlist,
    graph: ''
  };
  function updateLinks(ticker) {
    const normalized = String(ticker || '').toUpperCase();
    if (!/^[A-Z0-9]{2,5}$/.test(normalized)) return;
    companyCode = normalized;
    links.company = pages.companyIndex;
    links.research = `${pages.research}#r01?company=${encodeURIComponent(companyCode)}&period=FY2025`;
    links.graph = `${pages.graph}#r06?company=${encodeURIComponent(companyCode)}`;
    for (const key of ['company', 'research', 'graph']) {
      slot.querySelector(`[data-sidebar-link="${key}"]`)?.setAttribute('href', links[key]);
    }
  }
  updateLinks(companyCode);

  const navItem = (key, label) => {
    const active = key === 'company' && page === 'r_catalog'
      || page === ({dashboard:'r00',company:'r04',research:'r01',watchlist:'r05',graph:'r06'}[key]);
    const current = active ? ' aria-current="page"' : '';
    return `<a class="fm-nav-link" data-sidebar-link="${key}" href="${links[key]}"${current} title="${label}">${icon(key)}<span class="fm-nav-text">${label}</span></a>`;
  };

  slot.id = 'finmind-sidebar';
  document.body.dataset.finmindPage = page;
  slot.innerHTML = `
    <a class="fm-brand" href="${pages.dashboard}" aria-label="FinMind - Tổng quan"><span class="fm-mark">FM</span><span class="fm-brand-name">FinMind</span></a>
    <div class="fm-nav-wrap">
      <div class="fm-nav-group"><p class="fm-group-label">Nghiên cứu chính</p><nav aria-label="Nghiên cứu chính">
        ${navItem('dashboard', 'Tổng quan')}
        ${navItem('company', 'Doanh nghiệp')}
        ${navItem('research', 'Trợ lý nghiên cứu')}
        ${navItem('watchlist', 'Danh sách theo dõi')}
      </nav></div>
      <div class="fm-nav-group"><p class="fm-group-label">Tính năng mở rộng</p><nav aria-label="Tính năng mở rộng">
        ${navItem('graph', 'Đồ thị tri thức')}
      </nav></div>
    </div>
    <div class="fm-profile">
      <div class="fm-profile-menu" id="fm-profile-menu" hidden>
        <a href="${pages.profile}">${icon('profile')}Hồ sơ cá nhân</a>
        <div class="fm-menu-divider"></div>
        <a class="fm-logout" href="${pages.login}">${icon('logout')}Đăng xuất</a>
      </div>
      <button class="fm-profile-button" id="fm-profile-button" type="button" aria-label="Mở menu tài khoản" aria-controls="fm-profile-menu" aria-expanded="false">
        <span class="fm-profile-person"><span class="fm-avatar">NA</span><span class="fm-profile-copy"><span class="fm-profile-name">Nguyễn Văn A</span><span class="fm-profile-role">Nhà nghiên cứu</span></span></span>
        <span class="fm-chevron">${icon('chevron')}</span>
      </button>
    </div>`;
  updateLinks(companyCode);

  function syncActiveLink() {
    const activeKey = {r00:'dashboard',r01:'research',r04:'company',r05:'watchlist',r06:'graph',r_catalog:'company'}[page];
    slot.querySelectorAll('.fm-nav-link').forEach((link) => {
      if (link.dataset.sidebarLink === activeKey) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
  }
  window.addEventListener('hashchange', syncActiveLink);
  syncActiveLink();

  const toggle = slot.querySelector('#fm-profile-button');
  const menu = slot.querySelector('#fm-profile-menu');
  function setOpen(open) {
    menu.hidden = !open;
    toggle.setAttribute('aria-expanded', String(open));
  }
  toggle.addEventListener('click', (event) => {
    event.stopPropagation();
    setOpen(menu.hidden);
  });
  document.addEventListener('click', (event) => {
    if (!slot.contains(event.target)) setOpen(false);
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') setOpen(false);
  });

  window.FinMindSidebar = { setCompany: updateLinks };
})();
