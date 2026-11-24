// Buildings, kept as simple as a child's drawing of a house: a box, a triangle roof, a door, a window or two. Every
// kind of building is a variation on that (longer, taller, two of them side by side, a pointed roof for a tower),
// so a whole town is a few hundred boxes and still reads at a glance. What gives it life is what's around and on
// it: lit windows at night, smoke from chimneys, a flag on Aldric's buildings, scaffolding while it goes up.
import * as THREE from "three";
import { C, M, box, mesh } from "./materials.js";
import { rng, hash } from "./noise.js";
import { V } from "./terrain.js";

export const WIN_LIT = new THREE.MeshStandardMaterial({ color: 0x3a3a48, emissive: C.windowLit, emissiveIntensity: 0, roughness: 0.4, flatShading: true });
export const FLAME = new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xff7a1a, emissiveIntensity: 2.2, transparent: true, opacity: 0.9 });

const WALLS = [C.plaster, C.plaster2, C.plaster3, 0xf3d9c4, 0xe9e1cf];
const DOOR = 0x7a5034;

// a triangular prism: the roof. width along x, depth (the slope) along z, apex up
function prism(w, d, h) {
  const x = w / 2, z = d / 2;
  const p = [[-x, 0, -z], [x, 0, -z], [x, 0, z], [-x, 0, z], [-x, h, 0], [x, h, 0]];
  const tri = [[0, 4, 1], [1, 4, 5], [3, 2, 5], [3, 5, 4], [0, 3, 4], [1, 5, 2], [0, 1, 2], [0, 2, 3]];
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(tri.flatMap((t) => t.flatMap((i) => p[i])), 3));
  g.computeVertexNormals();
  return g;
}
const pyramid = (w, h) => new THREE.ConeGeometry(w * 0.75, h, 4).rotateY(Math.PI / 4).translate(0, h / 2, 0);
const at = (o, x, y, z) => { o.position.set(x, y, z); return o; };

function roofColor(b, out) {
  if (b.owner) return C.roofRed;                        // a settler's own build
  if (b.kind === "housing" || b.id === "b0") return C.thatch;
  return out.crowned ? C.slate : 0x6f8fb8;              // Aldric's: blue
}

// the one house: walls, roof, a door at the front (+z), windows along the front and sides
function house(b, R, out, { w, d, h, roof = 1, doors = 1, wins = 1, chimney = false, roofCol, wall, flag = false }) {
  const g = new THREE.Group();
  const wallM = M(wall ?? WALLS[Math.floor(R() * WALLS.length)]);
  g.add(at(mesh(box(w, h, d), wallM), 0, h / 2, 0));
  const r = mesh(prism(w + 0.5, d + 0.6, Math.min(d * 0.55, 2.6) * roof), M(roofCol ?? roofColor(b, out)));
  g.add(at(r, 0, h, 0));
  for (let k = 0; k < doors; k++) {
    const dx = doors === 1 ? (R() - 0.5) * w * 0.3 : (k - (doors - 1) / 2) * w / doors;
    g.add(at(mesh(box(0.9, 1.6, 0.08), M(DOOR)), dx, 0.8, d / 2 + 0.02));
  }
  const win = (x, y, z, side) => { const m = new THREE.Mesh(box(side ? 0.08 : 0.7, 0.6, side ? 0.7 : 0.08), WIN_LIT); at(m, x, y, z); g.add(m); };
  const rows = Math.max(1, Math.floor(h / 2.6));
  for (let row = 0; row < rows; row++) {
    const y = 1.5 + row * 2.4;
    for (let k = 0; k < wins; k++) {
      if (row === 0 && doors === 1 && wins === 1) win(w * 0.3 * (R() < 0.5 ? -1 : 1), y, d / 2 + 0.02, false);
      else if (row > 0 || doors > 1 || wins > 1) win((k - (wins - 1) / 2) * (w / Math.max(1, wins)) + (row === 0 ? w / wins / 2 : 0), y, d / 2 + 0.02, false);
    }
    if (d > 3.5) { win(w / 2 + 0.02, y, 0, true); win(-w / 2 - 0.02, y, 0, true); }
  }
  if (chimney) {
    const c = mesh(box(0.6, 1.6, 0.6), M(C.stone)); at(c, w * 0.28, h + 1.1, -d * 0.15); g.add(c);
    if (out.smoke) { const top = new THREE.Object3D(); top.position.set(w * 0.28, h + 2.0, -d * 0.15); g.add(top); out.smoke.push(top); }
  }
  if (flag && out.flags) {
    const pole = mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.4, 5), M(DOOR)); at(pole, -w * 0.35, h + Math.min(d * 0.55, 2.6) * roof * 0.5 + 1.2, 0); g.add(pole);
    const cloth = mesh(box(0.9, 0.55, 0.04), M(C.banner)); at(cloth, -w * 0.35 + 0.47, h + Math.min(d * 0.55, 2.6) * roof * 0.5 + 2.1, 0); g.add(cloth);
    out.flags.push(cloth);
  }
  return g;
}

