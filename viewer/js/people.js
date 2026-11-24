// People are pips: little faceted gumdrops in their role's colours, with dot eyes, floating hands and stubby feet.
// Hats and tools say who they are and what they're doing. (?people=kit brings back the KayKit humans.)
import * as THREE from "three";

import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { C, M, mesh } from "./materials.js";
import { hash } from "./noise.js";

const SKIN = [0xf2d3b3, 0xe8bf98, 0xd09f74, 0xb07a50, 0x8d5a36, 0x6a4128];
const HAIR = [0x2a1d14, 0x4a2f1c, 0x7a4f2a, 0xb98a4e, 0x3b3b3b, 0xd8c9a8];
// role -> [outfit, accent, hat]
const ROLE = [
  [/king|aldric/, 0x2c4f8f, 0xe2b448, "crown"], [/smith|forge/, 0x5a4636, 0x2d2a28, "apron"],
  [/guard|soldier|warrior|mercenar|sellsword|knight|squire|captain/, 0x8a3a32, 0x9a9ea3, "helmet"],
  [/archer|scout|hunter|ranger|trapper/, 0x4c6b3a, 0x6b4a2c, "hood"], [/thief|pickpocket|burglar|cutpurse|spy|assassin|smuggler/, 0x2f3033, 0x45474b, "hood"],
  [/priest|monk|nun|friar|cleric/, 0x6b5b4a, 0xd9d0bf, "hood"], [/healer|herbal|physician|doctor|barber|alchemist|witch/, 0xe6e1d3, 0x6b8f5a, "cap"],
  [/farmer|farmhand|shepherd|peasant/, 0x8a7a4c, 0x5e4a2a, "straw"], [/fisher|sailor|pirate/, 0x3c5f78, 0xd9cfb6, "cap"],
  [/miner|mason|quarry/, 0x6d6a63, 0x3d3b38, "cap"], [/woodcutter|lumberjack|carpenter/, 0x7a3f2a, 0x3d6b3a, "cap"],
  [/baker|cook|chef|miller|innkeeper|brewer|bartender|barmaid/, 0xe9e4d8, 0x9a6a3a, "cap"], [/bard|minstrel|jester|juggler/, 0x8a3a8a, 0xe2b448, "jester"],
  [/merchant|shopkeeper|trader|peddler|jeweler/, 0x6a3a5a, 0xc29a4a, "cap"], [/tailor/, 0x4a6a8a, 0xd8c2a0, "cap"],
  [/beggar|homeless|vagrant|drifter|urchin|hermit/, 0x7a6a55, 0x5a4a38, "none"], [/steward/, 0x3a3a5a, 0xc0a060, "cap"],
  [/scholar|scribe|wizard|mage|sorcerer|teacher|librarian/, 0x3d3a6b, 0xb8a0e0, "pointy"],
];
export function look(role, handle) {
  const r = String(role || "").toLowerCase();
  const hit = ROLE.find(([re]) => re.test(r)) || [null, 0x7d6a52, 0x4b3a2a, "none"];
  const h = hash(handle || role);
  // a pip's body is their outfit colour, a shade lighter or darker each, so a crowd of farmers isn't one colour
  const base = new THREE.Color(hit[1]), hsl = {}; base.getHSL(hsl);
  const tint = new THREE.Color().setHSL(hsl.h + ((h >>> 7) % 21 - 10) / 400, Math.min(0.75, hsl.s * 1.25 + 0.08),
    Math.min(0.78, Math.max(0.42, hsl.l * 0.7 + 0.24 + ((h >>> 12) % 13 - 6) / 100))).getHex();
  return { outfit: hit[1], accent: hit[2], hat: hit[3], tint, size: 0.92 + ((h >>> 17) % 17) / 100,
           skin: SKIN[h % SKIN.length], hair: HAIR[(h >>> 3) % HAIR.length] };
}

// Pips: little faceted gumdrops. No head, no neck, no legs - a round body with two dot eyes, floating nub hands,
// stubby feet, and a hat that says what they do. They hop when they walk and squash when they land.
const PIP = 1.3;                                   // how tall a pip's body is (the hat sits on top)
const SEG = 7;
let BODY_GEO = null, EYES_GEO = null, HAND_GEO = null, FOOT_GEO = null, HAT_GEO = null, STRAW_GEO = null,
  POINTY_GEO = null, TUFT_GEO = null;
