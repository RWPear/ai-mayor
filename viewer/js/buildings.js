// The building kit: every shape the simulation can make, built from a few parts (stone plinths, timber-framed
// walls, thick thatch or slate roofs, doors, windows that glow at night, chimneys that smoke), with variation
// from each building's id so no two cottages are quite the same. Projects stand as scaffolding that rises
// with their progress; collapses leave ruins.
import * as THREE from "three";
import { C, M, TEX, box, mesh } from "./materials.js";
import { rng, hash } from "./noise.js";
import { V } from "./terrain.js";

export const WIN_LIT = new THREE.MeshStandardMaterial({ color: 0x3a2f22, emissive: C.windowLit, emissiveIntensity: 0, roughness: 0.4 });
const WIN_DARK = new THREE.MeshStandardMaterial({ color: C.glass, roughness: 0.3, metalness: 0.1 });
export const FLAME = new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xff7a1a, emissiveIntensity: 2.2, transparent: true, opacity: 0.9 });

const PLASTERS = [C.plaster, C.plaster2, C.plaster3, 0xf0d9b5, 0xe9dcc0];
const wallMat = (style, R) => style === "plank" ? M(C.plank, "plank") : style === "stone" ? M(0xffffff, "stone")
  : style === "brick" ? M(0xffffff, "brick") : M(PLASTERS[Math.floor(R() * PLASTERS.length)], "plaster");
const roofMat = (kind) => kind === "slate" ? M(0xffffff, "slate") : kind === "plank" ? M(C.plankDark, "plank") : M(0xffffff, "thatch");

// a pitched roof: two thick slabs meeting at a ridge along x, plus gable triangles
function gableRoof(w, d, rise, overhang, kind, wallM, thick = 0.35) {
  const g = new THREE.Group();
  const half = d / 2 + overhang, slope = Math.hypot(half, rise), ang = Math.atan2(rise, half);
  for (const s of [-1, 1]) {
    const slab = mesh(box(w + overhang * 2, thick, slope), roofMat(kind));
    slab.rotation.x = s * ang; slab.position.set(0, rise / 2, s * half / 2);
    g.add(slab);
  }
  const tri = new THREE.Shape([new THREE.Vector2(-d / 2, 0), new THREE.Vector2(d / 2, 0), new THREE.Vector2(0, rise * (d / 2) / half)]);
  for (const s of [-1, 1]) {
    const end = mesh(new THREE.ShapeGeometry(tri), wallM); end.rotation.y = Math.PI / 2 * s; end.position.x = s * w / 2;
    end.material = wallM; g.add(end);
  }
  const ridge = mesh(new THREE.CylinderGeometry(0.16, 0.16, w + overhang * 2, 6), roofMat(kind));
  ridge.rotation.z = Math.PI / 2; ridge.position.y = rise + 0.08; g.add(ridge);
  return g;
}

function timberFrame(g, w, d, h, y0) {   // dark posts and beams over plaster: the cosy medieval look
  const T = M(C.timber);
  const posts = Math.max(2, Math.round(w / 2.2));
  for (const side of [-1, 1]) {
    for (let k = 0; k <= posts; k++) { const p = mesh(box(0.18, h, 0.12), T); p.position.set(-w / 2 + k * w / posts, y0 + h / 2, side * (d / 2 + 0.02)); g.add(p); }
    for (const yy of [y0 + 0.08, y0 + h * 0.55, y0 + h - 0.08]) { const b = mesh(box(w + 0.1, 0.16, 0.12), T); b.position.set(0, yy, side * (d / 2 + 0.03)); g.add(b); }
    const brace = mesh(box(0.14, Math.hypot(w / posts, h * 0.45), 0.1), T);
    brace.rotation.z = Math.atan2(w / posts, h * 0.45) * side; brace.position.set(side * (w / 2 - w / posts / 2), y0 + h * 0.77, side * (d / 2 + 0.04)); g.add(brace);
  }
  for (const side of [-1, 1]) for (const zz of [-d / 2, d / 2]) { const p = mesh(box(0.2, h, 0.2), T); p.position.set(side * (w / 2 + 0.02), y0 + h / 2, zz); g.add(p); }
}

function windowsOn(g, w, d, y, n, lit, face = 1, size = [0.7, 0.8]) {
  for (let k = 0; k < n; k++) {
    const x = -w / 2 + (k + 0.5) * w / n;
    const win = mesh(new THREE.BoxGeometry(size[0], size[1], 0.1), lit ? WIN_LIT : WIN_DARK, { cast: false });
    win.position.set(x, y, face * (d / 2 + 0.06)); g.add(win);
    const sill = mesh(box(size[0] + 0.2, 0.1, 0.2), M(C.timber)); sill.position.set(x, y - size[1] / 2 - 0.05, face * (d / 2 + 0.1)); g.add(sill);
    for (const s of [-1, 1]) { const sh = mesh(box(0.32, size[1], 0.05), M(0x5d7a4a)); sh.position.set(x + s * (size[0] / 2 + 0.18), y, face * (d / 2 + 0.1)); sh.rotation.y = s * 0.35; g.add(sh); }
  }
}

function door(g, x, d, y0, face = 1, w = 1.0, h = 1.9) {
  const dr = mesh(box(w, h, 0.12), M(C.plankDark, "plank")); dr.position.set(x, y0 + h / 2, face * (d / 2 + 0.05)); g.add(dr);
  const lintel = mesh(box(w + 0.3, 0.18, 0.18), M(C.timber)); lintel.position.set(x, y0 + h + 0.08, face * (d / 2 + 0.08)); g.add(lintel);
}

function plinth(g, w, d, h = 0.55) {
  const p = mesh(box(w + 0.3, h + 1.5, d + 0.3), M(0xffffff, "stone")); p.position.y = (h - 1.5) / 2; g.add(p);
  return h;
}

