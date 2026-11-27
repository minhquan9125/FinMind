/** Compose screen-space turns without Euler pole limits or a Three.js import. */
export function rotateOrientation(orientation, yaw, pitch) {
  const sy = Math.sin(yaw / 2),
    cy = Math.cos(yaw / 2);
  const sx = Math.sin(pitch / 2),
    cx = Math.cos(pitch / 2);
  const ax = cy * sx,
    ay = sy * cx,
    az = -sy * sx,
    aw = cy * cx;
  const [bx, by, bz, bw] = orientation;
  const x = aw * bx + ax * bw + ay * bz - az * by;
  const y = aw * by - ax * bz + ay * bw + az * bx;
  const z = aw * bz + ax * by - ay * bx + az * bw;
  const w = aw * bw - ax * bx - ay * by - az * bz;
  const length = Math.hypot(x, y, z, w);
  orientation[0] = x / length;
  orientation[1] = y / length;
  orientation[2] = z / length;
  orientation[3] = w / length;
}
