// Buildings, Thronefall-simple: warm orange timber, darker plank roofs, cream stone, a few dark windows that glow at
// night. Every kind has its own silhouette you can read from far away (a windmill is the farm, a big vat is the
// brewery, a striped tent or a long hall is the tavern), and the gold put into it shows: the same kind gets bigger
// and grander tier by tier. Running buildings smoke and glow; idle ones sit dark, and neglected ones sag.
// Every person's house is one of a few hundred instanced boxes (housesMesh): a hut, a cottage, a house with a
// garden, a townhouse - by the gold they've put into it.
import * as THREE from "three";
import { C, M, box, mesh } from "./materials.js";
import { rng, hash } from "./noise.js";
import { V } from "./terrain.js";

export const WIN_LIT = new THREE.MeshStandardMaterial({ color: 0x23305a, emissive: C.windowLit, emissiveIntensity: 0, roughness: 0.4, flatShading: true });
export const FLAME = new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xff7a1a, emissiveIntensity: 2.2, transparent: true, opacity: 0.9 });

const WOOD = C.plank, WOOD2 = C.plankDark, ROOF = C.thatch, STONE = C.stone, DOOR = 0x5a2e18, CANVAS = 0xf3e6c8;

// a triangular prism (a roof): width along x, slope along z, apex up
export function prism(w, d, h) {
  const x = w / 2, z = d / 2;
  const p = [[-x, 0, -z], [x, 0, -z], [x, 0, z], [-x, 0, z], [-x, h, 0], [x, h, 0]];
  const tri = [[0, 4, 1], [1, 4, 5], [3, 2, 5], [3, 5, 4], [0, 3, 4], [1, 5, 2], [0, 1, 2], [0, 2, 3]];
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(tri.flatMap((t) => t.flatMap((i) => p[i])), 3));
  g.computeVertexNormals();
  return g;
}
const pyramid = (w, h) => new THREE.ConeGeometry(w * 0.72, h, 4).rotateY(Math.PI / 4).translate(0, h / 2, 0);
const cyl = (r, h, n = 8) => new THREE.CylinderGeometry(r, r, h, n).translate(0, h / 2, 0);
const at = (o, x, y, z, ry = 0) => { o.position.set(x, y, z); o.rotation.y = ry; return o; };
const part = (geo, color) => mesh(geo, M(color));

// the house shape most things are made of: walls, a roof, a door at the front (+z), a dark window or two
function house(g, { w, d, h, x = 0, z = 0, roof = ROOF, wall = WOOD, door = true, wins = 1, chimney = null, out, ry = 0 }) {
  const o = new THREE.Group();
  o.add(at(part(box(w, h, d), wall), 0, h / 2, 0));
  o.add(at(part(prism(w + 0.4, d + 0.5, Math.min(d * 0.6, 3)), roof), 0, h, 0));
  if (door) o.add(at(part(box(0.8, 1.4, 0.08), DOOR), 0, 0.7, d / 2 + 0.03));
  for (let k = 0; k < wins; k++) {
    const wx = (k - (wins - 1) / 2) * (w / (wins + 0.5)) + (wins === 1 ? w * 0.28 : 0);
    o.add(at(new THREE.Mesh(box(0.6, 0.6, 0.08), WIN_LIT), wx, Math.min(h - 0.8, 1.6), d / 2 + 0.03));
  }
  if (chimney && out) {
    o.add(at(part(box(0.55, 1.5, 0.55), STONE), w * 0.3, h + 0.9, -d * 0.18));
    if (chimney === "smoke" && out.smoke) { const t = new THREE.Object3D(); t.position.set(w * 0.3, h + 1.8, -d * 0.18); o.add(t); out.smoke.push(t); }
  }
  at(o, x, 0, z, ry);
  g.add(o);
  return o;
}
function flag(g, x, y, z, out, color = C.banner) {
  g.add(at(part(cyl(0.06, 3, 5), WOOD2), x, y, z));
  const cloth = at(part(box(1.1, 0.65, 0.05), color), x + 0.58, y + 2.6, z); g.add(cloth);
  if (out.flags) out.flags.push(cloth);
}
function barrel(g, x, z, s = 1) { g.add(at(part(cyl(0.45 * s, 1.0 * s, 8), WOOD2), x, 0, z)); }
function fence(g, w, d, color = WOOD2) {      // a low post-and-rail fence round w x d
  for (const [sx, sz, len, rot] of [[0, -d / 2, w, 0], [0, d / 2, w, 0], [-w / 2, 0, d, Math.PI / 2], [w / 2, 0, d, Math.PI / 2]]) {
    const r = at(part(box(len, 0.12, 0.12), color), sx, 0.7, sz); r.rotation.y = rot; g.add(r);
    for (let k = 0; k <= Math.round(len / 2); k++) {
      const f = -len / 2 + k * len / Math.round(len / 2);
      g.add(at(part(box(0.18, 0.9, 0.18), color), sx + (rot ? 0 : f), 0.45, sz + (rot ? f : 0)));
    }
  }
}
function field(g, w, d, x = 0, z = 0, color = C.crop) {   // plank-yellow crop beds, like Thronefall's fields
  const rows = Math.max(3, Math.round(d / 1.3));
  for (let k = 0; k < rows; k++) g.add(at(part(box(w, 0.28, d / rows * 0.72), k % 2 ? color : 0xd9ad55), x, 0.14, z - d / 2 + (k + 0.5) * d / rows));
}
function fire(g, out, x, z) { const f = new THREE.Object3D(); f.position.set(x, 0, z); g.add(f); out.fires.push({ obj: f, small: true }); }