function chimney(g, x, z, top, list) {
  const c = mesh(box(0.7, 2.2, 0.7), M(0xffffff, "stone")); c.position.set(x, top - 0.6, z); g.add(c);
  const pot = new THREE.Object3D(); pot.position.set(x, top + 0.55, z); g.add(pot);
  list.push(pot);
}

function house(R, w, d, h, opt, out) {    // walls + roof: the shared body of cottages, rows, halls
  const g = new THREE.Group();
  const y0 = plinth(g, w, d, opt.plinth ?? 0.5);
  const wm = wallMat(opt.walls, R);
  const walls = mesh(box(w, h, d), wm); walls.position.y = y0 + h / 2; g.add(walls);
  if (opt.walls === "plaster") timberFrame(g, w, d, h, y0);
  const roof = gableRoof(w, d, opt.rise ?? Math.max(1.6, d * 0.55), opt.overhang ?? 0.55, opt.roof || "thatch", wm, opt.roof === "slate" ? 0.2 : 0.42);
  roof.position.y = y0 + h; g.add(roof);
  door(g, opt.doorX ?? (R() - 0.5) * w * 0.4, d, y0, -1);
  windowsOn(g, w, d, y0 + h * 0.58, Math.max(1, Math.round(w / 3.2)), opt.lit, -1);
  windowsOn(g, w, d, y0 + h * 0.58, Math.max(1, Math.round(w / 4)), opt.lit, 1);
  if (opt.chimney !== false) chimney(g, w * (R() < 0.5 ? -0.3 : 0.3), d * 0.15, y0 + h + (opt.rise ?? d * 0.55) * 0.75, out.smoke);
  return g;
}

