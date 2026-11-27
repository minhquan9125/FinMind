import {
  Component,
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import "./laptopHero.css";
import { rotateOrientation } from "./rotationInput.js";

const LaptopScene = lazy(() => import("./Laptop3D.tsx"));
const LAPTOP_POSTER = "/images/finmind-laptop-poster.webp?v=unsigned-workspace-20261127";

function useMedia(query) {
  const [matches, setMatches] = useState(
    () => window.matchMedia(query).matches,
  );
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    if (!context) return false;
    const device = navigator;
    const weak =
      context.getParameter(context.MAX_TEXTURE_SIZE) < 2048 ||
      (device.deviceMemory !== undefined && device.deviceMemory <= 2) ||
      (device.hardwareConcurrency !== undefined &&
        device.hardwareConcurrency <= 2) ||
      device.connection?.saveData;
    context.getExtension("WEBGL_lose_context")?.loseContext();
    return !weak;
  } catch {
    return false;
  }
}

class SceneBoundary extends Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure();
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function DashboardPoster() {
  return (
    <div className="fm-laptop-poster" aria-hidden="true">
      <img
        src={LAPTOP_POSTER}
        alt=""
        width="1518"
        height="1086"
        fetchpriority="high"
      />
    </div>
  );
}

/** DOM-owned free rotation, with explicit touch mode to preserve page scrolling. */
export default function LaptopHero({ motionPaused = false }) {
  const host = useRef(null);
  const input = useRef({
    x: 0,
    y: 0,
    scroll: 0,
    yaw: 0,
    pitch: 0,
    orientation: [0, 0, 0, 1],
    pose: [0, 0, 0, 1],
    manual: false,
    dragging: false,
    invalidate: null,
  });
  const gesture = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [touchRotation, setTouchRotation] = useState(false);
  const reducedMotion = useMedia("(prefers-reduced-motion: reduce)");
  const compact = useMedia("(max-width: 767px)");
  const [eligible, setEligible] = useState(false);
  const [visible, setVisible] = useState(false);
  const [pageVisible, setPageVisible] = useState(() => !document.hidden);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [paused, setPaused] = useState(false);
  const handleReady = useCallback(() => setReady(true), []);
  const handleFailure = useCallback(() => {
    setFailed(true);
    setReady(false);
  }, []);

  function beginManualRotation() {
    if (!input.current.manual) {
      input.current.orientation = [...input.current.pose];
      input.current.yaw = 0;
      input.current.pitch = 0;
    }
    input.current.manual = true;
  }
  function rotateBy(angle, pitch = 0) {
    beginManualRotation();
    input.current.yaw += angle;
    input.current.pitch += pitch;
    rotateOrientation(input.current.orientation, angle, pitch);
    input.current.invalidate?.();
  }
  function resetView() {
    input.current.manual = false;
    input.current.yaw = 0;
    input.current.pitch = 0;
    input.current.x = 0;
    input.current.y = 0;
    input.current.invalidate?.();
  }
  function pointerDown(event) {
    if (!ready || failed || !event.isPrimary || event.button !== 0) return;
    gesture.current = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      started: false,
    };
  }
  function pointerMove(event) {
    const current = gesture.current;
    if (!current || current.id !== event.pointerId) return;
    if (!current.started) {
      const dx = Math.abs(event.clientX - current.x),
        dy = Math.abs(event.clientY - current.y);
      if (Math.max(dx, dy) < 6) return;
      if (event.pointerType === "touch" && !touchRotation && dy > dx) {
        gesture.current = null;
        return;
      }
      beginManualRotation();
      current.started = true;
      input.current.dragging = true;
      setDragging(true);
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    const area = event.currentTarget;
    const sensitivity =
      (Math.PI * 2) /
      Math.max(320, Math.min(area.clientWidth, area.clientHeight) * 1.25);
    const yaw = (event.clientX - current.lastX) * sensitivity;
    const pitch =
      event.pointerType === "touch" && !touchRotation
        ? 0
        : (event.clientY - current.lastY) * sensitivity;
    input.current.yaw += yaw;
    input.current.pitch += pitch;
    rotateOrientation(input.current.orientation, yaw, pitch);
    current.lastX = event.clientX;
    current.lastY = event.clientY;
    input.current.invalidate?.();
  }
  function pointerEnd(event) {
    if (gesture.current?.id !== event.pointerId) return;
    gesture.current = null;
    input.current.dragging = false;
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId))
      event.currentTarget.releasePointerCapture(event.pointerId);
    input.current.invalidate?.();
  }

  useEffect(() => {
    setEligible(supportsWebGL());
  }, []);
  useEffect(() => {
    const element = host.current;
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.05 },
    );
    observer.observe(element);
    const visibility = () => setPageVisible(!document.hidden);
    const scroll = () => {
      const hero = element.closest("#research");
      const rect = hero.getBoundingClientRect();
      input.current.scroll = Math.min(
        1,
        Math.max(0, -rect.top / Math.max(1, rect.height * 0.65)),
      );
    };
    const pointer = (event) => {
      if (event.pointerType === "touch") return;
      const rect = element.getBoundingClientRect();
      input.current.x = Math.max(
        -1,
        Math.min(1, ((event.clientX - rect.left) / rect.width - 0.5) * 2),
      );
      input.current.y = Math.max(
        -1,
        Math.min(1, ((event.clientY - rect.top) / rect.height - 0.5) * 2),
      );
    };
    const resetPointer = () => {
      input.current.x = 0;
      input.current.y = 0;
    };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("resize", scroll, { passive: true });
    element.addEventListener("pointermove", pointer, { passive: true });
    element.addEventListener("pointerleave", resetPointer);
    scroll();
    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("resize", scroll);
      element.removeEventListener("pointermove", pointer);
      element.removeEventListener("pointerleave", resetPointer);
    };
  }, []);

  const canRender = eligible && !failed;
  return (
    <figure
      className="fm-laptop-showcase"
      ref={host}
      aria-label="Laptop hiển thị giao diện tổng quan FinMind với dữ liệu minh họa"
    >
      <div
        className="fm-laptop-stage"
        data-ready={ready && !failed}
        data-dragging={dragging}
        data-touch-rotation={touchRotation}
        role="group"
        tabIndex={ready && !failed ? 0 : undefined}
        aria-label="Laptop 3D. Kéo để xoay tự do 360 độ ngang và dọc. Dùng bốn phím mũi tên để xoay, Home để đặt lại. Trên điện thoại bật Xoay tự do để kéo dọc."
        onPointerDown={pointerDown}
        onPointerMove={pointerMove}
        onPointerUp={pointerEnd}
        onPointerCancel={pointerEnd}
        onLostPointerCapture={(event) => {
          // Touch starts with implicit capture on a child div. Its bubbling
          // lost-capture event must not end the drag when capture moves here.
          if (event.target === event.currentTarget) pointerEnd(event);
        }}
        onKeyDown={(event) => {
          if (!ready || failed) return;
          if (
            [
              "ArrowLeft",
              "ArrowRight",
              "ArrowUp",
              "ArrowDown",
              "Home",
            ].includes(event.key)
          ) {
            event.preventDefault();
            if (event.key === "Home") resetView();
            else if (event.key === "ArrowUp" || event.key === "ArrowDown")
              rotateBy(0, ((event.key === "ArrowUp" ? -1 : 1) * Math.PI) / 12);
            else
              rotateBy(((event.key === "ArrowRight" ? 1 : -1) * Math.PI) / 12);
          }
        }}
      >
        <div className="fm-laptop-static">
          <DashboardPoster />
        </div>
        {canRender && (
          <SceneBoundary fallback={null} onFailure={handleFailure}>
            <Suspense fallback={null}>
              <LaptopScene
                input={input}
                active={visible && pageVisible}
                reducedMotion={reducedMotion}
                compact={compact}
                paused={paused || motionPaused}
                onReady={handleReady}
                onFailure={handleFailure}
              />
            </Suspense>
          </SceneBoundary>
        )}
      </div>
      <figcaption className="fm-laptop-caption">
        <span>
          <i aria-hidden="true" />
          FinMind Workspace{" "}
        </span>
        {ready && !failed && (
          <div className="fm-laptop-controls">
            <span className="fm-laptop-drag-hint">Kéo để xoay tự do 360°</span>
            <button
              type="button"
              className="fm-laptop-touch-toggle"
              aria-pressed={touchRotation}
              onClick={() => setTouchRotation((value) => !value)}
            >
              {touchRotation ? "Xong · Cuộn trang" : "Xoay tự do"}
            </button>
            <button
              type="button"
              onClick={() => rotateBy(-Math.PI / 6)}
              aria-label="Xoay laptop sang trái"
            >
              ←
            </button>
            <button
              type="button"
              onClick={() => rotateBy(Math.PI / 6)}
              aria-label="Xoay laptop sang phải"
            >
              →
            </button>
            <button type="button" onClick={resetView}>
              Đặt lại góc
            </button>
            <button
              type="button"
              onClick={() => rotateBy(0, -Math.PI / 6)}
              aria-label="Xoay laptop lên trên"
            >
              ↑
            </button>
            <button
              type="button"
              onClick={() => rotateBy(0, Math.PI / 6)}
              aria-label="Xoay laptop xuống dưới"
            >
              ↓
            </button>
            {!reducedMotion && (
              <button
                type="button"
                onClick={() => setPaused((value) => !value)}
                disabled={motionPaused}
                aria-pressed={paused || motionPaused}
                aria-label={
                  paused
                    ? "Tiếp tục chuyển động laptop"
                    : "Tạm dừng chuyển động laptop"
                }
              >
                {motionPaused
                  ? "Đã tạm dừng"
                  : paused
                    ? "Tiếp tục"
                    : "Tạm dừng"}
                <span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span>
              </button>
            )}
          </div>
        )}
      </figcaption>
    </figure>
  );
}