const SHAPES = {
  keep: (g, t, b, out) => {
    if (t === 0) { house(g, { w: 4.6, d: 3.8, h: 2.3, roof: 0x8a4a28, chimney: "smoke", out }); if (!b.noPit) fire(g, out, 3.6, 2.6); return; }
    if (t === 1) { house(g, { w: 8, d: 5, h: 3.2, roof: C.slate, wins: 3, chimney: "smoke", out }); flag(g, -3.2, 3.2, 0, out); return; }
    const s = t === 2 ? 1 : 1.25;
    g.add(at(part(box(5 * s, 7.5 * s, 5 * s), STONE), 0, 3.75 * s, 0));
    for (let k = 0; k < 8; k++) { const a = k / 8 * Math.PI * 2; g.add(at(part(box(0.9, 0.9, 0.9), STONE), Math.cos(a) * 2.2 * s, 7.9 * s, Math.sin(a) * 2.2 * s)); }
    g.add(at(part(box(1.2, 2, 0.1), DOOR), 0, 1, 2.5 * s + 0.05));
    g.add(at(new THREE.Mesh(box(0.7, 0.9, 0.1), WIN_LIT), 0, 5 * s, 2.5 * s + 0.05));
    flag(g, 0, 7.5 * s, 0, out);
    if (t === 3) for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      g.add(at(part(cyl(1.3, 8.5, 8), STONE), sx * 4.6, 0, sz * 4.6));
      g.add(at(part(new THREE.ConeGeometry(1.6, 2.4, 8).translate(0, 1.2, 0), C.slate), sx * 4.6, 8.5, sz * 4.6));
    }
    else fence(g, 8.6, 8.6, WOOD);
  },
  farm: (g, t, b, out) => {
    if (t === 0) { field(g, 7, 7); fence(g, 8, 8); return; }
    field(g, 8.4, 4.6, 0, 1.8); house(g, { w: 3.6, d: 2.6, h: 2.2, x: -2, z: -2.6, roof: 0x9a3f22, wins: 0 });
    if (t >= 2) {                                    // a windmill
      g.add(at(part(cyl(1.1, 5.5, 8), CANVAS), 2.6, 0, -2.6));
      g.add(at(part(new THREE.ConeGeometry(1.3, 1.4, 8).translate(0, 0.7, 0), ROOF), 2.6, 5.5, -2.6));
      const sails = new THREE.Group();
      for (let k = 0; k < 4; k++) { const s = at(part(box(0.4, 2.6, 0.06), WOOD2), 0, 1.3, 0); const hold = new THREE.Group(); hold.add(s); hold.rotation.z = k * Math.PI / 2; sails.add(hold); }
      sails.position.set(2.6, 4.6, -1.4); g.add(sails); if (b.running) out.spin.push(sails);
    }
  },
  well: (g, t) => {
    g.add(at(part(cyl(1.0, 1.0, 10), STONE), 0, 0, 0));
    for (const s of [-1, 1]) g.add(at(part(box(0.14, 2, 0.14), WOOD2), s * 0.85, 1, 0));
    g.add(at(part(prism(t ? 2.8 : 2.2, t ? 2.6 : 2, t ? 1.1 : 0.7), ROOF), 0, 2, 0));
  },
  brewery: (g, t, b, out) => {
    house(g, { w: t ? 5.5 : 3.6, d: t ? 4 : 3, h: t ? 3 : 2.2, x: -1.4, roof: ROOF, chimney: "smoke", out, wins: t ? 2 : 0 });
    g.add(at(part(cyl(t ? 1.6 : 1.1, t ? 2.6 : 1.8, 10), 0xc8883e), 2.6, 0, 1.2));      // the vat
    barrel(g, 2.4, -2.4); barrel(g, 3.4, -1.8, 0.9); if (t) barrel(g, 1.4, -3.0);
  },
  tavern: (g, t, b, out) => {
    if (t === 0) {                                   // a striped tent and barrels
      for (let k = 0; k < 4; k++) g.add(at(part(prism(1.2, 5, 2.6), k % 2 ? 0xd14a3a : CANVAS), -1.8 + k * 1.2, 0, 0));
      barrel(g, 3, 2); barrel(g, 3.4, 0.9, 0.85); barrel(g, -3.3, 2.2);
      for (const z of [3.2, -3.2]) g.add(at(part(box(3.4, 0.5, 0.6), WOOD2), 0, 0.25, z));
      fire(g, out, 0, 3.6); return;
    }
    const big = t >= 2;
    house(g, { w: big ? 8.2 : 6, d: big ? 6 : 4.4, h: big ? 4.2 : 3, roof: 0x9a3f22, wins: big ? 4 : 2, chimney: "smoke", out });
    g.add(at(part(box(1.0, 0.7, 0.08), 0xf2c24e), (big ? 4.1 : 3) + 0.2, 2.2, (big ? 3 : 2.2) + 0.3));   // the sign
    barrel(g, -3.6, 3.2); barrel(g, -2.8, 3.6, 0.85);
  },
  bakery: (g, t, b, out) => {
    if (t) house(g, { w: 5, d: 4, h: 2.8, x: -1.2, roof: ROOF, chimney: "smoke", out, wins: 2 });
    g.add(at(part(new THREE.SphereGeometry(1.3, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2), C.clay), t ? 2.8 : 0, 0, t ? 1.8 : 0));
    if (!t) { g.add(at(part(box(3.6, 0.15, 2.6), WOOD2), 0, 2.4, -1.6)); for (const sx of [-1.7, 1.7]) g.add(at(part(box(0.15, 2.4, 0.15), WOOD2), sx, 1.2, -2.8)); }
    if (out.smoke) { const s = new THREE.Object3D(); s.position.set(t ? 2.8 : 0, 1.8, t ? 1.8 : 0); g.add(s); out.smoke.push(s); }
  },
  smithy: (g, t, b, out) => {
    if (t) house(g, { w: 5.5, d: 4.2, h: 2.8, roof: 0x6a5a5a, wall: STONE, chimney: "smoke", out, wins: 1 });
    else {
      for (const [sx, sz] of [[-2, -1.6], [2, -1.6], [-2, 1.6], [2, 1.6]]) g.add(at(part(box(0.2, 2.4, 0.2), WOOD2), sx, 1.2, sz));
      g.add(at(part(prism(4.8, 4, 1.2), ROOF), 0, 2.4, 0));
      g.add(at(part(box(0.8, 2.6, 0.8), STONE), -1.4, 1.3, -1.2));
      if (out.smoke) { const s = new THREE.Object3D(); s.position.set(-1.4, 2.8, -1.2); g.add(s); out.smoke.push(s); }
    }
    g.add(at(part(box(0.9, 0.7, 0.45), 0x45495c), 1.4, 0.35, t ? 3 : 0.6));   // the anvil
    if (b.running) fire(g, out, t ? -1.6 : -1.4, t ? 3 : 0);
  },
  tower: (g, t) => {                                 // on stilts, like Thronefall's watchtowers
    const h = t ? 6.5 : 4;
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      const leg = at(part(box(0.25, h, 0.25), WOOD2), sx * 1.2, h / 2, sz * 1.2); leg.rotation.set(sz * 0.06, 0, -sx * 0.06); g.add(leg);
    }
    g.add(at(part(box(3.2, 0.3, 3.2), WOOD), 0, h, 0));
    if (t) { g.add(at(part(box(2.6, 1.2, 2.6), WOOD), 0, h + 0.75, 0)); g.add(at(part(pyramid(3.4, 1.8), ROOF), 0, h + 1.35, 0)); }
    else for (const s of [-1, 1]) g.add(at(part(box(3.2, 0.6, 0.12), WOOD), 0, h + 0.45, s * 1.55));
  },
  chapel: (g, t, b, out) => {
    if (!t) {
      for (const [sx, sz] of [[-0.9, -0.9], [0.9, -0.9], [-0.9, 0.9], [0.9, 0.9]]) g.add(at(part(box(0.15, 2, 0.15), WOOD2), sx, 1, sz));
      g.add(at(part(prism(2.4, 2.4, 1.0), ROOF), 0, 2, 0)); g.add(at(part(box(0.9, 0.8, 0.6), STONE), 0, 0.4, 0));
      if (b.running) fire(g, out, 0, 0.6); return;
    }
    house(g, { w: 4.4, d: 7, h: 3.6, wall: 0xf4ead6, roof: C.slate, wins: 0, ry: Math.PI / 2 });
    g.add(at(part(box(1.8, 6.5, 1.8), 0xf4ead6), 0, 3.25, 3.6)); g.add(at(part(pyramid(2.4, 2.6), C.slate), 0, 6.5, 3.6));
  },
  stage: (g, t) => {
    if (!t) { g.add(at(part(cyl(1.3, 0.9, 9), 0x7a4a2a), 0, 0, 0)); for (let k = 0; k < 5; k++) { const a = k / 5 * 6.28; g.add(at(part(box(1.2, 0.4, 0.5), WOOD2), Math.cos(a) * 3, 0.2, Math.sin(a) * 3, -a)); } return; }
    g.add(at(part(cyl(3.2, 0.7, 10), WOOD), 0, 0, 0));
    for (let k = 0; k < 6; k++) { const a = k / 6 * 6.28; g.add(at(part(box(0.18, 3, 0.18), WOOD2), Math.cos(a) * 2.9, 2.2, Math.sin(a) * 2.9)); }
    g.add(at(part(new THREE.ConeGeometry(3.7, 1.8, 10).translate(0, 0.9, 0), 0xd14a3a), 0, 3.7, 0));
  },
  market: (g, t) => {
    if (t) {
      for (let k = 0; k < 8; k++) { const a = k / 8 * 6.28; g.add(at(part(box(0.3, 3.2, 0.3), STONE), Math.cos(a) * 3.8, 1.6, Math.sin(a) * 3.8)); }
      g.add(at(part(pyramid(10, 2.4), ROOF), 0, 3.2, 0));
    }
    const stall = (x, z, col) => { g.add(at(part(box(1.8, 0.9, 1.1), WOOD), x, 0.45, z)); g.add(at(part(prism(2.2, 1.6, 0.7), col), x, 1.9, z));
      for (const sx of [-0.85, 0.85]) g.add(at(part(box(0.1, 1.9, 0.1), WOOD2), x + sx, 0.95, z + 0.55)); };
    stall(-2.4, -1.8, 0xd14a3a); stall(0.4, -2.4, 0x3f6fc4); stall(2.6, 0.6, 0xf2c24e); if (t) stall(-1.6, 1.8, 0x5fb046);
  },
  vineyard: (g, t) => {
    const rows = t ? 6 : 4;
    for (let r = 0; r < rows; r++) for (let k = 0; k < 5; k++) {
      const x = -3.2 + k * 1.6, z = -3.2 + r * (6.4 / (rows - 1));
      g.add(at(part(box(0.12, 1.3, 0.12), WOOD2), x, 0.65, z));
      g.add(at(part(new THREE.IcosahedronGeometry(0.55, 0), 0x4f9a40), x, 1.2, z));
      if (t) g.add(at(part(new THREE.IcosahedronGeometry(0.18, 0), 0x6a2a6a), x + 0.3, 0.9, z));
    }
  },
  cellar: (g, t) => {                                // dug into a grassy bank
    const s = t ? 1.4 : 1;
    g.add(at(part(new THREE.SphereGeometry(3.4 * s, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2).scale(1, 0.55, 1), C.grassDry), 0, 0, -0.5));
    g.add(at(part(box(1.6, 1.8, 1.2), STONE), 0, 0.9, 3 * s - 0.6));
    g.add(at(part(box(0.9, 1.4, 0.1), DOOR), 0, 0.7, 3 * s));
    barrel(g, 1.6, 3 * s); if (t) house(g, { w: 3.4, d: 3, h: 2.4, x: -3.2, z: 2.4, roof: ROOF, wins: 1 });
  },
  barracks: (g, t, b, out) => {
    house(g, { w: t ? 8.5 : 7, d: 3.8, h: t ? 3.4 : 2.6, z: -2, roof: t ? C.slate : ROOF, wins: 3, chimney: "smoke", out });
    for (let k = 0; k < 3; k++) g.add(at(part(box(0.25, 1.6, 0.25), WOOD2), -2.5 + k * 2.5, 0.8, 2.6));    // training posts
    flag(g, 3.8, 0, 2.6, out);
    if (t) fence(g, 8.8, 8.8, STONE);
  },
  school: (g, t, b, out) => {
    house(g, { w: t ? 6.5 : 5, d: 4.2, h: t ? 3.6 : 2.8, roof: ROOF, wins: 2, chimney: "smoke", out });
    g.add(at(part(box(0.9, 1.4, 0.9), WOOD), 0, (t ? 3.6 : 2.8) + 1.6, 0)); g.add(at(part(pyramid(1.3, 1), ROOF), 0, (t ? 3.6 : 2.8) + 2.3, 0));
    if (t) { g.add(at(part(cyl(1.4, 5, 10), STONE), 3.6, 0, -1)); g.add(at(part(new THREE.ConeGeometry(1.7, 1.8, 10).translate(0, 0.9, 0), C.slate), 3.6, 5, -1)); }
  },
  baths: (g, t, b, out) => {
    g.add(at(part(box(8, 0.8, 6), STONE), 0, 0.4, 0));
    g.add(at(new THREE.Mesh(box(6.6, 0.1, 4.6), M(C.water, null, { emissive: 0x1a5070, emissiveIntensity: 0.4 })), 0, 0.82, 0));
    for (let k = 0; k < (t ? 6 : 4); k++) g.add(at(part(box(0.35, 2.8, 0.35), t ? STONE : WOOD2), -3.6 + k * (7.2 / ((t ? 6 : 4) - 1)), 1.4, -3));
    g.add(at(part(prism(8.6, 2.6, 1.2), ROOF), 0, 2.8, -3));
    if (out.smoke) for (const x of [-1.5, 1.5]) { const s = new THREE.Object3D(); s.position.set(x, 1, 0); g.add(s); out.smoke.push(s); }
  },
};