const SHAPES = {
  shack(b, R, out) {
    // a lean-to of weathered planks: taller at the front, a roof patched with whatever was to hand, a door
    // that won't shut, a crate and a cold fire pit
    const g = new THREE.Group(), [w, d, hf, hb] = [4.6, 3.8, 2.6, 1.9];
    const wood = M(0xb08a62, "plank"), dark = M(0x8a6844, "plank"), post = M(0x5e4430);
    const front = mesh(box(w, hf, 0.14), wood); front.position.set(0, hf / 2, -d / 2); g.add(front);
    const back = mesh(box(w, hb, 0.14), wood); back.position.set(0, hb / 2, d / 2); g.add(back);
    for (const s of [-1, 1]) {
      const shape = new THREE.Shape([new THREE.Vector2(-d / 2, 0), new THREE.Vector2(d / 2, 0), new THREE.Vector2(d / 2, hf), new THREE.Vector2(-d / 2, hb)]);
      const side = mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.14, bevelEnabled: false }), dark);
      side.rotation.y = Math.PI / 2; side.position.set(s * w / 2 - (s > 0 ? 0.14 : 0), 0, 0); g.add(side);
      for (const zz of [-d / 2, d / 2]) { const p = mesh(box(0.18, zz < 0 ? hf + 0.1 : hb + 0.1, 0.18), post); p.position.set(s * (w / 2), (zz < 0 ? hf : hb) / 2, zz); g.add(p); }
    }
    const fall = Math.atan2(hf - hb, d);
    const roof = mesh(box(w + 0.8, 0.14, Math.hypot(d, hf - hb) + 0.9), M(0x9c8060, "plank")); roof.rotation.x = fall; roof.position.set(0, (hf + hb) / 2 + 0.12, 0); g.add(roof);
    const patch = mesh(box(1.3, 0.08, 1.1), M(0xffffff, "thatch")); patch.rotation.x = fall; patch.position.set(0.9, (hf + hb) / 2 + 0.22, 0.3); g.add(patch);
    const patch2 = mesh(box(0.9, 0.06, 0.8), M(0x9a8a70, "canvas")); patch2.rotation.x = fall; patch2.position.set(-1.2, (hf + hb) / 2 + 0.2, -0.6); g.add(patch2);
    for (let k = 0; k < 4; k++) { const p = mesh(box(0.25 + R() * 0.3, 0.5 + R() * 0.7, 0.05), M(0xc79a68, "plank")); p.position.set(0.6 + R() * 1.3, 0.4 + R() * 1.4, -(d / 2 + 0.09)); p.rotation.z = (R() - 0.5) * 0.5; g.add(p); }
    const dr = mesh(box(0.9, 1.85, 0.08), M(0x6e5136, "plank")); dr.position.set(-1.05, 0.93, -(d / 2 + 0.35)); dr.rotation.y = 0.55; g.add(dr);
    const gap = mesh(box(0.9, 1.85, 0.05), M(0x1a130d)); gap.position.set(-1.4, 0.93, -(d / 2 + 0.02)); g.add(gap);
    const crate = mesh(box(0.7, 0.6, 0.7), M(C.plank, "plank")); crate.position.set(1.8, 0.3, -2.6); crate.rotation.y = 0.4; g.add(crate);
    if (!b.noPit) {
      const pit = mesh(new THREE.TorusGeometry(0.5, 0.15, 5, 10).rotateX(Math.PI / 2), M(C.stone)); pit.position.set(-2.3, 0.1, -3.2); g.add(pit);
      out.fires.push({ obj: pit, small: true });
    }
    // his fixes, as he makes them: a proper roof, a door that shuts, a chimney, a window
    const ups = (b.upgrades || []).map((u) => (typeof u === "string" ? u : u.name).toLowerCase());
    if (ups.some((u) => /roof|thatch/.test(u))) {         // a proper thatched gable on the old walls
      for (const p of [patch, patch2, roof]) p.visible = false;
      const up = mesh(box(w, hf - hb + 0.05, 0.14), wood); up.position.set(0, hb + (hf - hb) / 2, d / 2); g.add(up);
      for (const sx of [-1, 1]) { const fill = mesh(box(0.14, hf - hb, d), dark); fill.position.set(sx * (w / 2 - 0.07), hb + (hf - hb) / 2, 0); fill.scale.y = 1; g.add(fill); }
      const gab = gableRoof(w + 0.1, d + 0.1, 1.7, 0.5, "thatch", dark, 0.45); gab.position.y = hf; g.add(gab);
    }
    if (ups.some((u) => /door/.test(u))) { dr.rotation.y = 0; dr.position.set(-1.4, 0.93, -(d / 2 + 0.1)); gap.visible = false; }
    if (ups.some((u) => /chimney|hearth|fireplace/.test(u))) chimney(g, w / 2 - 0.5, d / 2 - 0.5, hb + 1.2, out.smoke);
    if (ups.some((u) => /window/.test(u))) { const win = mesh(box(0.8, 0.7, 0.1), out.lit ? WIN_LIT : WIN_DARK, { cast: false }); win.position.set(1.0, 1.5, -(d / 2 + 0.1)); g.add(win); }
    return g;
  },
  firepit(b, R, out) {
    // a ring of stones, a few logs to sit on, a pot on a tripod: the first thing that makes the field a home
    const g = new THREE.Group();
    for (let k = 0; k < 9; k++) { const a = k / 9 * Math.PI * 2; const st = mesh(new THREE.DodecahedronGeometry(0.22 + R() * 0.08, 0), M(C.stone, null, { flatShading: true })); st.position.set(Math.cos(a) * 0.65, 0.12, Math.sin(a) * 0.65); st.scale.y = 0.7; g.add(st); }
    const pit = new THREE.Object3D(); pit.position.y = 0.05; g.add(pit);
    out.fires.push({ obj: pit, small: true });
    for (let k = 0; k < 3; k++) { const a = k / 3 * Math.PI * 2 + 0.4; const log = mesh(new THREE.CylinderGeometry(0.2, 0.2, 1.3, 7), M(C.trunk)); log.rotation.z = Math.PI / 2; log.rotation.y = -a; log.position.set(Math.cos(a) * 1.5, 0.2, Math.sin(a) * 1.5); g.add(log); }
    for (let k = 0; k < 3; k++) { const a = k / 3 * Math.PI * 2; const leg = mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.4, 4), M(C.timber)); leg.position.set(Math.cos(a) * 0.35, 0.65, Math.sin(a) * 0.35); leg.rotation.set(Math.sin(a) * 0.25, 0, -Math.cos(a) * 0.25); g.add(leg); }
    const pot = mesh(new THREE.SphereGeometry(0.22, 8, 6), M(C.iron)); pot.position.y = 0.75; g.add(pot);
    return g;
  },
  prop(b, R, out) {
    // the odds and ends of a homestead: a drying rack, a bench, a chopping block with its woodpile
    const g = new THREE.Group(), n = (b.name || "").toLowerCase();
    if (/rack|line|hide|dry/.test(n)) {
      for (const s of [-1, 1]) for (const z of [-0.4, 0.4]) { const leg = mesh(box(0.1, 1.6, 0.1), M(C.timber)); leg.position.set(s * 1.0, 0.8, z * (s > 0 ? 1 : -1)); leg.rotation.x = z * 0.4; g.add(leg); }
      const bar = mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.3, 5), M(C.timber)); bar.rotation.z = Math.PI / 2; bar.position.y = 1.5; g.add(bar);
      for (let k = 0; k < 3; k++) { const c = mesh(box(0.5, 0.7, 0.04), M([C.canvas, C.thatch, C.plank][k])); c.position.set(-0.6 + k * 0.6, 1.15, 0); g.add(c); }
    } else if (/bench|seat|stool|chair|table/.test(n)) {
      const top = mesh(box(2.0, 0.12, 0.5), M(C.plank)); top.position.y = 0.5; g.add(top);
      for (const s of [-1, 1]) { const l = mesh(box(0.14, 0.5, 0.4), M(C.plankDark)); l.position.set(s * 0.8, 0.25, 0); g.add(l); }
    } else {
      const block = mesh(new THREE.CylinderGeometry(0.35, 0.4, 0.6, 8), M(C.trunk)); block.position.set(-0.6, 0.3, 0); g.add(block);
      for (let k = 0; k < 8; k++) { const log = mesh(new THREE.CylinderGeometry(0.15, 0.15, 1.2, 6), M(C.trunk)); log.rotation.x = Math.PI / 2; log.position.set(0.5 + (k % 4) * 0.3, 0.15 + Math.floor(k / 4) * 0.28, 0); g.add(log); }
    }
    return g;
  },
  hut(b, R, out) {
    const g = new THREE.Group(), [w, , h] = b.size;
    const r = Math.max(1.4, w / 2);
    const wall = mesh(new THREE.CylinderGeometry(r, r * 1.05, h * 0.6, 12), M(0x8a6a48, "plank")); wall.position.y = h * 0.3; g.add(wall);
    const roof = mesh(new THREE.ConeGeometry(r * 1.45, h * 0.8, 12), roofMat("thatch")); roof.position.y = h * 0.6 + h * 0.4; g.add(roof);
    door(g, 0, r * 2, 0, -1, 0.8, 1.5);
    return g;
  },
  cottage(b, R, out) {
    const [w, d, h] = b.size;
    const g = house(R, w * 0.85, d * 0.8, h * 0.62, { walls: b.material === "stone" ? "stone" : b.material === "clay" ? "brick" : "plaster", roof: b.material === "stone" ? "slate" : "thatch", lit: out.lit }, out);
    const fence = new THREE.Group();
    for (let k = 0; k < 7; k++) { const p = mesh(box(0.12, 0.8, 0.12), M(C.plank)); p.position.set(-w / 2 + k * w / 6, 0.4, -(d / 2 + 1.4)); fence.add(p); }
    const rail = mesh(box(w, 0.1, 0.08), M(C.plank)); rail.position.set(0, 0.6, -(d / 2 + 1.4)); fence.add(rail);
    if (R() < 0.7) g.add(fence);
    return g;
  },
  longhouse(b, R, out) {
    const [w, d, h] = b.size;
    const g = house(R, w, d * 0.82, h * 0.45, { walls: "plank", roof: "thatch", rise: d * 0.7, overhang: 0.9, lit: out.lit, plinth: 0.3 }, out);
    door(g, w * 0.3, d * 0.82, 0.3, -1); door(g, -w * 0.3, d * 0.82, 0.3, 1);
    return g;
  },
  rowhouses(b, R, out) {
    const [w, d, h] = b.size, g = new THREE.Group();
    const n = Math.max(3, Math.round(w / 5.5)), uw = w / n;
    for (let k = 0; k < n; k++) {
      const u = house(rng(hash(b.id) + k), uw - 0.1, d * 0.8, h * 0.6, { walls: k % 3 === 2 ? "brick" : "plaster", roof: b.material === "stone" ? "slate" : "thatch", lit: out.lit, chimney: true, rise: d * 0.42, overhang: 0.35 }, out);
      u.position.x = -w / 2 + (k + 0.5) * uw; g.add(u);
    }
    return g;
  },
  apartments(b, R, out) {
    // a stone ground floor, jettied timber-framed storeys above (each a little wider), a steep slate roof
    const [w, d, h] = b.size, g = new THREE.Group();
    const floors = Math.max(3, Math.round(h / 3.1)), fh = h / floors;
    const y0 = plinth(g, w, d, 0.4);
    const base = mesh(box(w, fh, d), M(0xffffff, "stone")); base.position.y = y0 + fh / 2; g.add(base);
    for (const f of [-1, 1]) for (let k = 0; k < Math.round(w / 3); k++) {
      const arch = mesh(box(1.4, fh * 0.7, 0.2), M(0x2b2622)); arch.position.set(-w / 2 + (k + 0.5) * w / Math.round(w / 3), y0 + fh * 0.35, f * (d / 2 + 0.05)); g.add(arch);
    }
    for (let f = 1; f < floors; f++) {
      const jw = w + f * 0.35, jd = d + f * 0.35, y = y0 + f * fh;
      const fl = mesh(box(jw, fh, jd), M(PLASTERS[(hash(b.id) + f) % PLASTERS.length], "plaster")); fl.position.y = y + fh / 2; g.add(fl);
      timberFrame(g, jw, jd, fh, y);
      windowsOn(g, jw, jd, y + fh * 0.55, Math.round(jw / 2.4), out.lit && R() < 0.85, -1, [0.8, 1.0]);
      windowsOn(g, jw, jd, y + fh * 0.55, Math.round(jw / 2.4), out.lit && R() < 0.85, 1, [0.8, 1.0]);
      const beam = mesh(box(jw + 0.2, 0.25, jd + 0.2), M(C.timber)); beam.position.y = y; g.add(beam);
    }
    const tw = w + floors * 0.35, td = d + floors * 0.35;
    const roof = gableRoof(tw, td, td * 0.6, 0.5, "slate", M(PLASTERS[0], "plaster"), 0.22); roof.position.y = y0 + floors * fh; g.add(roof);
    for (const s of [-0.3, 0.3]) chimney(g, tw * s, 0, y0 + floors * fh + td * 0.45, out.smoke);
    const stair = mesh(box(1.2, fh * 1.4, 3), M(C.plank, "plank")); stair.position.set(w / 2 + 0.7, y0 + fh * 0.7, 0); stair.rotation.x = 0.5; g.add(stair);
    door(g, 0, d, y0, -1, 1.4, 2.2);
    return g;
  },
  hall(b, R, out) {
    const [w, d, h] = b.size;
    const g = house(R, w, d, h * 0.55, { walls: b.material === "stone" ? "stone" : "plank", roof: b.material === "stone" ? "slate" : "thatch", rise: d * 0.75, overhang: 0.8, lit: out.lit }, out);
    door(g, 0, d, 0.5, -1, 2.0, 2.8);
    for (const s of [-1, 1]) {
      const pole = mesh(new THREE.CylinderGeometry(0.08, 0.08, 4.5, 6), M(C.timber)); pole.position.set(s * 2.2, 2.25, -(d / 2 + 1.2)); g.add(pole);
      const flag = mesh(box(0.05, 1.6, 0.9), M(out.crowned ? C.banner : 0x7a5a3a, null, { side: THREE.DoubleSide })); flag.position.set(s * 2.2, 3.6, -(d / 2 + 1.2) + 0.5); g.add(flag);
      out.flags.push(flag);
    }
    return g;
  },
  storehouse(b, R, out) {
    const [w, d, h] = b.size, g = new THREE.Group();
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const st = mesh(new THREE.CylinderGeometry(0.3, 0.4, 0.9, 6), M(C.stone)); st.position.set(sx * w * 0.38, 0.45, sz * d * 0.36); g.add(st); }
    const body = mesh(box(w * 0.9, h * 0.6, d * 0.85), M(C.plankDark, "plank")); body.position.y = 0.9 + h * 0.3; g.add(body);
    const roof = gableRoof(w * 0.9, d * 0.85, d * 0.4, 0.5, "plank", M(C.plankDark, "plank"), 0.2); roof.position.y = 0.9 + h * 0.6; g.add(roof);
    const ramp = mesh(box(1.2, 0.12, 2.2), M(C.plank, "plank")); ramp.position.set(0, 0.5, -(d * 0.42 + 1.0)); ramp.rotation.x = 0.4; g.add(ramp);
    for (let k = 0; k < 4; k++) { const s = mesh(new THREE.CylinderGeometry(0.3, 0.35, 0.6, 8), M(0xb59a6a, "canvas")); s.position.set(w / 2 + 0.4, 0.3, -d / 3 + k * 0.7); g.add(s); }
    return g;
  },
  workshop(b, R, out) {
    const [w, d, h] = b.size, g = new THREE.Group();
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const p = mesh(box(0.3, h * 0.75, 0.3), M(C.timber)); p.position.set(sx * w / 2, h * 0.375, sz * d / 2); g.add(p); }
    const back = mesh(box(w, h * 0.75, 0.2), M(C.plank, "plank")); back.position.set(0, h * 0.375, d / 2); g.add(back);
    const roof = mesh(box(w + 0.8, 0.25, d + 0.8), roofMat("thatch")); roof.position.y = h * 0.8; roof.rotation.x = 0.18; g.add(roof);
    const smith = /forge|smith|anvil|metal/.test((b.name || "").toLowerCase()) || b.boosts === "iron";
    const kiln = /kiln|pottery|brick/.test((b.name || "").toLowerCase());
    if (smith || kiln) {
      const f = mesh(kiln ? new THREE.SphereGeometry(1.3, 10, 8, 0, Math.PI * 2, 0, Math.PI / 2) : box(1.6, 1, 1.4), M(0xffffff, kiln ? "brick" : "stone"));
      f.position.set(-w / 4, kiln ? 0 : 0.5, 0); g.add(f);
      const ember = mesh(new THREE.SphereGeometry(0.3, 8, 6), FLAME); ember.position.set(-w / 4, kiln ? 0.4 : 1.05, -0.5); g.add(ember);
      out.fires.push({ obj: ember });
      const anvil = mesh(box(0.8, 0.6, 0.4), M(C.iron, null, { metalness: 0.6, roughness: 0.4 })); anvil.position.set(w / 4, 0.3, -0.3); g.add(anvil);
    } else {
      const horse = mesh(box(2.2, 0.8, 0.6), M(C.plank, "plank")); horse.position.set(0, 0.6, -0.4); g.add(horse);
      for (let k = 0; k < 5; k++) { const log = mesh(new THREE.CylinderGeometry(0.22, 0.22, 2.6, 7), M(C.trunk)); log.rotation.z = Math.PI / 2; log.position.set(w / 3, 0.22 + k * 0.42 * (k < 3 ? 1 : 0.8), d / 4 - (k % 3) * 0.45); g.add(log); }
    }
    return g;
  },
  plot(b, R, out) {
    const [w, d] = b.size, g = new THREE.Group();
    const soil = mesh(box(w, 0.25, d), M(0xffffff, "soil")); soil.position.y = 0.05; g.add(soil);
    const rows = Math.max(3, Math.round(d / 1.3));
    for (let k = 0; k < rows; k++) {
      const ridge = mesh(box(w * 0.92, 0.25, 0.5), M(0xffffff, "soil")); ridge.position.set(0, 0.25, -d / 2 + (k + 0.5) * d / rows); g.add(ridge);
      for (let j = 0; j < Math.round(w / 0.9); j++) { const p = mesh(new THREE.IcosahedronGeometry(0.28, 0), M(C.crop, null, { flatShading: true })); p.position.set(-w * 0.44 + j * 0.9, 0.5, -d / 2 + (k + 0.5) * d / rows); p.scale.y = 0.8 + R() * 0.6; g.add(p); }
    }
    for (let k = 0; k <= Math.round(w / 2); k++) for (const s of [-1, 1]) { const p = mesh(box(0.12, 0.9, 0.12), M(C.plank)); p.position.set(-w / 2 + k * 2 * w / Math.round(w / 2) / 2, 0.45, s * (d / 2 + 0.3)); g.add(p); }
    const sc = new THREE.Group();
    sc.add(at(mesh(box(0.1, 1.8, 0.1), M(C.plank)), 0, 0.9, 0), at(mesh(box(1.2, 0.1, 0.1), M(C.plank)), 0, 1.4, 0), at(mesh(new THREE.ConeGeometry(0.4, 0.3, 8), M(C.thatch)), 0, 2.0, 0));
    sc.position.set(w * 0.3, 0, 0); g.add(sc);
    return g;
  },
  fish_trap(b, R) {
    const g = new THREE.Group();
    for (let k = 0; k < 14; k++) { const a = k / 14 * Math.PI * 1.4; const p = mesh(new THREE.CylinderGeometry(0.06, 0.08, 1.6, 5), M(C.trunk)); p.position.set(Math.cos(a) * 1.8, -0.2, Math.sin(a) * 1.4); g.add(p); }
    return g;
  },
  well(b, R) {
    const g = new THREE.Group();
    const ring = mesh(new THREE.CylinderGeometry(1, 1.05, 1.0, 14, 1, true), M(0xffffff, "stone", { side: THREE.DoubleSide })); ring.position.y = 0.5; g.add(ring);
    for (const s of [-1, 1]) { const p = mesh(box(0.15, 2.2, 0.15), M(C.timber)); p.position.set(s * 0.9, 1.1, 0); g.add(p); }
    const roof = gableRoof(2.2, 1.6, 0.6, 0.2, "plank", M(C.plankDark, "plank"), 0.12); roof.position.y = 2.2; g.add(roof);
    const bucket = mesh(new THREE.CylinderGeometry(0.2, 0.16, 0.3, 8), M(C.plank)); bucket.position.set(0, 1.2, 0); g.add(bucket);
    return g;
  },
  tower(b, R, out) {
    const [w, , h] = b.size, g = new THREE.Group();
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) { const p = mesh(box(0.35, h, 0.35), M(C.timber)); p.position.set(sx * w / 2, h / 2, sz * w / 2); p.rotation.z = -sx * 0.03; g.add(p); }
    const deck = mesh(box(w + 1, 0.3, w + 1), M(C.plank, "plank")); deck.position.y = h - 1.6; g.add(deck);
    const roof = mesh(new THREE.ConeGeometry(w * 0.95, 2.4, 4), roofMat("thatch")); roof.position.y = h + 0.4; roof.rotation.y = Math.PI / 4; g.add(roof);
    const lad = mesh(box(0.6, h - 1.6, 0.1), M(C.plank)); lad.position.set(0, (h - 1.6) / 2, -w / 2 - 0.3); lad.rotation.x = -0.12; g.add(lad);
    return g;
  },
  wall_ring(b, R) {
    const g = new THREE.Group(), r = b.radius || b.size[0] / 2;
    const n = Math.round(r * 2 * Math.PI / 0.55);
    const geo = new THREE.CylinderGeometry(0.26, 0.3, 3.6, 6);
    geo.translate(0, 1.8, 0);
    const tip = new THREE.ConeGeometry(0.27, 0.6, 6).translate(0, 3.9, 0);
    const posts = new THREE.InstancedMesh(geo, M(0x7a5634, null, { flatShading: true }), n);
    const tips = new THREE.InstancedMesh(tip, M(0x8e6b45, null, { flatShading: true }), n);
    const o = new THREE.Object3D();
    let k = 0;
    for (let i = 0; i < n; i++) {
      const a = i / n * Math.PI * 2;
      if (Math.abs(Math.sin(a + 0.15) + 1) < 0.02) continue;                // a gap for the gate (south, where the road comes in)
      o.position.set(Math.cos(a) * r, 0, Math.sin(a) * r); o.scale.set(1, 0.85 + R() * 0.3, 1); o.updateMatrix();
      posts.setMatrixAt(k, o.matrix); tips.setMatrixAt(k, o.matrix); k++;
    }
    posts.count = tips.count = k; posts.castShadow = tips.castShadow = true;
    g.add(posts, tips);
    g.userData.followGround = true;
    return g;
  },
  bridge(b, R) {
    const [w, d] = b.size, g = new THREE.Group();
    const deck = mesh(box(w, 0.25, d), M(C.plank, "plank")); deck.position.y = 0.3; g.add(deck);
    for (const s of [-1, 1]) { const rail = mesh(box(0.12, 0.12, d), M(C.timber)); rail.position.set(s * w / 2, 1.1, 0); g.add(rail); for (let k = 0; k < 6; k++) { const p = mesh(box(0.14, 1.4, 0.14), M(C.timber)); p.position.set(s * w / 2, 0.4, -d / 2 + k * d / 5); g.add(p); } }
    return g;
  },
  jetty(b, R) { const g = SHAPES.bridge(b, R); return g; },
  road(b) { const g = new THREE.Group(); const s = mesh(box(b.size[0], 0.12, b.size[1]), M(0xffffff, "stone")); s.position.y = 0.06; g.add(s); return g; },
  shed(b, R, out) {
    const [w, d, h] = b.size;
    return house(R, w * 0.85, d * 0.85, h * 0.55, { walls: "plank", roof: "plank", rise: d * 0.35, chimney: /smoke/.test(b.name || ""), lit: false, plinth: 0.25 }, out);
  },
};