function geos() {
  if (BODY_GEO) return;
  const prof = [[0, 0], [0.34, 0.01], [0.45, 0.13], [0.48, 0.36], [0.44, 0.6], [0.34, 0.82], [0.18, 0.96], [0, 1.0]];
  BODY_GEO = new THREE.LatheGeometry(prof.map(([r, y]) => new THREE.Vector2(r * PIP, y * PIP)), SEG);
  // eyes: two tall black beads sitting proud of the front face (the body's front is a flat facet)
  const eye = (x) => new THREE.SphereGeometry(0.075, 6, 4).scale(0.85, 1.35, 0.5).translate(x, 0.64 * PIP, -0.405 * PIP);
  EYES_GEO = mergeGeometries([eye(-0.15), eye(0.15)]);
  HAND_GEO = new THREE.IcosahedronGeometry(0.115, 0);
  FOOT_GEO = new THREE.DodecahedronGeometry(0.13, 0).scale(1, 0.55, 1.3);
  HAT_GEO = new THREE.SphereGeometry(0.4, SEG, 2, 0, Math.PI * 2, 0, Math.PI * 0.42).translate(0, -0.02, 0);
  STRAW_GEO = new THREE.ConeGeometry(0.66, 0.3, 8).translate(0, 0.12, 0);
  POINTY_GEO = mergeGeometries([new THREE.ConeGeometry(0.27, 0.72, 5).translate(0, 0.36, 0), new THREE.CylinderGeometry(0.5, 0.5, 0.04, 8)]);
  TUFT_GEO = mergeGeometries([0, 1, 2].map((k) => new THREE.ConeGeometry(0.05, 0.24, 4).rotateZ((k - 1) * 0.5).translate((k - 1) * 0.07, 0.1, 0)));
}
const TOP = 0.86 * PIP;                            // where a hat sits
const solid = (geo, mat) => mesh(geo, mat, { cast: true, receive: false });
const shade = (hex, k) => new THREE.Color(hex).multiplyScalar(k).getHex();

function hatMesh(kind, L) {
  const g = new THREE.Group();
  const metal = (c) => M(c, null, { metalness: 0.5, roughness: 0.45 });
  if (kind === "crown") {
    g.add(solid(new THREE.CylinderGeometry(0.27, 0.3, 0.16, 6, 1, true), M(C.gold, null, { metalness: 0.6, roughness: 0.35, side: THREE.DoubleSide })));
    for (let k = 0; k < 5; k++) { const p = solid(new THREE.ConeGeometry(0.07, 0.18, 4), metal(C.gold)); const a = k / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.27, 0.15, Math.sin(a) * 0.27); g.add(p); }
    g.position.y = 0.14;
  } else if (kind === "battered") {
    const top = solid(new THREE.CylinderGeometry(0.22, 0.27, 0.26, 6), M(0x5a4532)); top.position.set(0.02, 0.13, 0);
    g.add(solid(new THREE.CylinderGeometry(0.46, 0.48, 0.05, 7), M(0x5a4532)), top);
    g.position.y = 0.1; g.rotation.z = 0.12;
  } else if (kind === "helmet") {
    g.add(solid(HAT_GEO, metal(L.accent)));
    const nose = solid(new THREE.BoxGeometry(0.06, 0.22, 0.06), metal(L.accent)); nose.position.set(0, -0.05, -0.39); g.add(nose);
  } else if (kind === "hood") {
    g.add(solid(new THREE.SphereGeometry(0.46, SEG, 3, 0, Math.PI * 2, 0, Math.PI * 0.5), M(shade(L.outfit, 0.8))));
    const tip = solid(new THREE.ConeGeometry(0.15, 0.32, 4), M(shade(L.outfit, 0.8))); tip.position.set(0, 0.22, 0.3); tip.rotation.x = 1.2; g.add(tip);
    g.position.y = -0.08; g.rotation.x = -0.15;
  } else if (kind === "straw") {
    g.add(solid(STRAW_GEO, M(C.thatch)));
  } else if (kind === "cap") {
    g.add(solid(HAT_GEO, M(L.accent)));
  } else if (kind === "jester") {
    for (const s of [-1, 1]) { const c = solid(new THREE.ConeGeometry(0.1, 0.48, 4), M(s < 0 ? L.outfit : L.accent)); c.position.set(s * 0.22, 0.26, 0); c.rotation.z = -s * 0.7; g.add(c); const b = solid(new THREE.OctahedronGeometry(0.07, 0), M(C.gold)); b.position.set(s * 0.4, 0.43, 0); g.add(b); }
    g.add(solid(HAT_GEO, M(L.accent)));
  } else if (kind === "pointy") {
    g.add(solid(POINTY_GEO, M(L.accent)));
    g.rotation.z = 0.12;
  } else {
    g.add(solid(TUFT_GEO, M(L.hair))); g.position.y = 0.2;
  }
  return g;
}