const SHAPES = {
  shack: (b, R, out) => {
    const g = house(b, R, out, { w: 4.6, d: 3.8, h: 2.3, roofCol: C.thatchOld, wall: C.plank });
    const ups = (b.upgrades || []).map((u) => String(u.name || u).toLowerCase());
    if (ups.some((u) => /roof/.test(u))) g.children[1].material = M(C.thatch);            // a patched roof
    if (!b.noPit) { const pit = new THREE.Object3D(); at(pit, 3.4, 0, 2.2); g.add(pit); out.fires.push({ obj: pit }); }
    return g;
  },
  hut: (b, R, out) => house(b, R, out, { w: 3.6, d: 3.4, h: 2.1 }),
  cottage: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.8, d: b.size[1] * 0.8, h: 2.6, chimney: R() < 0.6 }),
  longhouse: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.85, d: b.size[1] * 0.75, h: 2.8, doors: 2, wins: 3, chimney: true }),
  rowhouses: (b, R, out) => {                           // two or three little houses shoulder to shoulder
    const g = new THREE.Group(), n = b.size[0] > 14 ? 3 : 2, w = b.size[0] * 0.92 / n;
    for (let k = 0; k < n; k++) g.add(at(house(b, R, out, { w: w - 0.2, d: b.size[1] * 0.8, h: 2.6 + (k % 2) * 0.5, chimney: k === 0 }), (k - (n - 1) / 2) * w, 0, 0));
    return g;
  },
  apartments: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.85, d: b.size[1] * 0.8, h: 5.4, doors: 1, wins: 3, chimney: true }),
  hall: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.9, d: b.size[1] * 0.8, h: 3.4, roof: 1.2, doors: 1, wins: 4, chimney: true, flag: !b.owner }),
  storehouse: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.85, d: b.size[1] * 0.8, h: 3.0, wins: 0, wall: C.plank }),
  workshop: (b, R, out) => house(b, R, out, { w: b.size[0] * 0.85, d: b.size[1] * 0.8, h: 2.8, chimney: true, wall: C.plaster2 }),
  shed: (b, R, out) => house(b, R, out, { w: Math.max(2.6, b.size[0] * 0.7), d: Math.max(2.4, b.size[1] * 0.7), h: 2.0, roof: 0.6, wins: 0, wall: C.plank }),
  tower: (b, R, out) => {
    const g = new THREE.Group(), w = Math.max(3, b.size[0] * 0.6), h = 8.5;
    g.add(at(mesh(box(w, h, w), M(C.stone)), 0, h / 2, 0));
    g.add(at(mesh(pyramid(w + 0.8, 3), M(roofColor(b, out))), 0, h, 0));
    g.add(at(mesh(box(0.9, 1.6, 0.08), M(DOOR)), 0, 0.8, w / 2 + 0.02));
    g.add(at(new THREE.Mesh(box(0.6, 0.7, 0.08), WIN_LIT), 0, h - 1.6, w / 2 + 0.02));
    return g;
  },
  plot: (b, R) => {                                     // a garden: dark soil and rows of green
    const g = new THREE.Group(), r = b.radius ? b.radius * 0.6 : 0, w = r ? r * 1.6 : b.size[0] * 0.9, d = r ? r * 1.6 : b.size[1] * 0.9;
    g.add(at(mesh(box(w, 0.25, d), M(C.soil)), 0, 0.12, 0));
    const rows = Math.max(2, Math.floor(d / 1.2));
    for (let k = 0; k < rows; k++) g.add(at(mesh(box(w * 0.9, 0.35, 0.4), M(k % 2 ? C.crop : C.leaf2)), 0, 0.35, (k - (rows - 1) / 2) * (d / rows)));
    return g;
  },
  firepit: (b, R, out) => {
    const g = new THREE.Group();
    for (let k = 0; k < 7; k++) { const a = k / 7 * Math.PI * 2; g.add(at(mesh(box(0.45, 0.3, 0.45), M(C.stone)), Math.cos(a) * 0.8, 0.15, Math.sin(a) * 0.8)); }
    const f = new THREE.Object3D(); g.add(f); out.fires.push({ obj: f });
    return g;
  },
  prop: (b, R) => at(new THREE.Group().add(at(mesh(box(1, 0.8, 0.8), M(C.plank)), 0, 0.4, 0)), 0, 0, 0),
  fish_trap: (b) => new THREE.Group().add(at(mesh(box(2.2, 0.3, 1.2), M(C.plankDark)), 0, 0.1, 0)),
  well: (b, R) => {
    const g = new THREE.Group();
    g.add(at(mesh(new THREE.CylinderGeometry(1, 1.1, 1, 8), M(C.stone)), 0, 0.5, 0));
    for (const s of [-1, 1]) g.add(at(mesh(box(0.15, 1.8, 0.15), M(DOOR)), s * 0.85, 1.4, 0));
    g.add(at(mesh(prism(2.4, 2.2, 0.8), M(roofColor(b, {}))), 0, 2.2, 0));
    return g;
  },
  wall_ring: (b) => {                                   // a ring of posts round the settlement (follows the ground)
    const g = new THREE.Group(), r = b.radius || 40, n = Math.round(r * 2 * Math.PI / 1.2);
    const im = new THREE.InstancedMesh(box(0.7, 3, 0.7), M(C.plank), n), o = new THREE.Object3D();
    for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2; o.position.set(Math.cos(a) * r, 1.5, Math.sin(a) * r); o.rotation.y = -a; o.updateMatrix(); im.setMatrixAt(i, o.matrix); }
    im.castShadow = true; g.add(im);
    return g;
  },
  road: (b) => new THREE.Group().add(at(mesh(box(b.size[0], 0.12, b.size[1]), M(C.dirt)), 0, 0.06, 0)),
  bridge: (b) => {
    const g = new THREE.Group();
    g.add(at(mesh(box(b.size[0], 0.3, b.size[1]), M(C.plank)), 0, 0.5, 0));
    for (const s of [-1, 1]) g.add(at(mesh(box(b.size[0], 0.6, 0.15), M(C.plankDark)), 0, 0.95, s * b.size[1] / 2));
    return g;
  },
};
SHAPES.jetty = SHAPES.bridge;
SHAPES.path = SHAPES.road;