function ruin(b, R) {
  const [w, d] = b.size, g = new THREE.Group();
  const scorch = new THREE.Mesh(new THREE.CircleGeometry(Math.max(w, d) * 0.6, 16).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x1a1410, transparent: true, opacity: 0.45, depthWrite: false }));
  scorch.position.y = 0.05; g.add(scorch);
  for (let k = 0; k < 7; k++) { const s = mesh(box(w * (0.2 + R() * 0.3), 0.3 + R() * 1.0, 0.4), M(0x7a7066, "stone")); const side = k % 4; s.position.set(side < 2 ? (R() - 0.5) * w : (side === 2 ? -w / 2 : w / 2), 0.3, side < 2 ? (side ? d / 2 : -d / 2) : (R() - 0.5) * d); s.rotation.y = side < 2 ? 0 : Math.PI / 2; g.add(s); }
  for (let k = 0; k < 6; k++) { const beam = mesh(box(0.25, 0.25, 2 + R() * 3), M(0x3a2a1e)); beam.position.set((R() - 0.5) * w, 0.3 + R() * 0.6, (R() - 0.5) * d); beam.rotation.set(R() * 0.6, R() * 3, R() * 0.4); g.add(beam); }
  return g;
}

function scaffold(b, R, out) {
  // the finished building, cut off at the progress line; poles, ledgers, ladder and planks around it
  const g = new THREE.Group();
  const p = Math.max(0.04, Math.min(1, b.progress || 0));
  const full = (SHAPES[b.shape] || SHAPES.shed)(b, R, { ...out, lit: false, smoke: [], fires: [], flags: [] });
  const bbox = new THREE.Box3().setFromObject(full);
  const top = bbox.max.y, cut = top * Math.min(1, p * 1.12);
  full.traverse((o) => {
    if (!o.isMesh) return;
    const bb = new THREE.Box3().setFromObject(o);
    if (bb.min.y > cut) o.visible = false;
    else if (bb.max.y > cut && bb.max.y - bb.min.y > 0.5 && !o.isInstancedMesh) { const keep = (cut - bb.min.y) / (bb.max.y - bb.min.y); o.scale.y *= Math.max(0.05, keep); o.position.y -= (bb.max.y - bb.min.y) * (1 - keep) / 2; }
  });
  const [w, d] = [bbox.max.x - bbox.min.x, bbox.max.z - bbox.min.z];
  if ((b.progress || 0) < 0.06) {                      // just planned: stakes and string in the grass, a first pile
    const stake = M(0xc9a26a), str = new THREE.LineBasicMaterial({ color: 0xf2e6c8 });
    const pts = [];
    for (const [sx, sz] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      const st = mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.9, 5), stake); st.position.set(sx * w / 2, 0.45, sz * d / 2); g.add(st);
      pts.push(new THREE.Vector3(sx * w / 2, 0.75, sz * d / 2));
    }
    pts.push(pts[0].clone());
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), str));
    for (let k = 0; k < 4; k++) { const pl = mesh(new THREE.CylinderGeometry(0.2, 0.2, 2.2, 6), M(C.trunk)); pl.rotation.z = Math.PI / 2; pl.position.set(-w / 2 - 1.5, 0.2 + (k > 2 ? 0.36 : 0), -d / 4 + (k % 3) * 0.42); g.add(pl); }
    return g;
  }
  g.add(full);
  if (b.shape === "wall_ring" || b.shape === "plot" || b.shape === "road") return g;
  const pole = M(0xb08a58);
  const poleTop = Math.min(top + 1, cut + 2.4);       // scaffolding only rises as fast as the walls do
  const nx = Math.max(2, Math.round(w / 2.5)), nz = Math.max(2, Math.round(d / 2.5));
  for (let i = 0; i <= nx; i++) for (const s of [-1, 1]) { const pl = mesh(new THREE.CylinderGeometry(0.07, 0.07, poleTop, 5), pole); pl.position.set(bbox.min.x + i * w / nx, poleTop / 2, s * (d / 2 + 0.8)); g.add(pl); }
  for (let i = 0; i <= nz; i++) for (const s of [-1, 1]) { const pl = mesh(new THREE.CylinderGeometry(0.07, 0.07, poleTop, 5), pole); pl.position.set(s * (w / 2 + 0.8), poleTop / 2, bbox.min.z + i * d / nz); g.add(pl); }
  for (let y = 2; y < poleTop; y += 2) for (const s of [-1, 1]) {
    const lx = mesh(new THREE.CylinderGeometry(0.06, 0.06, w + 1.8, 5), pole); lx.rotation.z = Math.PI / 2; lx.position.set(0, y, s * (d / 2 + 0.8)); g.add(lx);
    const lz = mesh(new THREE.CylinderGeometry(0.06, 0.06, d + 1.8, 5), pole); lz.rotation.x = Math.PI / 2; lz.position.set(s * (w / 2 + 0.8), y, 0); g.add(lz);
    if (y < cut + 1) { const plank = mesh(box(w + 1.4, 0.08, 0.6), M(C.plank, "plank")); plank.position.set(0, y + 0.06, s * (d / 2 + 0.8)); g.add(plank); }
  }
  const lad = mesh(box(0.6, poleTop, 0.08), M(C.plank)); lad.position.set(w / 2 + 1.3, poleTop / 2, 0); lad.rotation.z = 0.2; g.add(lad);
  for (let k = 0; k < 6; k++) { const pl = mesh(box(0.3, 0.12, 3), M(C.plank, "plank")); pl.position.set(-w / 2 - 2.2, 0.08 + k * 0.13, -d / 4); g.add(pl); }
  return g;
}

