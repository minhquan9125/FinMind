// Scene 3D toàn màn hình của linh vật.
// - <Canvas> phủ kín viewport (fixed inset-0, pointer-events none) với camera trực giao zoom = 1
//   → 1 đơn vị Three.js = 1px CSS. Đổi toạ độ trình duyệt → 3D: X = x − W/2, Y = H/2 − y.
// - Vị trí do useMascotBehavior quyết định (petRef), scene chỉ đọc và vẽ mỗi frame.
// Chỉ được nạp qua React.lazy trong MascotWidget.
// (Next.js: thêm "use client" ở dòng đầu và import bằng dynamic(..., { ssr: false }).)
import React, { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, RoundedBox, useAnimations, useGLTF } from "@react-three/drei";
import * as THREE from "three";

const MODEL_URL = "/mascot.glb";
const PX_PER_UNIT = 57; // kích thước robot trên màn hình (robot cao ~2.3 đơn vị ≈ 130px)
const MAX_YAW = 0.6; // giới hạn xoay ngang của đầu (rad)
const MAX_PITCH = 0.35; // giới hạn cúi/ngẩng (rad)
const TARGET_HEIGHT = 2.2; // chiều cao chuẩn hoá cho model .glb
const FEET_Y = -1.02; // cao độ bàn chân trong hệ toạ độ của model

const COLORS = {
  body: "#f4f7f5",
  brand: "#2563eb",
  screen: "#0f172a",
  eye: "#67e8f9",
  cheek: "#fda4af",
  brow: "#f87171",
};

// Tên clip trong file .glb ứng với từng trạng thái (tìm theo "chứa chuỗi", không phân biệt hoa thường)
const CLIP_ALIASES = {
  idle: ["idle"],
  land: ["idle"],
  happy: ["happy", "cheer", "wave"],
  walk: ["walk"],
  run: ["run", "walk"],
  jump: ["jump", "fall"],
  startled: ["jump", "surprise"],
  drag: ["fall", "fly", "jump"],
  sit: ["sit"],
  sleep: ["sleep", "lie", "sit"],
  dizzy: ["dizzy", "stun", "hit"],
  wave: ["wave", "hello", "greet"],
};

const { lerp, clamp, damp } = THREE.MathUtils;
const smoothing = (delta, speed = 8) => 1 - Math.exp(-speed * delta); // lerp alpha không phụ thuộc FPS

/* ------------------------------------------------------------------ */
/* Hooks                                                               */
/* ------------------------------------------------------------------ */

/** Kiểm tra /mascot.glb có tồn tại không (Vite trả index.html 200 khi file thiếu). */
function useModelAvailable(url) {
  const [state, setState] = useState("checking");
  useEffect(() => {
    let alive = true;
    fetch(url, { method: "HEAD" })
      .then((res) => {
        const type = res.headers.get("content-type") || "";
        if (alive) setState(res.ok && !type.includes("text/html") ? "glb" : "fallback");
      })
      .catch(() => alive && setState("fallback"));
    return () => {
      alive = false;
    };
  }, [url]);
  return state;
}

/** Vận tốc cuộn (px/ms). Bắt mọi vùng cuộn: window lẫn container bên trong layout. */
function useScrollVelocity() {
  const velocity = useRef(0);
  useEffect(() => {
    const last = new WeakMap();
    const onScroll = (e) => {
      const el = e.target === document ? document.scrollingElement : e.target;
      if (!el || typeof el.scrollTop !== "number") return;
      if (el.closest?.("[data-mascot-ignore-scroll]")) return; // bỏ qua khung chat
      const now = performance.now();
      const prev = last.get(el) ?? { top: el.scrollTop, t: now };
      const v = (el.scrollTop - prev.top) / Math.max(now - prev.t, 16);
      last.set(el, { top: el.scrollTop, t: now });
      velocity.current = clamp(velocity.current + v * 0.6, -3, 3);
    };
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", onScroll, { capture: true });
  }, []);
  return velocity;
}

