import {
  Suspense,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  type MutableRefObject,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  Environment,
  Lightformer,
  useGLTF,
  useTexture,
} from "@react-three/drei";
import {
  Box3,
  Euler,
  Group,
  Mesh,
  PerspectiveCamera,
  Quaternion,
  Sphere,
  Vector3,
} from "three";
import { createMacBook } from "./macbookModel";

export interface LaptopInput {
  x: number;
  y: number;
  scroll: number;
  yaw: number;
  pitch: number;
  manual: boolean;
  dragging: boolean;
  orientation: [number, number, number, number];
  pose: [number, number, number, number];
  invalidate: (() => void) | null;
}
export interface Laptop3DProps {
  input: MutableRefObject<LaptopInput>;
  active: boolean;
  reducedMotion: boolean;
  paused: boolean;
  compact: boolean;
  onReady: () => void;
  onFailure: () => void;
}

const MODEL_URL = "/models/laptop.glb?v=macbook-pro-m3-629720";
const TEXTURE_URL = "/images/finmind-dashboard.webp?v=unsigned-workspace-20261127";
const CENTER_Y = 0.65;
const MODEL_SCALE = 0.15;

function MacBook({
  input,
  reducedMotion,
  paused,
  onReady,
  onFailure,
}: Laptop3DProps) {
  const { scene: source } = useGLTF(MODEL_URL, "/draco/");
  const sourceTexture = useTexture(TEXTURE_URL);
  const { gl, invalidate, camera, size } = useThree();
  const model = useMemo(
    () => createMacBook(source, sourceTexture, gl),
    [source, sourceTexture, gl],
  );
  const bounds = useMemo(() => {
    // Split batches retain unused attribute vertices. Bounds must use referenced
    // indices, otherwise an oversized box makes mobile framing unnecessarily tiny.
    model.scene.updateMatrixWorld(true);
    const box = new Box3(),
      point = new Vector3();
    model.scene.traverse((node) => {
      if (!(node instanceof Mesh)) return;
      const position = node.geometry.getAttribute("position");
      const indices = node.geometry.index
        ? new Set<number>(node.geometry.index.array)
        : Array.from({ length: position.count }, (_, index) => index);
      for (const index of indices)
        box.expandByPoint(
          point
            .fromBufferAttribute(position, index)
            .applyMatrix4(node.matrixWorld),
        );
    });
    const sphere = box.getBoundingSphere(new Sphere());
    return { center: sphere.center, radius: sphere.radius * MODEL_SCALE };
  }, [model]);
  const target = useMemo(() => new Quaternion(), []);
  const automatic = useMemo(() => new Euler(), []);
  const rig = useRef<Group>(null);
  const elapsed = useRef(0);
  const frameSample = useRef({
    elapsed: 0,
    frames: 0,
    slowWindows: 0,
    degraded: false,
  });
  const setDpr = useThree((state) => state.setDpr);

  useEffect(() => () => model.dispose(), [model]);
  useLayoutEffect(() => {
    if (!(camera instanceof PerspectiveCamera)) return;
    // Fit the complete rotation envelope, rather than only the open front pose.
    // The pivot is the model center: flipping no longer swings it off screen.
    const vertical = (camera.fov * Math.PI) / 360;
    const horizontal = Math.atan(
      (Math.tan(vertical) * size.width) / Math.max(1, size.height),
    );
    const distance =
      (bounds.radius / Math.sin(Math.min(vertical, horizontal))) * 1.12;
    const center = new Vector3(0, CENTER_Y, 0);
    camera.position.copy(
      new Vector3(0, 0.22, 1).normalize().multiplyScalar(distance).add(center),
    );
    camera.lookAt(center);
    camera.updateProjectionMatrix();
    invalidate();
  }, [bounds, camera, invalidate, size.width, size.height]);
  useLayoutEffect(() => {
    input.current.invalidate = invalidate;
    invalidate();
    onReady();
    return () => {
      input.current.invalidate = null;
    };
  }, [input, invalidate, onReady]);
  useFrame((_, delta) => {
    if (!rig.current) return;
    if (reducedMotion) {
      model.hinge.rotation.x = 0;
      rig.current.position.set(0, CENTER_Y, 0);
      if (input.current.manual)
        rig.current.quaternion.fromArray(input.current.orientation);
      else rig.current.quaternion.identity();
      rig.current.quaternion.toArray(input.current.pose);
      return;
    }
    if (paused) {
      if (input.current.manual)
        rig.current.quaternion.fromArray(input.current.orientation);
      else
        rig.current.quaternion.setFromEuler(
          automatic.set(0, -0.25 * (1 - input.current.scroll), -0.012),
        );
      rig.current.quaternion.toArray(input.current.pose);
      return;
    }
    const dt = Math.min(delta, 0.05);
    elapsed.current += dt;
    const progress = Math.min(1, elapsed.current / 1.8);
    // Transform-only power-out easing, without transparent mesh crossfades or
    // a second animation ticker competing with the R3F frame loop.
    const ease = 1 - (1 - progress) ** 3;
    model.hinge.rotation.x = 1.92 * (1 - ease);
    rig.current.position.y =
      CENTER_Y - (1 - ease) * 0.15 + Math.sin(elapsed.current * 0.65) * 0.025;
    const { x, y, scroll } = input.current;
    if (input.current.manual) target.fromArray(input.current.orientation);
    else
      target.setFromEuler(
        automatic.set(
          y * 0.018 * (1 - scroll),
          -0.25 * (1 - scroll) + x * 0.04,
          -0.012 * (1 - scroll),
        ),
      );
    rig.current.quaternion.slerp(
      target,
      1 - Math.exp(-dt * (input.current.dragging ? 20 : 10)),
    );
    rig.current.quaternion.toArray(input.current.pose);

    // Ignore shader compilation/entrance. Lower DPR first, then fall back to
    // the poster only after repeated slow windows at the lower quality.
    if (elapsed.current > 4 && delta < 0.5) {
      const sample = frameSample.current;
      sample.elapsed += delta;
      sample.frames++;
      if (sample.elapsed >= 2) {
        const fps = sample.frames / sample.elapsed;
        if (!sample.degraded && fps < 45) {
          sample.degraded = true;
          setDpr(1);
        } else if (sample.degraded) {
          sample.slowWindows = fps < 22 ? sample.slowWindows + 1 : 0;
          if (sample.slowWindows >= 2) onFailure();
        }
        sample.elapsed = 0;
        sample.frames = 0;
      }
    }
  });
  return (
    <>
      <group
        ref={rig}
        name="FinMindRotationPivot"
        position={[0, CENTER_Y - 0.15, 0]}
        rotation={[0, -0.25, -0.012]}
        scale={MODEL_SCALE}
      >
        <group
          position={[-bounds.center.x, -bounds.center.y, -bounds.center.z]}
        >
          <primitive object={model.scene} dispose={null} />
        </group>
      </group>
    </>
  );
}