// while it's going up: a footing, walls rising with progress, poles round it (the roof goes on at the end)
function scaffold(g, b) {
  const p = Math.max(0.04, b.progress || 0), w = 6, d = 5;
  if (b.shape === "farm" || b.shape === "vineyard") { field(g, Math.max(0.6, 7 * p), 7, 0, 0, C.soil); fence(g, 8, 8); return; }
  g.add(at(part(box(w + 0.6, 0.3, d + 0.6), STONE), 0, 0.15, 0));
  const h = 3 * Math.min(1, p * 1.15);
  if (h > 0.2) g.add(at(part(box(w, h, d), WOOD), 0, h / 2, 0));
  for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(at(part(box(0.15, 3.8, 0.15), WOOD2), sx * (w / 2 + 0.3), 1.9, sz * (d / 2 + 0.3)));
  for (const y of [1.6, 3.4]) for (const s of [-1, 1]) g.add(at(part(box(w + 0.8, 0.12, 0.12), WOOD2), 0, y, s * (d / 2 + 0.3)));
  if (p > 0.85) g.add(at(part(prism(w + 0.4, d + 0.5, 2.6 * (p - 0.85) / 0.15), ROOF), 0, h, 0));
}

function ring(g, b, land) {                          // the palisade: sharpened logs round the town
  const r = b.radius || 40, n = Math.round(r * 2 * Math.PI / 0.9);
  const show = b.state === "scaffold" ? Math.round(n * (b.progress || 0)) : n;
  const stone = (b.tier || 0) >= 1;
  const im = new THREE.InstancedMesh(stone ? box(1.6, 3.4, 1.0) : new THREE.CylinderGeometry(0.4, 0.45, 3.4, 5), M(stone ? STONE : WOOD), Math.max(1, show));
  const o = new THREE.Object3D(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
  for (let i = 0; i < show; i++) {
    const a = i / n * Math.PI * 2, x = b.pos[0] + Math.cos(a) * r, z = b.pos[1] + Math.sin(a) * r;
    if (Math.abs(a - 4.71) < 0.06) { im.setMatrixAt(i, zero); continue; }   // the gate, where the road comes in
    o.position.copy(V(x, z, land.height(x, z) + 1.4)); o.rotation.set(0, -a, 0); o.updateMatrix(); im.setMatrixAt(i, o.matrix);
  }
  im.count = show; im.castShadow = true; g.add(im);
}

export function buildingMesh(b, land, ctx) {
  const out = { smoke: ctx.smoke || [], fires: ctx.fires || [], flags: ctx.flags || [], spin: ctx.spin || [] };
  const g = new THREE.Group();
  if (b.shape === "wall") { ring(g, b, land); return tipped(g, b); }
  const inner = new THREE.Group(); g.add(inner);
  if (b.state === "scaffold" && !b.upgrade_of) scaffold(inner, b);
  else (SHAPES[b.shape] || SHAPES.well)(inner, Math.min(b.tier || 0, 3), b, b.running || b.shape === "keep" ? out : { ...out, smoke: [] });
  if (b.state === "scaffold" && b.upgrade_of)                         // being done up: scaffolding poles round it
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) inner.add(at(part(box(0.15, 5, 0.15), WOOD2), sx * 4.2, 2.5, sz * 4.2));
  const [x, z] = b.pos;
  const hs = [land.height(x, z), land.height(x - 4, z - 4), land.height(x + 4, z - 4), land.height(x - 4, z + 4), land.height(x + 4, z + 4)];
  const y = Math.max(...hs), drop = y - Math.min(...hs);
  g.position.copy(V(x, z, y));
  if (drop > 0.5) g.add(at(part(box(7, drop + 0.4, 7), C.dirt), 0, -drop / 2, 0));
  inner.rotation.y = (b.rot || 0) * Math.PI / 180;
  if (b.disrepair) { inner.rotation.z = 0.05; inner.traverse((o) => { if (o.isMesh && o.material !== WIN_LIT) o.material = M(new THREE.Color(o.material.color).multiplyScalar(0.7).getHex()); }); }
  return tipped(g, b);
}

