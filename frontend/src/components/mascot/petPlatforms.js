// Tìm các "bậc" trên trang (cạnh trên của card, khung, bảng...) để linh vật đứng / nhảy lên.

export const EDGE = 34; // khoảng cách tối thiểu tới mép bậc (px)
export const TOP_SAFE = 230; // không chọn bậc quá cao (đầu + bong bóng sẽ bị che)
const LAND_MIN_TOP = 180; // khi rơi, chỉ đáp xuống bậc thấp hơn mức này
const MIN_W = 140; // bậc tự nhận diện
const TAGGED_MIN_W = 56; // bậc gắn data-mascot-platform (cho phép cả Button nhỏ)
const MIN_H = 36;
const MAX_SCAN = 700;

const SELECTOR =
  "section, article, aside, form, table, [class*='rounded'], [class*='card'], [class*='border']";

export const viewW = () => document.documentElement.clientWidth;
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

/* ------------------------------------------------------------------ */
/* Không cản trở người dùng: kiểm tra vùng thân linh vật sẽ che         */
/* ------------------------------------------------------------------ */

export const BODY_HALF_W = 40; // nửa bề ngang thân robot (px)
export const BODY_H = 135; // chiều cao robot tính từ bàn chân (px)

const INTERACTIVE =
  "a[href], button, input, select, textarea, label, summary, video, iframe, " +
  "[role='button'], [role='link'], [role='tab'], [role='menuitem'], [role='checkbox'], [role='switch'], " +
  "[contenteditable=''], [contenteditable='true']";

/** Phần tử của trang nằm dưới điểm (x, y), bỏ qua chính linh vật / dock / chat. */
function pageElementAt(x, y) {
  for (const el of document.elementsFromPoint(x, y)) {
    if (!el.closest("[data-mascot-root]")) return el;
  }
  return null;
}

function hasOwnText(el) {
  for (const n of el.childNodes) {
    if (n.nodeType === Node.TEXT_NODE && n.textContent.trim()) return true;
  }
  return false;
}

/** Dưới con trỏ có nút / link / ô nhập... không. */
export function interactiveAt(x, y) {
  return !!pageElementAt(x, y)?.closest(INTERACTIVE);
}

/**
 * Chấm điểm một chỗ đứng (x, y = bàn chân):
 *   0 = trống hoàn toàn · 1 = che chữ · 2 = che phần tử bấm được / tràn ra ngoài màn hình
 */
export function spotScore(x, y) {
  if (x - BODY_HALF_W < 0 || x + BODY_HALF_W > viewW()) return 2;

  // Không đứng sau cụm nút "Gọi bé lại" / chat ở góc màn hình
  const dock = document.querySelector("[data-mascot-dock]")?.getBoundingClientRect();
  if (dock && x + BODY_HALF_W > dock.left - 8 && x - BODY_HALF_W < dock.right && y > dock.top - 8 && y - BODY_H < dock.bottom) {
    return 2;
  }

  let worst = 0;
  for (const fx of [-0.8, 0, 0.8]) {
    for (const fy of [0.08, 0.35, 0.62, 0.9]) {
      const px = x + fx * BODY_HALF_W;
      const py = y - fy * BODY_H;
      if (py < 0 || py > window.innerHeight) continue;
      const el = pageElementAt(px, py);
      if (!el) continue;
      if (el.closest(INTERACTIVE)) return 2;
      if (hasOwnText(el)) worst = 1;
    }
  }
  return worst;
}

/** Tìm chỗ đứng ít che nhất trên một bậc, ưu tiên gần preferX. Trả về { offset, score } hoặc null. */
export function findSafeOffset(surf, preferX) {
  const hi = Math.max(EDGE, surf.width - EDGE);
  const offsets = [];
  for (let o = EDGE; o <= hi; o += 36) offsets.push(o);
  const pref = preferX - surf.left;
  offsets.sort((a, b) => Math.abs(a - pref) - Math.abs(b - pref));

  let relaxed = null;
  for (const o of offsets.slice(0, 40)) {
    const score = spotScore(surf.left + o, surf.top);
    if (score === 0) return { offset: o, score };
    if (score === 1 && relaxed === null) relaxed = o;
  }
  return relaxed === null ? null : { offset: relaxed, score: 1 };
}

/** Bậc hiện tại còn đứng được không (còn trong DOM, còn trong khung nhìn). */
export function isPlatformUsable(el) {
  if (!el || !el.isConnected) return false;
  const r = el.getBoundingClientRect();
  return (
    r.width >= TAGGED_MIN_W &&
    r.top > 160 &&
    r.top < window.innerHeight - 30 &&
    r.right > 40 &&
    r.left < viewW() - 40
  );
}

