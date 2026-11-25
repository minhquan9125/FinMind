import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Bot, EyeOff, MessageCircle, MousePointer2, Send, X } from "lucide-react";
import { MASCOT_GREETING, MASCOT_LINES, MASCOT_TIPS, askMascot } from "./mascotMock";
import { PET_H, PET_W, useMascotBehavior } from "./useMascotBehavior";
import { dueReminder, getGreeting, getTimelyTip, hhmm, isNight } from "./timeTalk";

// Tách chunk: three.js chỉ tải khi linh vật được render
const MascotScene = lazy(() => import("./MascotScene"));

const TIP_INTERVAL_MS = 20000; // thưa ra để không che nội dung quá thường xuyên
const TIP_VISIBLE_MS = 5000;
const REMINDER_CHECK_MS = 15000;
const REMINDER_VISIBLE_MS = 8000;

// Keyframes riêng của widget (không đụng index.css của TL)
const KEYFRAMES = `
@keyframes mascot-pop { 0% { opacity: 0; transform: translateY(6px) scale(.92); } 100% { opacity: 1; transform: none; } }
@keyframes mascot-dot { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }
@keyframes mascot-zzz { 0% { opacity: 0; transform: translate(0, 0) scale(.6); } 20% { opacity: 1; } 100% { opacity: 0; transform: translate(18px, -42px) scale(1.15); } }
@keyframes mascot-float { 0% { opacity: 0; transform: translate(0, 0) scale(.4); } 15% { opacity: 1; transform: translate(calc(var(--dx) * .2), -8px) scale(1); } 100% { opacity: 0; transform: translate(var(--dx), -64px) scale(.9) rotate(var(--rot)); } }
@keyframes mascot-puff { 0% { opacity: .55; transform: translate(0, 0) scale(.4); } 100% { opacity: 0; transform: translate(var(--dx), -6px) scale(1.5); } }
@keyframes mascot-twinkle { 0% { opacity: 0; transform: scale(0) rotate(0); } 40% { opacity: 1; transform: scale(1.1) rotate(45deg); } 100% { opacity: 0; transform: scale(.3) rotate(120deg); } }
`;

/* Hiệu ứng hạt (DOM nhẹ, tự xoá sau khi chạy xong) */
const PARTICLE_PRESETS = {
  hearts: () =>
    [0, 1, 2].map((i) => ({
      char: i === 1 ? "💖" : "💙",
      left: 50 + (i - 1) * 10,
      top: 30,
      size: 16 + (i % 2) * 4,
      style: { "--dx": `${(i - 1) * 22 + (Math.random() * 10 - 5)}px`, "--rot": `${(i - 1) * 20}deg` },
      anim: `mascot-float 1.1s ${i * 0.08}s ease-out forwards`,
    })),
  puff: () =>
    [-1, 1].flatMap((dir) =>
      [0, 1].map((k) => ({
        dot: true,
        left: 50 + dir * 8,
        top: 93,
        size: 10 + k * 5,
        style: { "--dx": `${dir * (18 + k * 12)}px` },
        anim: `mascot-puff .55s ${k * 0.05}s ease-out forwards`,
      }))
    ),
  sparkle: () =>
    [
      [22, 30],
      [78, 26],
      [70, 52],
      [28, 56],
    ].map(([left, top], i) => ({
      char: "✦",
      color: i % 2 ? "#facc15" : "#60a5fa",
      left,
      top,
      size: 14 + (i % 2) * 6,
      anim: `mascot-twinkle .8s ${i * 0.1}s ease-out forwards`,
    })),
};

function Particles({ items }) {
  return items.map((p) => (
    <span
      key={p.id}
      className="pointer-events-none absolute -translate-x-1/2"
      style={{ left: `${p.left}%`, top: `${p.top}%` }}
    >
      {p.dot ? (
        <span
          className="block rounded-full bg-slate-300"
          style={{ width: p.size, height: p.size, opacity: 0, animation: p.anim, ...p.style }}
        />
      ) : (
        <span
          className="block leading-none"
          style={{ fontSize: p.size, color: p.color, opacity: 0, animation: p.anim, ...p.style }}
        >
          {p.char}
        </span>
      )}
    </span>
  ));
}

let particleId = 0;

const pick = (list) => list[Math.floor(Math.random() * list.length)];