function tipped(g, b) {
  const job = b.job ? `${b.job}${b.needs_crew === 1 ? "" : "s"}` : "people";
  const tip = `<strong>${esc(b.name)}</strong>` + (b.state === "scaffold"
    ? `<br>${b.upgrade_of ? "being done up" : "being built"}: ${Math.round((b.progress || 0) * 100)}% of ${b.need} days of work` + (b.builders ? ` · ${b.builders} building today` : " · nobody on it today")
    : b.needs_crew ? `<br>${b.running ? `running today: ${b.crew} ${job} (needs ${b.needs_crew})` : `idle today: needs ${b.needs_crew} ${job} a day`}` + (b.disrepair ? "<br>falling into disrepair" : "") : "")
    + (b.look ? `<br><span class="muted">${esc(b.look)}</span>` : "");
  g.traverse((o) => { o.userData.tip = tip; o.userData.building = b; });
  return g;
}

// the streets: flat dirt strips laid over the ground (crisper than painting the low-poly terrain)
export function streetsMesh(streets, land, width = 2.6) {
  const P = [], I = [], w = width / 2;
  for (const [a, b] of streets) {
    const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, n = Math.max(1, Math.ceil(L / 2));
    const nx = -(b[1] - a[1]) / L * w, nz = (b[0] - a[0]) / L * w, base = P.length / 3;
    for (let k = 0; k <= n; k++) {
      const f = k / n, x = a[0] + (b[0] - a[0]) * f, z = a[1] + (b[1] - a[1]) * f;
      for (const s of [-1, 1]) { const px = x + nx * s, pz = z + nz * s; P.push(px, land.height(px, pz) + 0.06, -pz); }
      if (k) { const q = base + (k - 1) * 2; I.push(q, q + 1, q + 2, q + 1, q + 3, q + 2); }
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(P, 3)); g.setIndex(I); g.computeVertexNormals();
  const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: C.dirt, roughness: 1, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2 }));
  m.receiveShadow = true;
  return m;
}