// tools held in the right hand, by animation
function tool(kind) {
  const g = new THREE.Group();
  const handle = (len) => mesh(new THREE.CylinderGeometry(0.045, 0.045, len, 4).translate(0, len / 2 - 0.1, 0), M(C.trunk));
  if (kind === "chop") { g.add(handle(0.9)); const b = mesh(new THREE.BoxGeometry(0.28, 0.2, 0.05), M(C.iron, null, { metalness: 0.6 })); b.position.set(0.12, 0.7, 0); g.add(b); }
  else if (kind === "mine") { g.add(handle(0.9)); const b = mesh(new THREE.BoxGeometry(0.6, 0.07, 0.07), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.75; b.rotation.z = 0.15; g.add(b); }
  else if (kind === "dig") { g.add(handle(1.0)); const b = mesh(new THREE.BoxGeometry(0.22, 0.3, 0.04), M(C.iron, null, { metalness: 0.6 })); b.position.y = -0.15; g.add(b); }
  else if (kind === "hammer") { g.add(handle(0.5)); const b = mesh(new THREE.BoxGeometry(0.2, 0.1, 0.1), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.38; g.add(b); }
  else if (kind === "cut") { g.add(handle(0.3)); const b = mesh(new THREE.TorusGeometry(0.2, 0.03, 3, 6, Math.PI), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.35; g.add(b); }
  else if (kind === "fish") { const r = mesh(new THREE.CylinderGeometry(0.02, 0.03, 2.2, 4).translate(0, 1.0, 0), M(C.trunk)); r.rotation.x = -0.7; g.add(r); }
  else if (kind === "judge" || kind === "read") { const s = mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.34, 5), M(0xe9dfc4)); s.rotation.z = Math.PI / 2; g.add(s); }
  else if (kind === "eat") { const b = mesh(new THREE.CylinderGeometry(0.15, 0.09, 0.1, 6), M(0x7a5a3a)); g.add(b); }
  else if (kind === "forage" || kind === "twist") { const b = mesh(new THREE.CylinderGeometry(0.16, 0.12, 0.22, 6), M(0x9a7a4a)); b.position.y = -0.1; g.add(b); }
  return g;
}

export class Person {
  constructor({ role, handle, name, king = false, crowned = false }) {
    geos();
    this.L = look(king ? "king" : role, handle);
    const h = hash(handle || name || role || "pip");
    this.root = new THREE.Group();
    this.pivot = new THREE.Group(); this.root.add(this.pivot);
    this.body = new THREE.Group(); this.pivot.add(this.body);           // what squashes and leans
    const tint = this.L.tint;
    this.body.add(solid(BODY_GEO, M(tint)));
    const belt = solid(new THREE.CylinderGeometry(0.485 * PIP, 0.475 * PIP, 0.09, SEG), M(this.L.accent)); belt.position.y = 0.3 * PIP;
    this.eyes = mesh(EYES_GEO, M(0x1b1712), { cast: false }); this.body.add(belt, this.eyes);
    if (king) {                                    // a big moustache, the one thing he's proud of
      for (const s of [-1, 1]) {
        const m = solid(new THREE.SphereGeometry(0.1, 6, 3).scale(1.9, 0.6, 0.6), M(0x6b4a30));
        m.rotation.z = s * -0.35; m.position.set(s * 0.15, 0.5 * PIP, -0.4 * PIP); this.body.add(m);
      }
    }
    const hat = hatMesh(king ? (crowned ? "crown" : "battered") : this.L.hat, this.L); hat.position.y += TOP; this.body.add(hat);
    const handMat = M(shade(tint, 0.82));
    this.handR = solid(HAND_GEO, handMat); this.handL = solid(HAND_GEO, handMat);
    this.legL = solid(FOOT_GEO, M(0x3d3129)); this.legR = solid(FOOT_GEO, M(0x3d3129));
    this.pivot.add(this.handR, this.handL, this.legL, this.legR);
    this.tools = {}; this.toolKind = null;
    this.blink = 2 + (h % 50) / 10;
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.5, 8).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x1a2a40, transparent: true, opacity: 0.25, depthWrite: false }));
    shadow.position.y = 0.03; this.root.add(shadow); this.shadow = shadow;
    this.size = this.L.size * (king ? 1.15 : 1);
    this.root.scale.setScalar(this.size);
    this.root.userData = { person: this, tip: name ? `<strong>${name}</strong>` : "" };
    this.root.traverse((o) => { o.userData.tip = this.root.userData.tip; o.userData.person = this; });
  }

  hold(kind) {
    if (kind === this.toolKind) return;
    if (this.toolKind && this.tools[this.toolKind]) this.tools[this.toolKind].visible = false;
    this.toolKind = kind;
    if (!kind) return;
    if (!this.tools[kind]) { this.tools[kind] = tool(kind); this.tools[kind].scale.setScalar(0.8); this.handR.add(this.tools[kind]); }
    this.tools[kind].visible = true;
  }

  // anim: walk, run, chop, mine, dig, hammer, cut, forage, twist, fish, eat, sleep, sit, read, craft, cook,
  // talk, speak, judge, sing, trade, think, pray, dance, idle
  pose(anim, t, heading = null) {
    const P = this.pivot, B = this.body, R = this.handR.position, Lh = this.handL.position;
    P.position.set(0, 0, 0); P.rotation.set(0, 0, 0); B.scale.set(1, 1, 1); B.rotation.set(0, 0, 0); B.position.set(0, 0, 0);
    R.set(0.76, 0.36, -0.12); Lh.set(-0.76, 0.36, -0.12); this.handR.rotation.set(0, 0, 0);
    this.legL.position.set(-0.17, 0.05, -0.04); this.legR.position.set(0.17, 0.05, -0.04);
    this.shadow.visible = true;
    if (heading !== null) this.root.rotation.y = heading;
    const blink = (t % this.blink) < 0.12;
    this.eyes.scale.set(1, blink ? 0.15 : 1, 1);
    const s = Math.sin(t * 9), c = Math.cos(t * 9);
    this.hold(["chop", "mine", "dig", "hammer", "cut", "fish", "judge", "read", "eat", "forage", "twist"].includes(anim) ? anim : null);
    switch (anim) {
      case "walk": case "run": {                   // a hop: up, land, squash
        const k = anim === "run" ? 1.6 : 1, ph = t * 7 * k, up = Math.abs(Math.sin(ph));
        P.position.y = up * 0.22 * k;
        const land = 1 - up;
        B.scale.set(1 + land * 0.1, 1 - land * 0.12 + up * 0.05, 1 + land * 0.1);
        B.rotation.x = -0.1 * k; P.rotation.z = Math.sin(ph) * 0.05;
        this.legL.position.z = -0.04 + Math.sin(ph) * 0.12; this.legR.position.z = -0.04 - Math.sin(ph) * 0.12;
        R.set(0.74, 0.38 + up * 0.15, -0.1 - Math.cos(ph) * 0.2); Lh.set(-0.74, 0.38 + up * 0.15, -0.1 + Math.cos(ph) * 0.2); break;
      }
      case "chop": case "mine": case "hammer": {
        const sw = (Math.sin(t * 4.5) + 1) / 2;
        R.set(0.35, 0.55 + sw * 0.7, -0.45); this.handR.rotation.x = -0.3 - sw * 1.8; Lh.set(0.05, 0.5 + sw * 0.5, -0.5);
        B.rotation.x = -0.12 * (1 - sw); B.scale.set(1 + (1 - sw) * 0.06, 1 - (1 - sw) * 0.08, 1 + (1 - sw) * 0.06); break;
      }
      case "dig": case "cut": { const sw = (Math.sin(t * 4) + 1) / 2; B.rotation.x = -0.3 * sw; R.set(0.3, 0.3, -0.55 - sw * 0.2); this.handR.rotation.x = -1.2; Lh.set(0.02, 0.4, -0.5); break; }
      case "forage": case "twist": B.rotation.x = -0.4 - Math.abs(s) * 0.08; R.set(0.32, 0.12 + Math.abs(s) * 0.15, -0.55); Lh.set(-0.3, 0.15, -0.5); break;
      case "fish": R.set(0.32, 0.6, -0.5); Lh.set(0.02, 0.55, -0.5); B.scale.y = 1 + Math.sin(t) * 0.02; break;
      case "sleep": B.rotation.x = -Math.PI / 2; B.position.set(0, 0.45, 0.6); this.eyes.scale.y = 0.15; R.set(0.45, 0.4, 0.3); Lh.set(-0.45, 0.4, 0.3); this.shadow.visible = false;
        B.scale.set(1 + Math.sin(t * 1.5) * 0.03, 1, 1 + Math.sin(t * 1.5) * 0.03); break;
      case "sit": case "read": case "craft": case "cook": case "eat":
        P.position.y = -0.12; B.scale.set(1.08, 0.9, 1.08); this.legL.position.z = this.legR.position.z = -0.42; this.legL.position.y = this.legR.position.y = 0.12;
        R.set(0.36, 0.45 + (anim === "eat" ? Math.max(0, s) * 0.35 : 0), -0.5); Lh.set(-0.36, 0.42, -0.5); B.rotation.x = 0.1; break;
      case "talk": case "speak": case "sing": case "trade":
        R.set(0.55, 0.6 + Math.max(0, s) * 0.35, -0.3); B.rotation.y = Math.sin(t * 1.3) * 0.2; B.scale.y = 1 + Math.abs(c) * 0.04; break;
      case "judge": R.set(0.5, 0.75, -0.4); B.rotation.x = 0.05; break;
      case "think": R.set(0.3, 0.75, -0.48); B.rotation.z = 0.12; break;
      case "pray": R.set(0.08, 0.6, -0.5); Lh.set(-0.08, 0.6, -0.5); B.rotation.x = 0.25; break;
      case "dance": P.rotation.y = Math.sin(t * 2) * 0.6; P.position.y = Math.abs(s) * 0.18; B.scale.set(1 - Math.abs(s) * 0.05, 1 + Math.abs(s) * 0.08, 1 - Math.abs(s) * 0.05); R.y = 1.0; Lh.y = 1.0; break;
      default: B.scale.y = 1 + Math.sin(t * 1.6) * 0.02; B.rotation.y = Math.sin(t * 0.4) * 0.2;
    }
  }
}

