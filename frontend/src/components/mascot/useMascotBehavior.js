// "Bộ não" của linh vật — Behavior State Machine.
//
// Trạng thái lớn (behavior):
//   WANDER   – tự đi dạo, chạy, nhảy giữa các bậc, thỉnh thoảng ngồi vắt vẻo trên mép card
//   SLEEP    – không có tương tác 8s → ngồi gục ngủ ngay trên bậc hiện tại (Zzz)
//   STARTLED – bị click khi đang ngủ → giật mình nảy lên, hiện "!" + mặt quạu, rồi chạy vụt đi chỗ khác
//   CHASE    – bấm "Gọi bé lại" → chạy/nhảy về phía con trỏ chuột
//   DRAG     – đang bị người dùng kéo đi
//
// Toạ độ (x, y) = điểm bàn chân, tính theo px của viewport. Scene 3D đọc trực tiếp từ ref này
// mỗi frame (không re-render React); chỉ khi đổi animation mới setState.
import { useEffect, useRef, useState } from "react";
import {
  BODY_H,
  BODY_HALF_W,
  EDGE,
  findPlatforms,
  findSafeOffset,
  interactiveAt,
  isPlatformUsable,
  pickJumpTarget,
  platformBelow,
  spotScore,
  surfaceUnderPoint,
  viewW,
} from "./petPlatforms";

export const BEHAVIOR = {
  WANDER: "WANDER",
  SLEEP: "SLEEP",
  STARTLED: "STARTLED",
  CHASE: "CHASE",
  DRAG: "DRAG",
};

// Khung DOM đi theo linh vật (vùng bấm, bong bóng, Zzz, "!")
export const PET_W = 150;
export const PET_H = 180;
export const FOOT_PAD = 8; // khoảng từ chân tới đáy khung DOM (px)

const WALK_SPEED = 75; // px/s
const RUN_SPEED = 260; // px/s — khi bỏ chạy / đuổi theo chuột
const GRAVITY = 2400; // px/s²
const GRAB_OFFSET = 70; // khi kéo: chân nằm dưới con trỏ bao nhiêu px
const SLEEP_AFTER_MS = 8000;
const SIT_MS = [4000, 8000];
const CHASE_MS = 9000;
const ALERT_MS = 1800;
const POKE_WINDOW_MS = 2000;
const POKES_TO_DIZZY = 4;
const THINK_MS = [3000, 7000]; // nghỉ giữa các lần tự đi dạo
const SAFETY_CHECK_MS = 800; // định kỳ kiểm tra chỗ đứng có đang che nội dung không
const YIELD_MS = 1500; // nhường đường: click xuyên qua linh vật trong khoảng này
const CHASE_SIDE_GAP = 75; // khi được gọi: đứng cạnh con trỏ, không đè lên

const floorY = () => window.innerHeight - 6;
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);
const lerp = (a, b, t) => a + (b - a) * t;
const rand = (a, b) => a + Math.random() * (b - a);
const now = () => performance.now();

const AIRBORNE = ["jump", "hop", "startled", "fall", "drag"];
const TIMED = ["land", "wave", "dizzy", "sit"];
const CAN_DOZE = ["idle", "sit"];
const RESTING = ["idle", "sit", "sleep"];

function surfaceOf(anchor) {
  if (anchor) {
    const r = anchor.getBoundingClientRect();
    return { left: r.left, width: r.width, top: r.top };
  }
  return { left: 0, width: viewW(), top: floorY() }; // anchor = null → sàn (đáy màn hình)
}

/** Trạng thái nội bộ → animation của robot. */
function robotMode(s) {
  switch (s.mode) {
    case "walk":
      return s.speed > 120 ? "run" : "walk";
    case "chase":
      return s.moving ? "run" : "happy";
    case "hop":
    case "fall":
    case "jump":
      return "jump";
    default:
      return s.mode; // idle, sit, sleep, startled, drag, wave, dizzy, land
  }
}

function behaviorOf(s, t) {
  if (s.mode === "drag") return BEHAVIOR.DRAG;
  if (s.mode === "sleep") return BEHAVIOR.SLEEP;
  if (s.mode === "startled" || t < s.alertUntil) return BEHAVIOR.STARTLED;
  if (t < s.chaseUntil) return BEHAVIOR.CHASE;
  return BEHAVIOR.WANDER;
}