function hasVisibleBox(cs) {
  const bg = cs.backgroundColor;
  return (
    parseFloat(cs.borderTopWidth) > 0 ||
    cs.boxShadow !== "none" ||
    (bg !== "transparent" && bg !== "rgba(0, 0, 0, 0)")
  );
}

/**
 * Lấy danh sách bậc đang nhìn thấy:
 *  1. Ưu tiên phần tử gắn `data-mascot-platform` (Card, Button, Navbar...).
 *  2. Trang chưa gắn attribute nào → tự nhận diện khung có viền/nền rõ ràng.
 */
export function findPlatforms() {
  const out = [];
  const tagged = document.querySelectorAll("[data-mascot-platform]");
  const auto = tagged.length === 0;
  const nodes = auto ? document.querySelectorAll(SELECTOR) : tagged;
  const minW = auto ? MIN_W : TAGGED_MIN_W;
  const W = viewW();
  const H = window.innerHeight;
  const len = Math.min(nodes.length, MAX_SCAN);

  for (let i = 0; i < len && out.length < 60; i++) {
    const el = nodes[i];
    const r = el.getBoundingClientRect();
    if (r.width < minW || (auto && r.height < MIN_H)) continue;
    if (r.top < TOP_SAFE || r.top > H - 70 || r.left < 0 || r.right > W) continue;
    if (el.closest("[data-mascot-root]")) continue;

    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || Number(cs.opacity) < 0.5) continue;
    if (auto && !hasVisibleBox(cs)) continue;

    // Cạnh trên phải thật sự nhìn thấy (không bị phần tử khác đè lên)
    const probe = document.elementFromPoint(r.left + r.width / 2, r.top + 3);
    if (!probe || !(probe === el || el.contains(probe))) continue;

    out.push(el);
  }
  return out;
}

/** Khi đang rơi từ prevY xuống y: tìm bậc đầu tiên nằm ngay dưới chân. */
export function platformBelow(candidates, x, prevY, y) {
  let best = null;
  for (const el of candidates) {
    if (!el.isConnected) continue;
    const r = el.getBoundingClientRect();
    if (x < r.left + 12 || x > r.right - 12) continue;
    if (r.top < prevY - 2 || r.top > y || r.top < LAND_MIN_TOP) continue;
    if (!best || r.top < best.top) best = { el, top: r.top };
  }
  return best;
}

/**
 * Bậc mà con trỏ đang "chỉ vào" (dùng cho CHASE):
 * con trỏ nằm trong card → card sâu nhất chứa nó; không thì bậc gần nhất phía dưới con trỏ; null = sàn.
 */
export function surfaceUnderPoint(platforms, x, y) {
  let inside = null;
  let below = null;
  for (const el of platforms) {
    if (!el.isConnected) continue;
    const r = el.getBoundingClientRect();
    if (x < r.left + 10 || x > r.right - 10) continue;
    if (y >= r.top && y <= r.bottom) {
      if (!inside || r.top > inside.top) inside = { el, top: r.top };
    } else if (r.top >= y - 30 && (!below || r.top < below.top)) {
      below = { el, top: r.top };
    }
  }
  return (inside ?? below)?.el ?? null;
}

/** Chọn ngẫu nhiên một bậc khác để nhảy tới (mặc định ưu tiên gần, preferFar khi bỏ chạy). */
export function pickJumpTarget(platforms, currentAnchor, x, y, preferFar = false) {
  const options = [];
  let total = 0;

  for (const el of platforms) {
    if (el === currentAnchor) continue;
    const r = el.getBoundingClientRect();
    const lo = r.left + EDGE;
    const hi = r.right - EDGE;
    if (hi - lo < 20) continue;

    const nearestX = clamp(x, lo, hi);
    const dx = Math.abs(nearestX - x);
    const dy = Math.abs(r.top - y);
    if (dx > 650 || dy > 450) continue;
    if (dy < 12 && dx < 5) continue; // bậc lồng nhau, cùng độ cao → nhảy cũng như không

    const weight = preferFar ? 1 + (dx + dy) / 150 : 1 / (1 + (dx + dy) / 250);
    total += weight;
    options.push({ el, lo, hi, left: r.left, weight });
  }
  if (!options.length) return null;

  let roll = Math.random() * total;
  const chosen = options.find((o) => (roll -= o.weight) <= 0) ?? options[options.length - 1];
  const targetX = chosen.lo + Math.random() * (chosen.hi - chosen.lo);
  return { el: chosen.el, offset: targetX - chosen.left };
}