/** Hướng nhìn [-1, 1] từ đầu linh vật tới con trỏ (dùng chung cho robot & .glb). */
function lookTarget(pet, out) {
  const head = pet.y - 95; // đầu cao hơn bàn chân ~95px
  out.x = clamp((pet.mouse.x - pet.x) / (window.innerWidth / 2), -1, 1);
  out.y = clamp((pet.mouse.y - head) / (window.innerHeight / 2), -1, 1);
  return out;
}

/* ------------------------------------------------------------------ */
/* Đặt linh vật đúng toạ độ màn hình                                    */
/* ------------------------------------------------------------------ */

function PetPositioner({ petRef, children }) {
  const group = useRef();
  const { size } = useThree();
  useFrame(() => {
    const p = petRef.current;
    if (!group.current || !p) return;
    // Bàn chân (FEET_Y * scale) phải nằm đúng (x, y) của trình duyệt
    group.current.position.set(p.x - size.width / 2, size.height / 2 - p.y - FEET_Y * PX_PER_UNIT, 0);
  });
  return (
    <group ref={group}>
      <group scale={PX_PER_UNIT}>{children}</group>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Rig chung: hover, quay mặt theo hướng đi, nghiêng theo cuộn         */
/* ------------------------------------------------------------------ */

function MascotRig({ mode, facing, hovered, scrollVel, children }) {
  const root = useRef();
  const squash = useRef(1);
  const hoverScale = useRef(1);

  useFrame((state, delta) => {
    const g = root.current;
    if (!g) return;
    const t = state.clock.elapsedTime;

    scrollVel.current = damp(scrollVel.current, 0, 3, delta);
    const v = scrollVel.current;

    // Hover phóng 1.05x · squash & stretch: bay lên thì dãn, tiếp đất thì bẹp · luôn thở nhẹ
    const hoverS = damp(hoverScale.current, hovered ? 1.05 : 1, 10, delta);
    hoverScale.current = hoverS;
    const sqTarget = mode === "land" ? 0.86 : mode === "jump" || mode === "startled" ? 1.08 : 1;
    squash.current = damp(squash.current, sqTarget, 16, delta);
    const sq = squash.current;
    const widen = 1 / Math.sqrt(sq); // giữ "thể tích": dẹt thì bè ra, dãn thì thon lại
    g.scale.set(hoverS * widen, hoverS * sq * (1 + Math.sin(t * 2) * 0.012), hoverS * widen);

    // Lơ lửng nhẹ khi đứng yên + nảy theo cuộn
    const floatY = mode === "idle" ? Math.sin(t * 1.6) * 0.03 : 0;
    g.position.y = damp(g.position.y, floatY - v * 0.08, 12, delta);

    // Quay người theo hướng di chuyển (vẫn hé mặt ra phía người xem)
    g.rotation.y = damp(g.rotation.y, facing * 0.9, 8, delta);

    // Nghiêng theo cuộn trang + đổ người về trước khi đi/chạy
    const lean = mode === "run" ? -facing * 0.14 : mode === "walk" ? -facing * 0.06 : 0;
    g.rotation.z = damp(g.rotation.z, clamp(-v * 0.12, -0.35, 0.35) + lean, 6, delta);
    g.rotation.x = damp(g.rotation.x, clamp(v * 0.08, -0.2, 0.2), 6, delta);
  });

  return <group ref={root}>{children}</group>;
}

/* ------------------------------------------------------------------ */
/* Bóng đổ mềm dưới chân                                               */
/* ------------------------------------------------------------------ */

function useRadialTexture() {
  const [texture] = useState(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(15,23,42,1)");
    g.addColorStop(0.5, "rgba(15,23,42,0.5)");
    g.addColorStop(1, "rgba(15,23,42,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    return new THREE.CanvasTexture(c);
  });
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

function BlobShadow({ mode, perch }) {
  const mesh = useRef();
  const mat = useRef();
  const texture = useRadialTexture();

  useFrame((_, delta) => {
    const airborne = mode === "jump" || mode === "startled" || mode === "drag";
    const hidden = airborne || (perch && (mode === "sit" || mode === "sleep")); // ngồi vắt vẻo: chân thả qua mép
    const target = hidden ? 0 : 0.22;
    mat.current.opacity = damp(mat.current.opacity, target, 10, delta);
    const k = damp(mesh.current.scale.x, airborne ? 0.6 : mode === "land" ? 1.15 : 1, 10, delta);
    mesh.current.scale.set(k, k * 0.22, 1);
  });

  return (
    <mesh ref={mesh} position={[0, FEET_Y + 0.02, -0.8]}>
      <circleGeometry args={[0.6, 32]} />
      <meshBasicMaterial ref={mat} map={texture} transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}

/* ------------------------------------------------------------------ */
/* Robot dự phòng dựng bằng hình khối                                  */
/* ------------------------------------------------------------------ */

function BodyMaterial({ color = COLORS.body }) {
  return <meshStandardMaterial color={color} roughness={0.35} metalness={0.1} />;
}

function GlowMaterial({ color, intensity = 1.4, materialRef }) {
  return (
    <meshStandardMaterial
      ref={materialRef}
      color={color}
      emissive={color}
      emissiveIntensity={intensity}
      toneMapped={false}
    />
  );
}

/** Góc tay [phải, trái] (rotation.z) theo trạng thái. */
function armTargets(mode, t) {
  switch (mode) {
    case "wave":
      return [2.6 + Math.sin(t * 14) * 0.35, -0.15];
    case "happy":
      return [2.1 + Math.sin(t * 10) * 0.2, -2.1 - Math.sin(t * 10) * 0.2];
    case "jump":
      return [2.3, -2.3];
    case "startled":
      return [2.8, -2.8];
    case "drag":
      return [2.7 + Math.sin(t * 8) * 0.2, -2.7 - Math.sin(t * 8) * 0.2]; // vùng vẫy
    case "sit":
    case "sleep":
      return [0.3, -0.3]; // tay đặt lên đùi
    case "dizzy":
      return [0.7 + Math.sin(t * 6) * 0.3, -0.7 - Math.sin(t * 6 + 1) * 0.3];
    case "walk":
    case "run":
      return [0.2, -0.2];
    default: {
      const swing = Math.sin(t * 1.6) * 0.05;
      return [0.12 + swing, -0.12 - swing];
    }
  }
}

/** Góc chân [trái, phải] (rotation.x) theo trạng thái. perch = đang ngồi trên mép card. */
function legTargets(mode, t, perch) {
  switch (mode) {
    case "walk":
      return [Math.sin(t * 9) * 0.55, -Math.sin(t * 9) * 0.55];
    case "run":
      return [Math.sin(t * 16) * 0.9, -Math.sin(t * 16) * 0.9];
    case "sit": // vắt vẻo: đung đưa chân thả xuống mép card / trên sàn thì duỗi ra trước
      return perch
        ? [-0.25 + Math.sin(t * 2.4) * 0.3, -0.25 - Math.sin(t * 2.4) * 0.3]
        : [-1.35, -1.35];
    case "sleep":
      return perch ? [-0.12, -0.12] : [-1.35, -1.35];
    case "drag":
      return [Math.sin(t * 6) * 0.45, -Math.sin(t * 6 + 1) * 0.45];
    case "jump":
    case "startled":
      return [-0.35, 0.2];
    default:
      return [0, 0];
  }
}

function RobotFallback({ mode, perch, alert, hovered, petRef }) {
  const root = useRef();
  const head = useRef();
  const eyes = useRef();
  const brows = useRef();
  const smile = useRef();
  const mouthO = useRef();
  const frown = useRef();
  const cheeks = useRef();
  const cheekMats = useRef([]);
  const leftArm = useRef();
  const rightArm = useRef();
  const leftLeg = useRef();
  const rightLeg = useRef();
  const body = useRef();
  const antennaMat = useRef();
  const blink = useRef({ next: 1.5, start: -10 });
  const look = useRef({ x: 0, y: 0 });

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    const a = smoothing(delta);
    const sleeping = mode === "sleep";
    const seated = sleeping || mode === "sit";

    // 1. Đầu nhìn theo chuột (ngủ thì gục, chóng mặt thì lắc lư)
    const target = lookTarget(petRef.current, look.current);
    const yaw = sleeping ? 0 : target.x * MAX_YAW;
    const pitch = sleeping ? 0.38 + Math.sin(t * 1.2) * 0.06 : target.y * MAX_PITCH;
    const roll = mode === "dizzy" ? Math.sin(t * 10) * 0.25 : sleeping ? 0.15 : 0;
    head.current.rotation.y = lerp(head.current.rotation.y, yaw, a);
    head.current.rotation.x = lerp(head.current.rotation.x, pitch, a);
    head.current.rotation.z = lerp(head.current.rotation.z, roll, a);

    // 2. Mắt + lông mày quạu
    const b = blink.current;
    if (t > b.next) {
      b.start = t;
      b.next = t + 2 + Math.random() * 3;
    }
    const p = (t - b.start) / 0.16;
    let eyeY = p >= 0 && p < 1 ? 1 - Math.sin(p * Math.PI) * 0.9 : 1;
    let eyeX = 1;
    if (sleeping) eyeY = 0.12;
    else if (mode === "startled" || mode === "drag") {
      eyeY = 1.35;
      eyeX = 1.15;
    } else if (alert) eyeY = 0.6;
    else if (mode === "dizzy") eyeY = 0.35 + Math.abs(Math.sin(t * 8)) * 0.5;
    else if (mode === "wave" || mode === "land" || mode === "happy") eyeY *= 0.5;
    eyes.current.scale.y = lerp(eyes.current.scale.y, eyeY, 0.5);
    eyes.current.scale.x = lerp(eyes.current.scale.x, eyeX, 0.3);
    const browK = lerp(brows.current.scale.x, alert ? 1 : 0.001, 0.3);
    brows.current.scale.setScalar(browK);
    brows.current.visible = browK > 0.02;

    // Miệng: "O" khi hoảng / bị nhấc / chóng mặt · mếu khi quạu · còn lại cười
    const surprised = mode === "startled" || mode === "drag" || mode === "dizzy";
    const grumpy = alert && !surprised;
    mouthO.current.visible = surprised;
    frown.current.visible = grumpy;
    smile.current.visible = !surprised && !grumpy;
    const smileK = mode === "happy" || mode === "wave" || hovered ? 1.35 : sleeping ? 0.6 : 1;
    smile.current.scale.setScalar(lerp(smile.current.scale.x, smileK, a));
    mouthO.current.scale.setScalar(1 + Math.sin(t * 12) * (mode === "drag" ? 0.15 : 0.05));

    // Má ửng hồng khi được rê chuột / đang vui
    const blush = hovered || mode === "happy" || mode === "wave" ? 1 : 0;
    const cheekK = lerp(cheeks.current.scale.x, 1 + blush * 0.35, a);
    cheeks.current.scale.setScalar(cheekK);
    cheekMats.current.forEach((m) => {
      if (m) m.opacity = lerp(m.opacity, 0.55 + blush * 0.4, a);
    });

    // 3. Tay
    const [rT, lT] = armTargets(mode, t);
    const armSpeed = ["wave", "drag", "startled", "happy"].includes(mode) ? 0.3 : a;
    rightArm.current.rotation.z = lerp(rightArm.current.rotation.z, rT, armSpeed);
    leftArm.current.rotation.z = lerp(leftArm.current.rotation.z, lT, armSpeed);
    const armSwing = mode === "walk" ? Math.sin(t * 9) * 0.6 : mode === "run" ? Math.sin(t * 16) * 1.0 : 0;
    rightArm.current.rotation.x = lerp(rightArm.current.rotation.x, armSwing, a);
    leftArm.current.rotation.x = lerp(leftArm.current.rotation.x, -armSwing, a);

    // 4. Chân
    const [lL, rL] = legTargets(mode, t, perch);
    leftLeg.current.rotation.x = lerp(leftLeg.current.rotation.x, lL, smoothing(delta, 12));
    rightLeg.current.rotation.x = lerp(rightLeg.current.rotation.x, rL, smoothing(delta, 12));

    // 5. Cả người: ngồi xuống (trên mép card thì mông chạm mép, chân thả xuống), nhún khi đi/chạy
    let bodyY = 0;
    if (seated) bodyY = perch ? -0.345 : -0.25;
    else if (mode === "walk") bodyY = Math.abs(Math.sin(t * 9)) * 0.05;
    else if (mode === "run") bodyY = Math.abs(Math.sin(t * 16)) * 0.09;
    root.current.position.y = lerp(root.current.position.y, bodyY, smoothing(delta, 10));

    // 6. Thở + ăng-ten (ngủ thì mờ, phấn khích thì nháy nhanh)
    body.current.scale.y = 1 + Math.sin(t * (sleeping ? 1.2 : 2)) * (sleeping ? 0.035 : 0.02);
    if (antennaMat.current) {
      antennaMat.current.emissiveIntensity = sleeping
        ? 0.25
        : 1.5 + Math.sin(t * (["idle", "walk", "sit"].includes(mode) ? 3 : 10)) * 0.8;
    }
  });

  return (
    <group position={[0, -0.15, 0]}>
      <group ref={root}>
        {/* Thân */}
        <RoundedBox ref={body} args={[0.95, 0.85, 0.7]} radius={0.22} smoothness={4} position={[0, -0.1, 0]}>
          <BodyMaterial />
        </RoundedBox>
        <mesh position={[0, -0.05, 0.351]}>
          <circleGeometry args={[0.12, 32]} />
          <GlowMaterial color={COLORS.brand} intensity={0.6} />
        </mesh>

        {/* Tay (pivot ở vai) */}
        <group ref={leftArm} position={[-0.56, 0.18, 0]}>
          <mesh position={[0, -0.25, 0]}>
            <capsuleGeometry args={[0.1, 0.3, 6, 12]} />
            <BodyMaterial />
          </mesh>
        </group>
        <group ref={rightArm} position={[0.56, 0.18, 0]}>
          <mesh position={[0, -0.25, 0]}>
            <capsuleGeometry args={[0.1, 0.3, 6, 12]} />
            <BodyMaterial />
          </mesh>
        </group>

        {/* Chân (pivot ở hông) */}
        <group ref={leftLeg} position={[-0.22, -0.5, 0]}>
          <mesh position={[0, -0.18, 0]}>
            <capsuleGeometry args={[0.12, 0.15, 6, 12]} />
            <BodyMaterial color={COLORS.brand} />
          </mesh>
        </group>
        <group ref={rightLeg} position={[0.22, -0.5, 0]}>
          <mesh position={[0, -0.18, 0]}>
            <capsuleGeometry args={[0.12, 0.15, 6, 12]} />
            <BodyMaterial color={COLORS.brand} />
          </mesh>
        </group>

        {/* Đầu */}
        <group ref={head} position={[0, 0.72, 0]}>
          <RoundedBox args={[1.15, 0.85, 0.85]} radius={0.28} smoothness={5}>
            <BodyMaterial />
          </RoundedBox>
          {/* Màn hình mặt */}
          <RoundedBox args={[0.9, 0.55, 0.06]} radius={0.025} smoothness={4} position={[0, 0, 0.41]}>
            <meshStandardMaterial color={COLORS.screen} roughness={0.2} metalness={0.4} />
          </RoundedBox>
          {/* Mắt */}
          <group ref={eyes} position={[0, 0.04, 0.45]}>
            {[-0.2, 0.2].map((x) => (
              <group key={x} position={[x, 0, 0]}>
                <mesh>
                  <capsuleGeometry args={[0.065, 0.08, 4, 12]} />
                  <GlowMaterial color={COLORS.eye} />
                </mesh>
                {/* Đốm sáng cho mắt long lanh */}
                <mesh position={[0.025, 0.045, 0.062]}>
                  <sphereGeometry args={[0.022, 12, 12]} />
                  <meshBasicMaterial color="#ffffff" toneMapped={false} />
                </mesh>
              </group>
            ))}
          </group>
          {/* Lông mày quạu (chỉ hiện khi STARTLED) */}
          <group ref={brows} position={[0, 0.19, 0.45]} visible={false}>
            {[
              [-0.2, -0.45],
              [0.2, 0.45],
            ].map(([x, rz]) => (
              <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, rz]}>
                <boxGeometry args={[0.18, 0.035, 0.02]} />
                <GlowMaterial color={COLORS.brow} intensity={1.2} />
              </mesh>
            ))}
          </group>
          {/* Má hồng */}
          <group ref={cheeks} position={[0, -0.14, 0.445]}>
            {[-0.32, 0.32].map((x, i) => (
              <mesh key={x} position={[x, 0, 0]}>
                <circleGeometry args={[0.05, 24]} />
                <meshBasicMaterial
                  ref={(m) => {
                    cheekMats.current[i] = m;
                  }}
                  color={COLORS.cheek}
                  transparent
                  opacity={0.55}
                />
              </mesh>
            ))}
          </group>
          {/* Miệng: cười / chữ O / mếu */}
          <group position={[0, -0.12, 0.445]}>
            <mesh ref={smile} rotation={[0, 0, Math.PI]}>
              <torusGeometry args={[0.06, 0.014, 8, 20, Math.PI]} />
              <GlowMaterial color={COLORS.eye} intensity={1} />
            </mesh>
            <mesh ref={mouthO} visible={false}>
              <torusGeometry args={[0.04, 0.015, 8, 20]} />
              <GlowMaterial color={COLORS.eye} intensity={1} />
            </mesh>
            <mesh ref={frown} position={[0, -0.05, 0]} visible={false}>
              <torusGeometry args={[0.055, 0.014, 8, 20, Math.PI]} />
              <GlowMaterial color={COLORS.brow} intensity={1} />
            </mesh>
          </group>
          {/* Tai */}
          {[-0.6, 0.6].map((x) => (
            <mesh key={x} position={[x, 0, 0]} rotation={[0, 0, Math.PI / 2]}>
              <cylinderGeometry args={[0.13, 0.13, 0.08, 24]} />
              <BodyMaterial color={COLORS.brand} />
            </mesh>
          ))}
          {/* Ăng-ten */}
          <mesh position={[0, 0.52, 0]}>
            <cylinderGeometry args={[0.02, 0.02, 0.2, 8]} />
            <BodyMaterial color={COLORS.brand} />
          </mesh>
          <mesh position={[0, 0.66, 0]}>
            <sphereGeometry args={[0.07, 20, 20]} />
            <GlowMaterial color={COLORS.eye} materialRef={antennaMat} />
          </mesh>
        </group>
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Model .glb (Tripo / Meshy / Mixamo)                                 */
/* ------------------------------------------------------------------ */

function GlbMascot({ mode, petRef }) {
  const mixerRoot = useRef();
  const turnRoot = useRef(); // dùng khi model không có xương đầu
  const { scene, animations } = useGLTF(MODEL_URL);
  const head = useRef(null);
  const applied = useRef({ x: 0, y: 0 });
  const look = useRef({ x: 0, y: 0 });

  // Chuẩn hoá kích thước + tìm xương/nhóm đầu
  useLayoutEffect(() => {
    const box = new THREE.Box3().setFromObject(scene);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const k = TARGET_HEIGHT / (size.y || 1);
    scene.scale.setScalar(k);
    scene.position.set(-center.x * k, -box.min.y * k + FEET_Y, -center.z * k);

    let found = null;
    scene.traverse((o) => {
      if (!found && /head/i.test(o.name)) found = o; // "Head", "mixamorigHead", ...
    });
    head.current = found;
  }, [scene]);

  const target = () => head.current ?? turnRoot.current;

  // (A) Chạy TRƯỚC mixer: gỡ phần xoay đã cộng ở frame trước
  useFrame(() => {
    const h = target();
    if (!h) return;
    h.rotation.x -= applied.current.x;
    h.rotation.y -= applied.current.y;
  });

  const { actions, names } = useAnimations(animations, mixerRoot); // mixer cập nhật giữa (A) và (B)

  // (B) Chạy SAU mixer: cộng góc nhìn theo chuột lên pose hiện tại
  useFrame((_, delta) => {
    const h = target();
    if (!h) return;
    const a = smoothing(delta);
    const k = mode === "sleep" ? 0 : 1;
    const lt = lookTarget(petRef.current, look.current);
    applied.current.x = lerp(applied.current.x, lt.y * MAX_PITCH * k, a);
    applied.current.y = lerp(applied.current.y, lt.x * MAX_YAW * k, a);
    h.rotation.x += applied.current.x;
    h.rotation.y += applied.current.y;
  });

  // Chuyển clip theo trạng thái
  useEffect(() => {
    const find = (key) => names.find((n) => n.toLowerCase().includes(key));
    const keys = [...(CLIP_ALIASES[mode] ?? []), "idle"];
    const name = keys.map(find).find(Boolean) ?? names[0];
    const action = name && actions[name];
    if (!action) return undefined;
    action.reset().fadeIn(0.25).play();
    return () => {
      action.fadeOut(0.25);
    };
  }, [mode, actions, names]);

  return (
    <group ref={mixerRoot}>
      <group ref={turnRoot}>
        <primitive object={scene} />
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ */
/* Phụ trợ                                                             */
/* ------------------------------------------------------------------ */

class SafeBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error) {
    console.warn("[Mascot]", error);
  }
  render() {
    return this.state.failed ? this.props.fallback ?? null : this.props.children;
  }
}

function MascotModel(props) {
  const source = useModelAvailable(MODEL_URL);
  if (source === "checking") return null;
  if (source === "fallback") return <RobotFallback {...props} />;
  return (
    <SafeBoundary fallback={<RobotFallback {...props} />}>
      <Suspense fallback={<RobotFallback {...props} />}>
        <GlbMascot {...props} />
      </Suspense>
    </SafeBoundary>
  );
}

/* ------------------------------------------------------------------ */
/* Scene                                                               */
/* ------------------------------------------------------------------ */

const CANVAS_STYLE = { position: "fixed", inset: 0, zIndex: 50, pointerEvents: "none" };

export default function MascotScene({ petRef, mode = "idle", facing = 0, hovered = false, perch = false, alert = false }) {
  const scrollVel = useScrollVelocity();

  return (
    <Canvas
      orthographic
      dpr={[1, 2]}
      camera={{ zoom: 1, position: [0, 0, 1000], near: 1, far: 3000 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      className="fixed inset-0 z-50 pointer-events-none"
      style={CANVAS_STYLE}
    >
      <ambientLight intensity={0.6} />
      <directionalLight position={[300, 400, 500]} intensity={1.1} />

      {/* HDR tải từ CDN — lỗi/mất mạng thì bỏ qua, model vẫn hiển thị */}
      <SafeBoundary>
        <Suspense fallback={null}>
          <Environment preset="city" />
        </Suspense>
      </SafeBoundary>

      <PetPositioner petRef={petRef}>
        <BlobShadow mode={mode} perch={perch} />
        <MascotRig mode={mode} facing={facing} hovered={hovered} scrollVel={scrollVel}>
          <MascotModel mode={mode} perch={perch} alert={alert} hovered={hovered} petRef={petRef} />
        </MascotRig>
      </PetPositioner>
    </Canvas>
  );
}
