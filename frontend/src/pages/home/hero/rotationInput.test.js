import test from "node:test";
import assert from "node:assert/strict";
import { rotateOrientation } from "./rotationInput.js";

test("either axis can complete a full turn and return to the same orientation", () => {
  for (const axis of ["yaw", "pitch"]) {
    const q = [0, 0, 0, 1];
    for (let step = 0; step < 24; step++)
      rotateOrientation(
        q,
        axis === "yaw" ? Math.PI / 12 : 0,
        axis === "pitch" ? Math.PI / 12 : 0,
      );
    assert.ok(Math.hypot(q[0], q[1], q[2]) < 1e-12);
    assert.ok(Math.abs(Math.abs(q[3]) - 1) < 1e-12);
  }
});

test("mixed free rotation stays normalized after long use and works past a pole", () => {
  const q = [0, 0, 0, 1];
  rotateOrientation(q, 0, Math.PI / 2);
  const atPole = [...q];
  rotateOrientation(q, Math.PI / 3, 0);
  assert.notDeepEqual(q, atPole);
  for (let step = 0; step < 10000; step++)
    rotateOrientation(q, Math.sin(step) * 0.03, Math.cos(step) * 0.04);
  assert.ok(q.every(Number.isFinite));
  assert.ok(Math.abs(Math.hypot(...q) - 1) < 1e-12);
});