export function buildingMesh(b, land, ctx) {
  const R = rng(hash(b.id || b.name));
  const out = { smoke: ctx.smoke, fires: ctx.fires, flags: ctx.flags, lit: (b.residents && b.residents.length > 0) || b.shape === "hall", crowned: ctx.crowned };
  let g;
  if (b.state === "ruin") g = ruin(b, R);
  else if (b.state === "scaffold") g = scaffold(b, R, out);
  else g = (SHAPES[b.shape] || SHAPES.shed)(b, R, out);
  const [x, z] = b.pos;
  const hs = [land.height(x, z)];
  const [w, d] = b.size || [4, 4];
  if (b.shape !== "wall_ring") for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) hs.push(land.height(x + sx * w / 2, z + sz * d / 2));
  const y = b.shape === "wall_ring" ? 0 : Math.max(...hs) * 0.6 + hs[0] * 0.4;
  g.position.copy(V(x, z, y));
  g.rotation.y = (b.rot || 0) * Math.PI / 180 + (b.shape === "wall_ring" ? 0 : (R() - 0.5) * 0.04);
  if (b.quality === "shoddy" && b.state === "standing") g.rotation.z = 0.035;   // it leans
  if (b.shape === "wall_ring") {                                                // posts follow the ground
    g.traverse((o) => {
      if (!o.isInstancedMesh) return;
      const m = new THREE.Matrix4(), p = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
      for (let i = 0; i < o.count; i++) { o.getMatrixAt(i, m); m.decompose(p, q, s); p.y = land.height(x + p.x, z - p.z) - 0.3; m.compose(p, q, s); o.setMatrixAt(i, m); }
      o.instanceMatrix.needsUpdate = true;
    });
    g.position.copy(V(x, z, 0));
  }
  const tip = `<strong>${esc(b.name)}</strong>${b.owner ? ` <span class="muted">(built by @${esc(b.owner)})</span>` : ""}<br>` + (b.state === "scaffold" ? `being built - ${Math.round((b.progress || 0) * 100)}%`
    : b.state === "ruin" ? "collapsed" : [b.shape, b.capacity ? `room for ${b.capacity}` : null, b.quality].filter(Boolean).join(", "))
    + (b.residents && b.residents.length ? `<br>${b.residents.length} living here` : "") + (b.look ? `<br><span class="muted">${esc(b.look)}</span>` : "");
  g.traverse((o) => { o.userData.tip = tip; o.userData.building = b; });
  return g;
}