// everyone else: instanced pips (hundreds of them for a handful of draw calls)
const HATS = { cap: "dome", helmet: "dome", hood: "dome", jester: "dome", straw: "straw", pointy: "pointy", none: "tuft", apron: "tuft" };
export class Crowd {
  constructor(scene, max = 600) {
    geos();
    this.max = max;
    const flat = (c) => new THREE.MeshStandardMaterial({ color: c ?? 0xffffff, roughness: 1, flatShading: true });
    const im = (geo, mat, n) => { const m = new THREE.InstancedMesh(geo, mat, n); m.castShadow = true; m.frustumCulled = false; m.count = 0; return m; };
    this.body = im(BODY_GEO, flat(), max);
    this.eyes = im(EYES_GEO, flat(0x1b1712), max); this.eyes.castShadow = false;
    this.hats = { dome: im(HAT_GEO, flat(), max), straw: im(STRAW_GEO, flat(C.thatch), max), pointy: im(POINTY_GEO, flat(), max), tuft: im(TUFT_GEO, flat(), max) };
    this.hands = im(HAND_GEO, flat(), max * 2);
    this.feet = im(FOOT_GEO, flat(0x3d3129), max * 2);
    this.group = new THREE.Group(); this.group.add(this.body, this.eyes, this.hands, this.feet, ...Object.values(this.hats));
    scene.add(this.group);
    this.people = []; this.looks = [];
    this.o = new THREE.Object3D(); this.o.rotation.order = "YXZ";    // turn to face, then lean forward
    this.m = new THREE.Matrix4(); this.l = new THREE.Matrix4(); this.q = new THREE.Matrix4();
    this.col = new THREE.Color();
  }