export function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// everyone's house, instanced: [x, z, rot, tier, size, handle, t]
const HOUSE_TIER = ["a hut", "a cottage", "a house with a garden", "a fine townhouse"];
export function housesMesh(houses, land) {
  const g = new THREE.Group(), n = houses.length;
  if (!n) return g;
  const flat = (c) => new THREE.MeshStandardMaterial({ color: c ?? 0xffffff, roughness: 1, flatShading: true });
  const mk = (geo, mat) => { const m = new THREE.InstancedMesh(geo, mat, n); m.castShadow = true; m.receiveShadow = true; m.count = 0; g.add(m); return m; };
  const walls = mk(new THREE.BoxGeometry(1, 1, 1).translate(0, 0.5, 0), flat());
  const roofs = mk(prism(1.12, 1.15, 0.62), flat());
  const doors = mk(new THREE.BoxGeometry(0.22, 0.42, 0.04).translate(0, 0.21, 0.5), flat(DOOR));
  const wins = mk(new THREE.BoxGeometry(0.2, 0.2, 0.04).translate(0.28, 0.55, 0.5), WIN_LIT);
  const chims = mk(new THREE.BoxGeometry(0.16, 0.5, 0.16).translate(-0.25, 1.25, -0.15), flat(STONE));
  const gardens = mk(new THREE.BoxGeometry(1, 0.18, 0.55).translate(0, 0.09, 0.95), flat(0x4f9a40));
  const o = new THREE.Object3D(), col = new THREE.Color(), cnt = { w: 0, c: 0, g: 0 };
  const WALLS = [0xf0b878, 0xe9a866, 0xf5c690, 0xe5a060, 0xf2bd80], ROOFS = [0xcf6a30, 0xd8783a, 0xc25e2a, 0xdc8445, 0xc96f35];
  houses.forEach(([x, z, rot, tier, size, h]) => {
    const s = size * (0.78 + 0.08 * tier), H = tier >= 3 ? 1.25 : 0.72 + 0.06 * tier, R = rng(hash(h));
    o.position.copy(V(x, z, land.height(x, z) - 0.05)); o.rotation.set(0, rot * Math.PI / 180 + (R() - 0.5) * 0.08, 0);
    o.scale.set(s, s * H, s); o.updateMatrix();
    walls.setMatrixAt(cnt.w, o.matrix); walls.setColorAt(cnt.w, col.setHex(WALLS[hash(h) % WALLS.length]));
    doors.setMatrixAt(cnt.w, o.matrix); wins.setMatrixAt(cnt.w, o.matrix);
    if (tier >= 1) chims.setMatrixAt(cnt.c++, o.matrix);
    o.position.y += s * H; o.scale.set(s, s, s); o.updateMatrix();
    roofs.setMatrixAt(cnt.w, o.matrix); roofs.setColorAt(cnt.w, col.setHex(tier >= 3 ? C.slate : ROOFS[(hash(h) >>> 3) % ROOFS.length]));
    o.position.y -= s * H; o.updateMatrix();
    if (tier >= 2) gardens.setMatrixAt(cnt.g++, o.matrix);
    cnt.w++;
  });
  walls.count = roofs.count = doors.count = wins.count = cnt.w; chims.count = cnt.c; gardens.count = cnt.g;
  for (const m of [walls, roofs]) { m.instanceMatrix.needsUpdate = true; m.instanceColor.needsUpdate = true; }
  for (const m of [doors, wins, chims, gardens]) m.instanceMatrix.needsUpdate = true;
  const tip = (k) => { const hh = houses[k]; return hh ? `<strong>@${esc(hh[5])}'s house</strong><br>${HOUSE_TIER[hh[3]] || "a house"}` : ""; };
  for (const m of [walls, roofs, doors]) m.userData.houseTip = tip;
  return g;
}