// while it's going up: a foundation, walls rising with progress, corner poles; the roof goes on at the end
function scaffold(b, R, out) {
  const g = new THREE.Group(), [w0, d0] = b.size || [4, 4], w = w0 * 0.8, d = d0 * 0.8, p = Math.max(0.05, b.progress || 0);
  if (["plot", "road", "bridge", "jetty", "fish_trap", "firepit", "prop", "wall_ring"].includes(b.shape)) {
    const full = (SHAPES[b.shape] || SHAPES.prop)(b, R, { smoke: [], fires: [], flags: [] });
    full.scale.set(1, Math.max(0.2, p), 1);
    return full;
  }
  g.add(at(mesh(box(w + 0.4, 0.3, d + 0.4), M(C.stone)), 0, 0.15, 0));
  const h = (b.shape === "tower" ? 8 : b.shape === "apartments" ? 5.4 : 2.7) * Math.min(1, p * 1.15);
  if (h > 0.2) g.add(at(mesh(box(w, h, d), M(C.plank)), 0, h / 2, 0));
  const top = (b.shape === "tower" ? 9 : 3.4);
  for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) g.add(at(mesh(box(0.15, top, 0.15), M(C.plankDark)), sx * (w / 2 + 0.3), top / 2, sz * (d / 2 + 0.3)));
  for (const y of [top * 0.45, top * 0.9]) for (const s of [-1, 1]) g.add(at(mesh(box(w + 0.8, 0.12, 0.12), M(C.plankDark)), 0, y, s * (d / 2 + 0.3)));
  if (p > 0.85) g.add(at(mesh(prism(w + 0.5, d + 0.6, Math.min(d * 0.55, 2.6) * (p - 0.85) / 0.15), M(roofColor(b, out))), 0, h, 0));
  return g;
}