export default function Laptop3D(props: Laptop3DProps) {
  const { active, reducedMotion, paused, compact, onFailure } = props;
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const canvas = host.current?.querySelector("canvas");
    if (!canvas) return;
    const lost = (event: Event) => {
      event.preventDefault();
      onFailure();
    };
    canvas.addEventListener("webglcontextlost", lost);
    return () => canvas.removeEventListener("webglcontextlost", lost);
  }, [onFailure]);
  return (
    <div className="fm-laptop-canvas" ref={host} aria-hidden="true">
      <Canvas
        frameloop={active && !reducedMotion && !paused ? "always" : "demand"}
        dpr={[1, compact ? 1.25 : 1.5]}
        camera={{ position: [0, 2.8, 9.5], fov: 38, near: 0.1, far: 40 }}
        gl={{
          alpha: true,
          antialias: !compact,
          powerPreference: compact ? "low-power" : "high-performance",
        }}
        onCreated={({ gl, scene }) => {
          gl.setClearColor(0x000000, 0);
          scene.background = null;
        }}
        fallback={null}
      >
        <ambientLight intensity={0.45} />
        <directionalLight
          position={[-3, 5, 5]}
          intensity={1.5}
          color="#fff9f2"
        />
        <Suspense fallback={null}>
          <Environment resolution={256} frames={1}>
            <Lightformer
              form="rect"
              intensity={4}
              position={[-4, 3, 2]}
              rotation={[0, Math.PI / 3, 0]}
              scale={[4, 6, 1]}
            />
            <Lightformer
              form="rect"
              intensity={3}
              position={[5, 2, -2]}
              rotation={[0, -Math.PI / 2, 0]}
              scale={[3, 6, 1]}
            />
            <Lightformer
              form="rect"
              intensity={2}
              position={[0, 6, 1]}
              rotation={[Math.PI / 2, 0, 0]}
              scale={[7, 4, 1]}
            />
          </Environment>
          <MacBook {...props} />
        </Suspense>
      </Canvas>
    </div>
  );
}
