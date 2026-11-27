import { useEffect, useRef } from 'react';

/** One paint per pointer frame; no idle render loop or React mousemove state. */
export default function LandingPointerGlow({ paused }) {
  const glow = useRef(null);
  useEffect(() => {
    const element = glow.current;
    const media = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
    let frame = 0;
    let x = 0;
    let y = 0;
    const hide = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      element.dataset.visible = 'false';
    };
    const move = (event) => {
      if (paused || !media.matches || event.pointerType === 'touch') return;
      x = event.clientX;
      y = event.clientY;
      if (!frame) frame = requestAnimationFrame(() => {
        element.style.transform = `translate3d(${x}px, ${y}px, 0)`;
        element.dataset.visible = 'true';
        frame = 0;
      });
    };
    const root = element.parentElement;
    root.addEventListener('pointermove', move, { passive: true });
    root.addEventListener('pointerleave', hide);
    media.addEventListener('change', hide);
    document.addEventListener('visibilitychange', hide);
    window.addEventListener('blur', hide);
    return () => {
      hide();
      root.removeEventListener('pointermove', move);
      root.removeEventListener('pointerleave', hide);
      media.removeEventListener('change', hide);
      document.removeEventListener('visibilitychange', hide);
      window.removeEventListener('blur', hide);
    };
  }, [paused]);
  return <div ref={glow} className="finmind-pointer-glow" aria-hidden="true" />;
}