// fallen down: low broken walls, the roof on the ground beside them
function ruin(b, R) {
  const g = new THREE.Group(), [w0, d0] = b.size || [4, 4], w = w0 * 0.8, d = d0 * 0.8;
  g.add(at(mesh(box(w, 0.9, d), M(0x8e8678)), 0, 0.45, 0));
  const r = mesh(prism(w, d, 1.6), M(0x6e5a44)); at(r, w * 0.3, 0.4, d * 0.4); r.rotation.set(0.5, 0.3, 0.35); g.add(r);
  return g;
}

export function buildingMesh(b, land, ctx) {
  const R = rng(hash(b.id || b.name));
  const out = { smoke: ctx.smoke, fires: ctx.fires, flags: ctx.flags, crowned: ctx.crowned };
  const g = b.state === "ruin" ? ruin(b, R) : b.state === "scaffold" ? scaffold(b, R, out) : (SHAPES[b.shape] || SHAPES.shed)(b, R, out);
  const [x, z] = b.pos;
  const [w, d] = b.size || [4, 4];
  const hs = [land.height(x, z)];
  if (b.shape !== "wall_ring") for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) hs.push(land.height(x + sx * w / 2, z + sz * d / 2));
  const flatLot = ["plot", "road", "firepit", "prop", "bridge", "jetty", "fish_trap"].includes(b.shape);
  const y = b.shape === "wall_ring" ? 0 : flatLot ? Math.max(...hs) * 0.6 + hs[0] * 0.4 : Math.max(...hs);
  g.position.copy(V(x, z, y));
  const drop = y - Math.min(...hs);                    // on a slope it sits level on a stone footing
  if (!flatLot && b.shape !== "wall_ring" && drop > 0.25 && b.state !== "ruin") g.add(at(mesh(box(w * 0.85, drop + 0.4, d * 0.85), M(C.stone)), 0, -(drop + 0.4) / 2 + 0.05, 0));
  g.rotation.y = (b.rot || 0) * Math.PI / 180 + (b.shape === "wall_ring" ? 0 : (R() - 0.5) * 0.06);
  if (b.quality === "shoddy" && b.state === "standing") g.rotation.z = 0.04;       // it leans
  if (b.shape === "wall_ring") {
    g.traverse((o) => {
      if (!o.isInstancedMesh) return;
      const m = new THREE.Matrix4(), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
      for (let i = 0; i < o.count; i++) { o.getMatrixAt(i, m); m.decompose(p, q, s); p.y = land.height(x + p.x, z - p.z) + 1.2; m.compose(p, q, s); o.setMatrixAt(i, m); }
      o.instanceMatrix.needsUpdate = true;
    });
    g.position.copy(V(x, z, 0));
  }
  const tip = `<strong>${esc(b.name)}</strong>${b.owner ? ` <span class="muted">(built by @${esc(b.owner)})</span>` : ""}<br>` + (b.state === "scaffold" ? `being built - ${Math.round((b.progress || 0) * 100)}%`
    : b.state === "ruin" ? "collapsed" : [b.capacity ? `room for ${b.capacity}` : null, b.quality].filter(Boolean).join(", "))
    + (b.residents && b.residents.length ? `<br>${b.residents.length} living here` : "") + (b.look ? `<br><span class="muted">${esc(b.look)}</span>` : "");
  g.traverse((o) => { o.userData.tip = tip; o.userData.building = b; });
  return g;
}