function at(o, x, y, z) { o.position.set(x, y, z); return o; }

export function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// tents (A-frames) and the camp's fires
export function tentsMesh(tents, land, ctx) {
  const g = new THREE.Group();
  if (!tents.length) return g;
  const shape = new THREE.Shape([new THREE.Vector2(-1.1, 0), new THREE.Vector2(1.1, 0), new THREE.Vector2(0, 1.5)]);
  const geo = new THREE.ExtrudeGeometry(shape, { depth: 2.2, bevelEnabled: false }).translate(0, 0, -1.1);
  const im = new THREE.InstancedMesh(geo, M(0xffffff, "canvas"), tents.length);
  const o = new THREE.Object3D(), col = new THREE.Color();
  tents.forEach(([x, z], i) => {
    const R = rng(i + 9);
    o.position.copy(V(x, z, land.height(x, z) - 0.05)); o.rotation.set(0, (R() - 0.5) * 0.4, (R() - 0.5) * 0.05); o.scale.setScalar(0.9 + R() * 0.2); o.updateMatrix();
    im.setMatrixAt(i, o.matrix);
    im.setColorAt(i, col.setHex([0xe0d5b8, 0xd2c39c, 0xc9b28a, 0xb8a888, 0xd7cdb8][i % 5]));
  });
  im.castShadow = true; im.receiveShadow = true; g.add(im);
  for (let i = 0; i < tents.length; i += 10) {
    const [x, z] = tents[i];
    const fx = x + 1.6, fz = z - 2.2;
    const ring = mesh(new THREE.TorusGeometry(0.45, 0.13, 5, 10).rotateX(Math.PI / 2), M(C.stone));
    ring.position.copy(V(fx, fz, land.height(fx, fz) + 0.05)); g.add(ring);
    ctx.fires.push({ obj: ring, camp: true });
  }
  return g;
}

