import {
  BufferGeometry, Group, Material, Mesh, MeshBasicMaterial, MeshStandardMaterial,
  Object3D, SRGBColorSpace, Texture, WebGLRenderer,
} from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/** Contract verified against the 16-inch jackbaeten GLB linked in models/README.md. */
const DISPLAY = "Object_123";
const HINGE = [0, 0.6, -12.75] as const;
const LID_BOUNDARY_Y = 1.12;
type Batch = { lid: boolean; material: Material; parts: BufferGeometry[]; names: string[] };

export function createMacBook(source: Object3D, sourceTexture: Texture, renderer: WebGLRenderer) {
  const scene = new Group();
  scene.name = "FinMindMacBook";
  const hinge = new Group();
  hinge.name = "FinMindHinge";
  hinge.position.set(...HINGE);
  scene.add(hinge);
  const texture = sourceTexture.clone();
  texture.colorSpace = SRGBColorSpace;
  texture.flipY = true;
  texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  texture.needsUpdate = true;
  const materials = new Map<string, Material>();
  const geometries: BufferGeometry[] = [];
  const batches = new Map<string, Batch>();
  let sourceTriangles = 0;
  let displayFound = false;
  source.updateMatrixWorld(true);

  source.traverse(node => {
    if (!(node instanceof Mesh)) return;
    if (Array.isArray(node.material)) throw new Error("Unexpected MacBook multi-material primitive");
    const isDisplay = node.name === DISPLAY;
    displayFound ||= isDisplay;
    // Palette 001/003 have identical opaque PBR maps and attributes. Palette
    // 002 uses the same atlas with BLEND alpha, so preserve it separately.
    const materialKey = isDisplay ? "finmind-display"
      : /^PaletteMaterial00[13]$/.test(node.material.name) ? "shared-opaque-palette" : node.material.uuid;
    let material = materials.get(materialKey);
    if (!material) {
      material = isDisplay ? new MeshBasicMaterial({ map: texture, toneMapped: false }) : (node.material as Material).clone();
      material.name = isDisplay ? "FinMindDashboard" : node.material.name;
      if (material instanceof MeshStandardMaterial) material.envMapIntensity = 1.1;
      materials.set(materialKey, material);
    }
    // Bake each original transform once. Split only indices; retain every
    // triangle, normal, tangent and UV, including the display's camera notch.
    const geometry = (node.geometry as BufferGeometry).clone().applyMatrix4(node.matrixWorld);
    const position = geometry.getAttribute("position");
    const index = geometry.index;
    const count = index ? index.count : position.count;
    const base: number[] = [], lid: number[] = [];
    sourceTriangles += count / 3;
    for (let i = 0; i < count; i += 3) {
      const a = index ? index.getX(i) : i;
      const b = index ? index.getX(i + 1) : i + 1;
      const c = index ? index.getX(i + 2) : i + 2;
      const y = (position.getY(a) + position.getY(b) + position.getY(c)) / 3;
      (isDisplay || y > LID_BOUNDARY_Y ? lid : base).push(a, b, c);
    }
    for (const [isLid, indices] of [[false, base], [true, lid]] as const) {
      if (!indices.length) continue;
      const part = new BufferGeometry();
      for (const [name, attribute] of Object.entries(geometry.attributes)) {
        part.setAttribute(name, isLid && base.length ? attribute.clone() : attribute);
      }
      part.setIndex(indices);
      const key = `${isLid}:${materialKey}`;
      const batch: Batch = batches.get(key) || { lid: isLid, material, parts: [], names: [] };
      batch.parts.push(part);
      batch.names.push(node.name);
      batches.set(key, batch);
    }
  });
  if (!displayFound) throw new Error("MacBook display Object_123 is missing");

  let renderTriangles = 0;
  for (const batch of batches.values()) {
    const geometry = batch.parts.length > 1 ? mergeGeometries(batch.parts, false) : batch.parts[0];
    if (!geometry) throw new Error("MacBook batch attributes do not match");
    if (batch.parts.length > 1) batch.parts.forEach(part => part.dispose());
    if (batch.lid) geometry.translate(-HINGE[0], -HINGE[1], -HINGE[2]);
    geometry.computeBoundingSphere();
    const mesh = new Mesh(geometry, batch.material);
    mesh.name = batch.names.includes(DISPLAY) ? "FinMindDisplay" : batch.names.join("+");
    (batch.lid ? hinge : scene).add(mesh);
    geometries.push(geometry);
    renderTriangles += (geometry.index?.count || 0) / 3;
  }
  if (sourceTriangles !== renderTriangles) throw new Error("MacBook triangle count changed during batching");
  scene.userData.modelStats = { sourceTriangles, renderTriangles, drawCalls: batches.size };
  return {
    scene, hinge, texture, materials: [...materials.values()],
    dispose() {
      texture.dispose();
      materials.forEach(material => material.dispose());
      geometries.forEach(geometry => geometry.dispose());
    },
  };
}