export function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// tents: a triangle of canvas each, and a fire for every few
export function tentsMesh(tents, land, ctx) {
  const g = new THREE.Group();
  if (!tents.length) return g;
  const im = new THREE.InstancedMesh(prism(2.2, 2.4, 1.6), M(0xffffff), tents.length);
  const o = new THREE.Object3D(), col = new THREE.Color();
  tents.forEach(([x, z], i) => {
    const R = rng(i + 9);
    o.position.copy(V(x, z, land.height(x, z) - 0.05)); o.rotation.set(0, (R() - 0.5) * 0.5, 0); o.scale.setScalar(0.9 + R() * 0.2); o.updateMatrix();
    im.setMatrixAt(i, o.matrix); im.setColorAt(i, col.setHex([0xf1e7cf, 0xe8d6ae, 0xd9c9a4, 0xe9b98f, 0xc9d6c1][i % 5]));
  });
  im.castShadow = true; im.receiveShadow = true; g.add(im);
  for (let i = 0; i < tents.length; i += 8) {
    const [x, z] = tents[i], fx = x + 1.6, fz = z - 2.2;
    const ring = new THREE.Group();
    for (let k = 0; k < 5; k++) { const a = k / 5 * Math.PI * 2; ring.add(at(mesh(box(0.3, 0.2, 0.3), M(C.stone)), Math.cos(a) * 0.5, 0.1, Math.sin(a) * 0.5)); }
    ring.position.copy(V(fx, fz, land.height(fx, fz))); g.add(ring);
    ctx.fires.push({ obj: ring, camp: true });
  }
  return g;
}

// the stores: one simple heap per material, taller the more there is
const PILE = { wood: C.plank, stone: C.stone, food: 0xe2c27a, thatch: C.thatch, rope: 0xc9a46a, clay: C.clay, iron: C.iron };
export function pilesMesh(piles, land) {
  const g = new THREE.Group();
  for (const p of piles) {
    const n = Math.min(9, Math.max(1, Math.ceil(Math.log2(p.amount + 1) * 1.5))), [x, z] = p.pos, y = land.height(x, z);
    const heap = new THREE.Group();
    for (let k = 0; k < n; k++) heap.add(at(mesh(box(0.8, 0.6, 0.8), M(PILE[p.material] || C.plank)), (k % 3 - 1) * 0.85, 0.3 + Math.floor(k / 9) * 0.6, (Math.floor(k / 3) % 3 - 1) * 0.85));
    heap.position.copy(V(x, z, y));
    heap.traverse((o) => { o.userData.tip = `<strong>${p.amount} ${p.material}</strong> in the stores`; });
    g.add(heap);
  }
  return g;
}

export function cartMesh(pos, land) {
  const g = new THREE.Group();
  g.add(at(mesh(box(2.4, 0.6, 1.4), M(C.plank)), 0, 0.9, 0));
  for (const s of [-1, 1]) g.add(at(mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.15, 8).rotateX(Math.PI / 2), M(C.plankDark)), -0.4, 0.5, s * 0.75));
  g.add(at(mesh(prism(2.4, 1.6, 1.0), M(0xc45a4a)), 0, 1.2, 0));
  g.position.copy(V(pos[0], pos[1], land.height(pos[0], pos[1])));
  g.traverse((o) => { o.userData.tip = "<strong>The peddler's cart</strong>"; });
  return g;
}