// the stores as heaps: a log stack, a stone heap, clay, thatch bundles, food sacks and crates, iron
export function pilesMesh(piles, land) {
  const g = new THREE.Group();
  for (const p of piles) {
    const R = rng(hash(p.material));
    const n = Math.min(24, Math.max(1, Math.ceil(Math.log2(p.amount + 1) * 2.6)));
    const [x, z] = p.pos, y = land.height(x, z);
    for (let k = 0; k < n; k++) {
      let m;
      if (p.material === "wood") { m = mesh(new THREE.CylinderGeometry(0.2, 0.2, 2.2, 7), M(C.trunk)); m.rotation.z = Math.PI / 2; m.position.set(0, 0.2 + Math.floor(k / 5) * 0.36, (k % 5 - 2) * 0.42 + (Math.floor(k / 5) % 2) * 0.2); }
      else if (p.material === "stone") { m = mesh(new THREE.DodecahedronGeometry(0.28 + R() * 0.12, 0), M(C.stone, null, { flatShading: true })); m.position.set((R() - 0.5) * 1.4, 0.2 + R() * 0.6 * (k / n), (R() - 0.5) * 1.4); }
      else if (p.material === "clay") { m = mesh(new THREE.SphereGeometry(0.4, 8, 6), M(C.clay)); m.scale.y = 0.6; m.position.set((R() - 0.5) * 1.2, 0.15 + (k / n) * 0.4, (R() - 0.5) * 1.2); }
      else if (p.material === "thatch") { m = mesh(new THREE.CylinderGeometry(0.2, 0.25, 1.2, 8), M(0xffffff, "thatch")); m.rotation.x = Math.PI / 2; m.position.set((k % 4 - 1.5) * 0.45, 0.22 + Math.floor(k / 4) * 0.4, 0); }
      else if (p.material === "rope") { m = mesh(new THREE.TorusGeometry(0.28, 0.1, 6, 12), M(0xb8995e)); m.rotation.x = Math.PI / 2; m.position.set(0, 0.1 + k * 0.18, 0); }
      else if (p.material === "food") { m = k % 3 ? mesh(new THREE.CylinderGeometry(0.28, 0.32, 0.6, 8), M(0xc9b083, "canvas")) : mesh(box(0.6, 0.5, 0.6), M(C.plank, "plank")); m.position.set((k % 4 - 1.5) * 0.65, 0.3 + Math.floor(k / 8) * 0.55, (Math.floor(k / 4) % 2) * 0.7); }
      else { m = mesh(box(0.8, 0.12, 0.2), M(C.iron, null, { metalness: 0.6 })); m.position.set(0, 0.06 + k * 0.13, 0); }
      g.add(m);
    }
    g.children.slice(-n).forEach((m) => m.position.add(V(x, z, y)));
    g.children.slice(-n).forEach((m) => { m.userData.tip = `<strong>${p.amount} ${p.material}</strong> in the stores`; });
  }
  return g;
}

export function cartMesh(pos, land) {
  const g = new THREE.Group();
  const bed = mesh(box(2.4, 0.5, 1.5), M(C.plank, "plank")); bed.position.y = 0.9; g.add(bed);
  for (const s of [-1, 1]) { const wh = mesh(new THREE.CylinderGeometry(0.55, 0.55, 0.12, 12), M(C.plankDark)); wh.rotation.x = Math.PI / 2; wh.position.set(-0.4, 0.55, s * 0.8); g.add(wh); }
  const canopy = mesh(new THREE.CylinderGeometry(0.9, 0.9, 2.4, 12, 1, true, 0, Math.PI), M(0x9a3a3a, "canvas", { side: THREE.DoubleSide })); canopy.rotation.z = Math.PI / 2; canopy.position.y = 1.2; g.add(canopy);
  for (let k = 0; k < 4; k++) { const c = mesh(box(0.4, 0.35, 0.4), M(C.plank, "plank")); c.position.set(-0.8 + k * 0.5, 1.3, 0); g.add(c); }
  g.position.copy(V(pos[0], pos[1], land.height(pos[0], pos[1])));
  g.traverse((o) => { o.userData.tip = "<strong>The peddler's cart</strong>"; });
  return g;
}