function usePrefersReducedMotion() {
  const [reduce, setReduce] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return undefined;
    const onChange = () => setReduce(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return reduce;
}

/* ------------------------------------------------------------------ */
/* Bong bóng thoại + Zzz                                               */
/* ------------------------------------------------------------------ */

function SpeechBubble({ text, side, onOpenChat }) {
  // Lật bong bóng khi linh vật sát mép màn hình
  const align = side === "right" ? "right-0" : side === "left" ? "left-0" : "left-1/2 -translate-x-1/2";
  const tail = side === "right" ? "right-[68px]" : side === "left" ? "left-[68px]" : "left-1/2 -translate-x-1/2";
  return (
    <div className={`pointer-events-none absolute bottom-[calc(100%-34px)] w-52 select-none ${align}`}>
      <div
        key={text}
        className="relative rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[13px] leading-snug text-slate-800 shadow-lg [animation:mascot-pop_.3s_ease-out]"
      >
        <p>{text}</p>
        <button
          type="button"
          onClick={onOpenChat}
          className="pointer-events-auto mt-1.5 inline-flex items-center gap-1 rounded-full bg-blue-600 px-2.5 py-1 text-[11px] font-medium text-white transition-colors hover:bg-blue-700"
        >
          <MessageCircle size={12} /> Hỏi mình nhé
        </button>
        <span
          className={`absolute top-full -mt-1.5 h-3 w-3 rotate-45 border-b border-r border-slate-200 bg-white ${tail}`}
        />
      </div>
    </div>
  );
}

function SleepingZzz() {
  return (
    <div className="pointer-events-none absolute left-[62%] top-[26%]">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="absolute font-bold text-blue-500"
          style={{ fontSize: 12 + i * 4, opacity: 0, animation: `mascot-zzz 2.4s ${i * 0.8}s infinite ease-out` }}
        >
          z
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Linh vật di chuyển trên trang                                        */
/* ------------------------------------------------------------------ */

function AlertMark() {
  return (
    <div className="pointer-events-none absolute left-[68%] top-[24%]">
      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-red-500 text-lg font-black text-white shadow-lg [animation:mascot-pop_.25s_ease-out]">
        !
      </span>
    </div>
  );
}

function Pet({ chatOpen, onOpenChat, callRef }) {
  const reduceMotion = usePrefersReducedMotion();
  const [bubble, setBubble] = useState(null);
  const [hovered, setHovered] = useState(false);
  const hideTimer = useRef(null);
  const tipIndex = useRef(0);
  const greeted = useRef(false);
  const modeRef = useRef("idle");

  const [particles, setParticles] = useState([]);
  const burst = useCallback((kind) => {
    const batch = PARTICLE_PRESETS[kind]().map((p) => ({ ...p, id: ++particleId }));
    const ids = new Set(batch.map((p) => p.id));
    setParticles((list) => [...list.slice(-16), ...batch]);
    setTimeout(() => setParticles((list) => list.filter((p) => !ids.has(p.id))), 1400);
  }, []);

  // important = câu nhắc theo giờ: vẫn hiện cả khi bé đang ngủ (nói mớ 😴)
  const say = useCallback((text, ms = 4500, important = false) => {
    setBubble({ text, important });
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setBubble(null), ms);
  }, []);

  // Xen kẽ: gợi ý khám phá trang ↔ câu hợp với giờ hiện tại
  const sayNextTip = useCallback(() => {
    if (Math.random() < 0.45) {
      say(getTimelyTip(), TIP_VISIBLE_MS);
      return;
    }
    tipIndex.current = (tipIndex.current + 1) % MASCOT_TIPS.length;
    say(MASCOT_TIPS[tipIndex.current], TIP_VISIBLE_MS);
  }, [say]);

  const handleEvent = useCallback(
    (type) => {
      switch (type) {
        case "land":
          if (!greeted.current) {
            greeted.current = true;
            say(getGreeting(), 6500); // chào theo buổi: sáng / trưa / chiều / tối / khuya
          }
          break;
        case "poke":
          sayNextTip();
          burst("hearts");
          break;
        case "touchdown":
          burst("puff");
          break;
        case "wake":
          say(pick(MASCOT_LINES.wake), 3500);
          break;
        case "wake-self":
          say(pick(MASCOT_LINES.wakeSelf), 3500);
          burst("sparkle");
          break;
        case "dizzy":
          say(pick(MASCOT_LINES.dizzy), 3000);
          break;
        case "drag":
          say(pick(MASCOT_LINES.drag), 2500);
          break;
        case "drop":
          say(pick(MASCOT_LINES.drop), 2500);
          break;
        case "startled":
          say(pick(MASCOT_LINES.startled), 2500);
          break;
        case "chase":
          say(pick(MASCOT_LINES.chase), 2500);
          break;
        case "chase-arrive":
          say(pick(MASCOT_LINES.arrive), 3000);
          burst("sparkle");
          break;
        case "sleep":
          setBubble((b) => (b?.important ? b : null)); // câu nhắc theo giờ thì vẫn giữ lại
          break;
        default:
      }
    },
    [say, sayNextTip, burst]
  );

  const { petRef, followerRef, view, handlers, callPet } = useMascotBehavior({
    paused: chatOpen,
    wander: !reduceMotion,
    onEvent: handleEvent,
    sleepAfterMs: isNight() ? 5000 : 8000, // ban đêm bé buồn ngủ hơn
  });
  modeRef.current = view.mode;

  useEffect(() => {
    callRef.current = callPet;
    return () => {
      callRef.current = null;
    };
  });

  // Gợi ý mỗi 8 giây (không làm phiền khi đang ngủ / bị kéo / đang chat)
  useEffect(() => {
    if (chatOpen) return undefined;
    const id = setInterval(() => {
      if (modeRef.current !== "sleep" && modeRef.current !== "drag") sayNextTip();
    }, TIP_INTERVAL_MS);
    return () => clearInterval(id);
  }, [chatOpen, sayNextTip]);

  // Nhắc theo giờ thực: giờ giao dịch, giờ ăn, khuya, nghỉ mắt...
  const firedReminders = useRef(new Set());
  const sessionStart = useRef(Date.now());
  useEffect(() => {
    if (chatOpen) return undefined;
    const check = () => {
      if (!greeted.current || modeRef.current === "drag") return;
      const text = dueReminder(firedReminders.current, sessionStart.current);
      if (text) {
        say(`🕒 ${hhmm()} · ${text}`, REMINDER_VISIBLE_MS, true);
        burst("sparkle");
      }
    };
    const first = setTimeout(check, 7500); // ngay sau lời chào
    const id = setInterval(check, REMINDER_CHECK_MS);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
  }, [chatOpen, say, burst]);

  useEffect(() => () => clearTimeout(hideTimer.current), []);

  const sleeping = view.mode === "sleep";
  const dragging = view.mode === "drag";

  return (
    <>
      {/* Canvas 3D phủ toàn màn hình, không chặn chuột */}
      <Suspense fallback={null}>
        <MascotScene
          petRef={petRef}
          mode={view.mode}
          facing={view.facing}
          hovered={hovered}
          perch={view.perch}
          alert={view.alert}
        />
      </Suspense>

      {/* Khung DOM nhỏ đi theo linh vật: vùng bấm/kéo, bong bóng, Zzz, "!" */}
      <div
        ref={followerRef}
        data-mascot-root
        data-behavior={view.behavior}
        className="pointer-events-none fixed left-0 top-0 z-50 will-change-transform"
        style={{ width: PET_W, height: PET_H, transform: "translate3d(-9999px, 0, 0)" }}
      >
        {bubble && (!sleeping || bubble.important) && !chatOpen && !view.yielding && (
          <SpeechBubble text={bubble.text} side={view.side} onOpenChat={onOpenChat} />
        )}
        {sleeping && <SleepingZzz />}
        {view.alert && <AlertMark />}
        <Particles items={particles} />

        {/* Vùng bấm/kéo trùng thân robot — phần còn lại trong suốt, không chặn click vào trang */}
      <div
        role="button"
        tabIndex={-1}
        aria-label="Linh vật Fin — bấm để chọc, kéo để nhấc lên"
        title={sleeping ? "Fin đang ngủ... chọc thử xem?" : undefined}
        className={`absolute bottom-[3%] left-[27%] right-[27%] top-[22%] touch-none ${
          view.yielding ? "pointer-events-none" : "pointer-events-auto"
        } ${dragging ? "cursor-grabbing" : "cursor-pointer"}`}
        onPointerEnter={() => setHovered(true)}
        onPointerLeave={() => setHovered(false)}
        {...handlers}
      />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Chat mini                                                           */
/* ------------------------------------------------------------------ */

let msgId = 0;
const createMsg = (from, text) => ({ id: ++msgId, from, text });

function TypingDots() {
  return (
    <span className="inline-flex gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-blue-600"
          style={{ animation: `mascot-dot 1.2s ${i * 0.15}s infinite` }}
        />
      ))}
    </span>
  );
}

function MiniChat({ onClose }) {
  const [messages, setMessages] = useState(() => [createMsg("bot", MASCOT_GREETING)]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const listRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, typing]);

  const send = async (e) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || typing) return;
    setInput("");
    setMessages((m) => [...m, createMsg("user", q)]);
    setTyping(true);
    const reply = await askMascot(q);
    setTyping(false);
    setMessages((m) => [...m, createMsg("bot", reply)]);
  };

  return (
    <div className="flex h-[380px] w-[300px] max-w-[calc(100vw-32px)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl [animation:mascot-pop_.25s_ease-out]">
      <header className="flex items-center justify-between bg-blue-600 px-4 py-2.5 text-white">
        <div className="flex items-center gap-2">
          <Bot size={18} />
          <div className="leading-tight">
            <p className="text-sm font-semibold">Fin</p>
            <p className="text-[11px] opacity-80">Trợ lý FinMind · 🕒 {hhmm()}</p>
          </div>
        </div>
        <button type="button" onClick={onClose} aria-label="Đóng chat" className="rounded-full p-1 hover:bg-white/15">
          <X size={16} />
        </button>
      </header>

      <div ref={listRef} className="flex-1 space-y-2 overflow-y-auto bg-slate-50 px-3 py-3">
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
            <p
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-[13px] leading-snug ${
                m.from === "user"
                  ? "rounded-br-sm bg-blue-600 text-white"
                  : "rounded-bl-sm bg-white text-slate-800 shadow-sm"
              }`}
            >
              {m.text}
            </p>
          </div>
        ))}
        {typing && (
          <div className="flex justify-start">
            <p className="rounded-2xl rounded-bl-sm bg-white px-3 py-2.5 shadow-sm">
              <TypingDots />
            </p>
          </div>
        )}
      </div>

      <form onSubmit={send} className="flex items-center gap-2 border-t border-slate-100 p-2">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Hỏi Fin điều gì đó..."
          className="flex-1 rounded-full border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-500"
        />
        <button
          type="submit"
          disabled={!input.trim() || typing}
          aria-label="Gửi"
          className="rounded-full bg-blue-600 p-2 text-white transition-opacity disabled:opacity-40"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Widget                                                              */
/* ------------------------------------------------------------------ */

export default function MascotWidget() {
  const [chatOpen, setChatOpen] = useState(false);
  const [petVisible, setPetVisible] = useState(true);
  const callRef = useRef(null);
  const openChat = useCallback(() => setChatOpen(true), []);

  return (
    <>
      <style>{KEYFRAMES}</style>

      {petVisible && <Pet chatOpen={chatOpen} onOpenChat={openChat} callRef={callRef} />}

      <div
        data-mascot-root
        data-mascot-dock
        data-mascot-ignore-scroll
        className="fixed bottom-4 right-4 z-[60] flex flex-col items-end gap-2"
      >
        {chatOpen && <MiniChat onClose={() => setChatOpen(false)} />}
        <div className="flex items-center gap-2">
          {petVisible && (
            <button
              type="button"
              onClick={() => callRef.current?.()}
              className="inline-flex h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 text-xs font-medium text-slate-700 shadow transition-colors hover:border-blue-300 hover:text-blue-600"
            >
              <MousePointer2 size={14} /> Gọi bé lại
            </button>
          )}
          <button
            type="button"
            onClick={() => setPetVisible((v) => !v)}
            title={petVisible ? "Cất Fin đi" : "Gọi Fin ra chơi"}
            aria-label={petVisible ? "Ẩn linh vật" : "Hiện linh vật"}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow transition-colors hover:text-blue-600"
          >
            {petVisible ? <EyeOff size={16} /> : <Bot size={16} />}
          </button>
          <button
            type="button"
            onClick={() => setChatOpen((v) => !v)}
            aria-label={chatOpen ? "Đóng chat" : "Mở chat với Fin"}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-transform hover:scale-105"
          >
            {chatOpen ? <X size={20} /> : <MessageCircle size={20} />}
          </button>
        </div>
      </div>
    </>
  );
}