export function useMascotBehavior({ paused = false, wander = true, onEvent, sleepAfterMs = SLEEP_AFTER_MS }) {
  const followerRef = useRef(null);
  const onEventRef = useRef(onEvent);
  const flags = useRef({ paused, wander, sleepAfterMs });
  const st = useRef(null);
  const [view, setView] = useState({
    mode: "jump",
    facing: 0,
    side: "right",
    perch: false,
    alert: false,
    yielding: false,
    behavior: BEHAVIOR.WANDER,
  });

  useEffect(() => {
    onEventRef.current = onEvent;
    flags.current = { paused, wander, sleepAfterMs };
  });

  if (!st.current) {
    st.current = {
      x: viewW() - 330, // rơi xuống bên trái cụm nút góc phải
      y: -PET_H, // xuất hiện bằng cách rơi từ trên xuống
      vx: 0,
      vy: 0,
      anchor: null, // phần tử đang đứng; null = sàn
      offsetX: 0, // vị trí chân so với mép trái của bậc
      mode: "fall",
      facing: 0,
      speed: WALK_SPEED,
      walkTo: 0,
      moving: false,
      arrived: false,
      jump: null,
      until: 0,
      nextThink: 0,
      candidates: [],
      chaseCache: { t: 0, platforms: [] },
      chaseUntil: 0,
      alertUntil: 0,
      yieldUntil: 0,
      nextSafety: 0,
      lastYieldCheck: 0,
      flee: false,
      lastActivity: now(),
      mouse: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
      pokes: [],
      pokeCount: 0,
      press: null,
      lastDrag: 0,
    };
  }

  const emit = (type) => onEventRef.current?.(type);

  /* ---------------- chuyển trạng thái ---------------- */

  const toIdle = (s, t = now()) => {
    s.until = 0;
    if (t < s.chaseUntil) {
      s.mode = "chase";
      s.arrived = false;
      return;
    }
    s.mode = "idle";
    s.facing = 0;
    s.nextThink = t + (s.flee ? 150 : rand(...THINK_MS));
  };

  const startFall = (s, vx = 0, vy = 0) => {
    s.mode = "fall";
    s.anchor = null;
    s.vx = vx;
    s.vy = vy;
    s.candidates = findPlatforms();
  };

  const land = (s, anchor, top) => {
    s.anchor = anchor;
    s.vx = 0;
    s.vy = 0;
    s.y = top;
    const surf = surfaceOf(anchor);
    s.offsetX = clamp(s.x - surf.left, EDGE, Math.max(EDGE, surf.width - EDGE));
    s.mode = "land";
    s.facing = 0;
    s.until = now() + (s.flee ? 150 : 380);
    if (!s.greeted) {
      s.greeted = true; // lần đầu xuất hiện: vẫy tay chào
      s.mode = "wave";
      s.until = now() + 1800;
    }
    emit("touchdown");
  };

  const startJump = (s, anchor, offset, opts = {}) => {
    const surf = surfaceOf(anchor);
    const x1 = surf.left + offset;
    const dist = Math.hypot(x1 - s.x, surf.top - s.y);
    s.jump = {
      x0: s.x,
      y0: s.y,
      anchor,
      offset,
      t: 0,
      dur: opts.dur ?? clamp(0.45 + dist / 900, 0.45, 1.1),
      h: opts.h ?? clamp((s.y - surf.top) / 2 + 70, 60, 280), // đủ cao để vượt qua bậc đích
    };
    s.facing = Math.abs(x1 - s.x) > 8 ? Math.sign(x1 - s.x) : 0;
    s.mode = opts.mode ?? "jump";
  };

  const startWalk = (s, to, speed = WALK_SPEED) => {
    s.walkTo = to;
    s.speed = speed;
    s.facing = Math.sign(to - s.offsetX) || 1;
    s.mode = "walk";
  };

  /* ---------------- chọn chỗ đứng không cản trở người dùng ---------------- */

  /** Chỗ đứng trên một bậc (null = sàn). strictOnly: chỉ nhận chỗ không che gì cả. */
  const safeSpotOn = (anchor, preferX, strictOnly = true) => {
    const spot = findSafeOffset(surfaceOf(anchor), preferX);
    if (!spot || (strictOnly && spot.score > 0)) return null;
    return { anchor, offset: spot.offset };
  };

  /** Chọn bậc khác để nhảy tới, chỉ nhận bậc còn chỗ trống. */
  const pickSafeJump = (s, preferFar = false, strictOnly = true) => {
    const platforms = findPlatforms();
    for (let i = 0; i < 4; i++) {
      const target = pickJumpTarget(platforms, s.anchor, s.x, s.y, preferFar);
      if (!target) break;
      const left = target.el.getBoundingClientRect().left;
      const spot = safeSpotOn(target.el, left + target.offset, strictOnly);
      if (spot) return spot;
      platforms.splice(platforms.indexOf(target.el), 1);
    }
    return s.anchor ? safeSpotOn(null, s.x + rand(-300, 300), strictOnly) : null; // xuống sàn
  };

  const goTo = (s, spot, speed = WALK_SPEED) => {
    if (spot.anchor === s.anchor) startWalk(s, spot.offset, speed);
    else startJump(s, spot.anchor, spot.offset);
  };

  /** Đang đứng che nội dung → dời sang chỗ trống gần nhất. allowRelaxed: chấp nhận chỗ chỉ che chữ. */
  const relocate = (s, allowRelaxed) => {
    const spot =
      safeSpotOn(s.anchor, s.x, true) ??
      pickSafeJump(s, false, true) ??
      (allowRelaxed ? safeSpotOn(s.anchor, s.x, false) ?? pickSafeJump(s, false, false) : null);
    if (!spot || (spot.anchor === s.anchor && Math.abs(spot.offset - s.offsetX) < 4)) return false;
    goTo(s, spot, 170);
    return true;
  };

  /** WANDER: tự quyết định làm gì tiếp theo (mọi điểm đến đều phải là chỗ trống). */
  const think = (s, t) => {
    if (s.flee) {
      // Bỏ chạy sang chỗ trống ở xa
      s.flee = false;
      const spot = pickSafeJump(s, true, true) ?? pickSafeJump(s, true, false);
      if (spot) return goTo(s, spot, RUN_SPEED);
      return toIdle(s, t);
    }

    const roll = Math.random();
    if (roll < 0.2) {
      s.mode = "sit"; // ngồi vắt vẻo trên mép card
      s.facing = 0;
      s.until = t + rand(...SIT_MS);
      return undefined;
    }
    if (roll < 0.5) {
      const spot = safeSpotOn(s.anchor, s.x + rand(-260, 260));
      if (spot && Math.abs(spot.offset - s.offsetX) > 30) {
        return startWalk(s, spot.offset, Math.random() < 0.25 ? 160 : WALK_SPEED);
      }
    } else if (roll < 0.85) {
      const spot = pickSafeJump(s);
      if (spot) return goTo(s, spot);
    }
    return toIdle(s, t);
  };

  /** CHASE: chạy trên bậc hiện tại, hoặc nhảy sang bậc mà con trỏ đang chỉ vào. */
  const chaseStep = (s, t, dt, surf) => {
    if (t - s.chaseCache.t > 400) s.chaseCache = { t, platforms: findPlatforms() };
    const m = s.mouse;
    const target = surfaceUnderPoint(s.chaseCache.platforms, m.x, m.y);
    const goalX = m.x + (s.x <= m.x ? -CHASE_SIDE_GAP : CHASE_SIDE_GAP); // đứng cạnh con trỏ

    if (target !== s.anchor) {
      const surf2 = surfaceOf(target);
      startJump(s, target, clamp(goalX - surf2.left, EDGE, Math.max(EDGE, surf2.width - EDGE)));
      s.arrived = false;
      return;
    }

    const goal = clamp(goalX - surf.left, EDGE, Math.max(EDGE, surf.width - EDGE));
    const d = goal - s.offsetX;
    if (Math.abs(d) > 18) {
      s.offsetX += Math.sign(d) * Math.min(Math.abs(d), RUN_SPEED * dt);
      s.facing = Math.sign(d);
      s.moving = true;
      if (Math.abs(d) > 60) s.arrived = false;
    } else {
      s.facing = 0;
      s.moving = false;
      if (!s.arrived) {
        s.arrived = true;
        emit("chase-arrive");
      }
    }
  };

  /* ---------------- mỗi frame ---------------- */

  const step = (t, dt) => {
    const s = st.current;
    const { paused: isPaused, wander: canWander } = flags.current;

    switch (s.mode) {
      case "drag":
        return; // vị trí do con trỏ quyết định

      case "fall": {
        const prevY = s.y;
        s.vy += GRAVITY * dt;
        s.y += s.vy * dt;
        s.x += s.vx * dt;
        s.vx *= Math.pow(0.4, dt);
        const W = viewW();
        if (s.x < 40 || s.x > W - 40) {
          s.x = clamp(s.x, 40, W - 40);
          s.vx = -s.vx * 0.5; // dội lại khi đập mép màn hình
        }
        if (s.vy > 0) {
          const hit = platformBelow(s.candidates, s.x, prevY, s.y);
          if (hit) {
            land(s, hit.el, hit.top);
            emit("land");
            return;
          }
        }
        if (s.y >= floorY()) {
          land(s, null, floorY());
          emit("land");
        }
        return;
      }

      case "jump":
      case "hop":
      case "startled": {
        const j = s.jump;
        j.t += dt;
        const p = Math.min(j.t / j.dur, 1);
        if (j.anchor && !j.anchor.isConnected) return startFall(s);
        const surf = surfaceOf(j.anchor); // bậc đích có thể đang trôi theo cuộn trang
        s.x = lerp(j.x0, surf.left + j.offset, p);
        s.y = lerp(j.y0, surf.top, p) - j.h * 4 * p * (1 - p);
        if (p >= 1) {
          if (j.anchor && !isPlatformUsable(j.anchor)) startFall(s);
          else land(s, j.anchor, surf.top);
        }
        return;
      }

      default: {
        // Đang đứng trên bậc: bậc cuộn khỏi màn hình / biến mất → rơi
        if (s.anchor && !isPlatformUsable(s.anchor)) return startFall(s);

        const surf = surfaceOf(s.anchor);
        if (s.mode === "walk") {
          const d = s.walkTo - s.offsetX;
          s.offsetX += Math.sign(d) * Math.min(Math.abs(d), s.speed * dt);
          if (Math.abs(d) < 2) toIdle(s, t);
        } else if (s.mode === "chase") {
          if (t > s.chaseUntil) {
            s.moving = false;
            toIdle(s, t);
            emit("chase-end");
          } else {
            chaseStep(s, t, dt, surf);
            if (s.mode !== "chase") return; // vừa bắt đầu nhảy
          }
        }

        s.offsetX = clamp(s.offsetX, EDGE, Math.max(EDGE, surf.width - EDGE));
        s.x = surf.left + s.offsetX;
        s.y = surf.top;

        if (s.until && t > s.until && TIMED.includes(s.mode)) toIdle(s, t);

        // Không cản trở: chỗ đang đứng/ngồi/ngủ mà che nội dung → tự dời đi
        if (t > s.nextSafety && RESTING.includes(s.mode) && t > s.chaseUntil) {
          s.nextSafety = t + SAFETY_CHECK_MS;
          const score = spotScore(s.x, s.y);
          if (score > 0 && relocate(s, score === 2)) s.lastActivity = t;
        }

        if (isPaused) return;
        if (!canWander) return;
        if (s.mode === "idle" && t > s.nextThink) think(s, t);

        // SLEEP: không tương tác 8s → ngồi gục ngay tại chỗ, chỉ tỉnh khi bị click
        if (CAN_DOZE.includes(s.mode) && t > s.chaseUntil && t - s.lastActivity > flags.current.sleepAfterMs) {
          s.mode = "sleep";
          s.facing = 0;
          s.until = 0;
          emit("sleep");
        }
      }
    }
  };

  /* ---------------- tương tác ---------------- */

  const poke = () => {
    const s = st.current;
    const t = now();
    s.lastActivity = t;
    if (AIRBORNE.includes(s.mode)) return;

    if (s.mode === "sleep") {
      // STARTLED: nảy lên, "!" + mặt quạu, sau đó bỏ chạy
      s.alertUntil = t + ALERT_MS;
      s.flee = true;
      startJump(s, s.anchor, s.offsetX, { h: 95, dur: 0.55, mode: "startled" });
      emit("startled");
      return;
    }

    s.pokes = s.pokes.filter((p) => t - p < POKE_WINDOW_MS);
    s.pokes.push(t);
    if (s.pokes.length >= POKES_TO_DIZZY) {
      s.pokes = [];
      s.mode = "dizzy";
      s.facing = 0;
      s.until = t + 1600;
      s.flee = true;
      s.alertUntil = t + 1600 + ALERT_MS;
      emit("dizzy");
      return;
    }

    s.pokeCount += 1;
    if (s.pokeCount % 2) {
      s.mode = "wave";
      s.facing = 0;
      s.until = t + 2000;
    } else {
      startJump(s, s.anchor, s.offsetX, { h: 55, dur: 0.5, mode: "hop" });
    }
    emit("poke");
  };

  /** CHASE: "Gọi bé lại". */
  const callPet = () => {
    const s = st.current;
    const t = now();
    s.lastActivity = t;
    s.chaseUntil = t + CHASE_MS;
    s.flee = false;
    s.alertUntil = 0;
    s.arrived = false;
    if (!AIRBORNE.includes(s.mode)) s.mode = "chase"; // đang nhảy thì đáp xong sẽ đuổi
    emit("chase");
  };

  const handlers = {
    onPointerDown: (e) => {
      if (e.button !== 0) return;
      e.currentTarget.setPointerCapture(e.pointerId);
      st.current.press = { x: e.clientX, y: e.clientY, dragging: false };
      st.current.lastActivity = now();
    },
    onPointerMove: (e) => {
      const s = st.current;
      const p = s.press;
      if (!p) return;
      if (!p.dragging && Math.hypot(e.clientX - p.x, e.clientY - p.y) > 6) {
        p.dragging = true;
        s.mode = "drag";
        s.anchor = null;
        s.facing = 0;
        s.vx = 0;
        s.vy = 0;
        s.chaseUntil = 0;
        emit("drag");
      }
      if (p.dragging) {
        const t = now();
        const nx = e.clientX;
        const ny = e.clientY + GRAB_OFFSET;
        if (s.lastDrag) {
          const dt = Math.max((t - s.lastDrag) / 1000, 0.008);
          s.vx = lerp(s.vx, (nx - s.x) / dt, 0.5);
          s.vy = lerp(s.vy, (ny - s.y) / dt, 0.5);
        }
        s.lastDrag = t;
        s.x = nx;
        s.y = ny;
      }
    },
    onPointerUp: () => {
      const s = st.current;
      const p = s.press;
      s.press = null;
      s.lastDrag = 0;
      if (!p) return;
      if (p.dragging) {
        startFall(s, clamp(s.vx, -900, 900), clamp(s.vy, -900, 400)); // thả ra → rơi theo quán tính
        emit("drop");
      } else {
        poke();
      }
    },
  };
  handlers.onPointerCancel = handlers.onPointerUp;

  /* ---------------- vòng lặp ---------------- */

  useEffect(() => {
    const s0 = st.current;
    const onMove = (e) => {
      const t = now();
      s0.mouse.x = e.clientX;
      s0.mouse.y = e.clientY;
      s0.lastActivity = t;

      // Nhường đường: con trỏ đặt lên linh vật mà bên dưới là nút/link/ô nhập
      // → cho click xuyên qua ngay và tránh sang chỗ khác
      if (t - s0.lastYieldCheck < 80 || t < s0.yieldUntil || s0.press || AIRBORNE.includes(s0.mode)) return;
      s0.lastYieldCheck = t;
      const overBody =
        Math.abs(e.clientX - s0.x) < BODY_HALF_W && e.clientY < s0.y && e.clientY > s0.y - BODY_H;
      if (overBody && interactiveAt(e.clientX, e.clientY)) {
        s0.yieldUntil = t + YIELD_MS;
        s0.chaseUntil = 0;
        relocate(s0, true);
        emit("yield");
      }
    };
    const markActive = () => {
      s0.lastActivity = now();
    };
    const activityEvents = ["keydown", "wheel", "touchstart", "pointerdown"];
    window.addEventListener("pointermove", onMove, { passive: true });
    activityEvents.forEach((ev) => window.addEventListener(ev, markActive, { passive: true }));

    let raf;
    let last = now();
    const loop = (t) => {
      const dt = Math.min((t - last) / 1000, 0.05);
      last = t;
      step(t, dt);

      const s = st.current;
      const el = followerRef.current;
      if (el) {
        el.style.transform = `translate3d(${Math.round(s.x - PET_W / 2)}px, ${Math.round(
          s.y - PET_H + FOOT_PAD
        )}px, 0)`;
      }

      const mode = robotMode(s);
      const W = viewW();
      const side = s.x > W - 130 ? "right" : s.x < 130 ? "left" : "center";
      const perch = s.anchor !== null && !AIRBORNE.includes(s.mode);
      const alert = s.mode === "startled" || t < s.alertUntil;
      const behavior = behaviorOf(s, t);
      const yielding = t < s.yieldUntil;
      setView((v) =>
        v.mode === mode &&
        v.facing === s.facing &&
        v.side === side &&
        v.perch === perch &&
        v.alert === alert &&
        v.yielding === yielding &&
        v.behavior === behavior
          ? v
          : { mode, facing: s.facing, side, perch, alert, yielding, behavior }
      );
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      activityEvents.forEach((ev) => window.removeEventListener(ev, markActive));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { petRef: st, followerRef, view, handlers, callPet };
}