  set(people) {   // [{role, handle, home:[x,z], work:[x,z]}]
    this.people = people.slice(0, this.max);
    this.looks = this.people.map((p) => look(p.role, p.handle));
    const col = this.col;
    this.looks.forEach((L, i) => {
      this.body.setColorAt(i, col.setHex(L.tint));
      this.hands.setColorAt(i * 2, col.setHex(shade(L.tint, 0.82))); this.hands.setColorAt(i * 2 + 1, col);
    });
    for (const m of [this.body, this.hands]) if (m.instanceColor) m.instanceColor.needsUpdate = true;
  }

  // positions: [{x, y, z, heading, bob, lean, stride, lie, sit, walkPose, work, hidden}]
  update(states) {
    const o = this.o, m = this.m, l = this.l, q = this.q, col = this.col, t = performance.now() / 1000;
    const n = { body: 0, hands: 0, feet: 0, dome: 0, straw: 0, pointy: 0, tuft: 0 };
    const put = (im, key, mat) => { im.setMatrixAt(n[key]++, mat); };
    states.forEach((s, i) => {
      if (i >= this.people.length || s.hidden) return;
      const L = this.looks[i], j = this.people[i].j || i, size = L.size;
      // hop when walking, squash on landing, a swing or a stoop at work
      const ph = t * 7 + j, up = s.walkPose ? Math.abs(Math.sin(ph)) : 0, land = s.walkPose ? 1 - up : 0;
      const sw = s.work === "swing" ? (Math.sin(t * 4.5 + j) + 1) / 2 : 0;
      const sx = 1 + land * 0.1 + (s.sit ? 0.08 : 0), sy = 1 - land * 0.12 + up * 0.05 - (s.sit ? 0.1 : 0);
      o.position.set(s.x, s.y + (s.lie ? 0.45 : up * 0.22 * size) + (s.sit ? 0.18 : 0), s.z);
      o.rotation.set(s.lie ? -Math.PI / 2 : s.walkPose ? -0.1 : s.work === "stoop" ? -0.35 : s.work === "swing" ? -0.1 * (1 - sw) : 0, s.heading, 0, "YXZ");
      o.scale.set(size, size, size); o.updateMatrix();
      m.copy(o.matrix);
      const body = l.makeScale(sx, sy, sx).premultiply(m);
      // body, eyes, hat all ride the squashed body
      this.body.setColorAt(n.body, col.setHex(L.tint));
      this.eyes.setMatrixAt(n.body, (s.lie || (t + j) % (2 + (j % 5) / 2) < 0.12) ? q.makeScale(0, 0, 0) : body);
      this.body.setMatrixAt(n.body++, body);
      const hk = HATS[L.hat] || "tuft", hat = this.hats[hk];
      hat.setColorAt(n[hk], col.setHex(L.hat === "none" || L.hat === "apron" ? L.hair : L.accent));
      put(hat, hk, q.makeTranslation(0, TOP + (hk === "tuft" ? 0.2 : 0), 0).premultiply(body));
      // hands: at the sides; up and down with a swing; low for a stoop; swinging along on a walk
      const hy = s.work === "swing" ? 0.55 + sw * 0.7 : s.work === "stoop" ? 0.15 : 0.36 + up * 0.15;
      const hz = s.work ? -0.45 : -0.1 - (s.walkPose ? Math.cos(ph) * 0.2 : 0);
      const hx = s.work === "swing" ? 0.35 : 0.74;
      this.hands.setMatrixAt(n.hands++, l.makeTranslation(hx, hy, hz).premultiply(m));
      this.hands.setMatrixAt(n.hands++, l.makeTranslation(s.work === "swing" ? 0.05 : -0.74, hy, s.work ? -0.5 : -0.1 + (s.walkPose ? Math.cos(ph) * 0.2 : 0)).premultiply(m));
      // feet: stepping on a walk, tucked forward when sitting
      const st = s.walkPose ? Math.sin(ph) * 0.12 : 0, fz = s.sit ? -0.42 : -0.04;
      for (const [fx, d] of [[-0.17, st], [0.17, -st]]) this.feet.setMatrixAt(n.feet++, l.makeTranslation(fx, s.sit ? 0.12 : 0.05 - up * 0.22, fz + d).premultiply(m));
    });
    this.body.count = this.eyes.count = n.body; this.hands.count = n.hands; this.feet.count = n.feet;
    for (const k of Object.keys(this.hats)) this.hats[k].count = n[k];
    for (const im of [this.body, this.eyes, this.hands, this.feet, ...Object.values(this.hats)]) {
      im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
    }
  }
}

export function makePerson(opts) { return new Person(opts); }
