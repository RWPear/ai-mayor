// People, Prison Architect style in 3D: a chunky egg of a body in a role's colours, a big round head, little
// floating hands, no legs, a dark outline. Hats and tools say who they are and what they're doing.
import * as THREE from "three";
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
  return { outfit: hit[1], accent: hit[2], hat: hit[3], skin: SKIN[h % SKIN.length], hair: HAIR[(h >>> 3) % HAIR.length] };
}

const OUTLINE = new THREE.MeshBasicMaterial({ color: 0x1b140f, side: THREE.BackSide });
let BODY_GEO = null, HEAD_GEO = null, HAND_GEO = null;
function geos() {
  if (BODY_GEO) return;
  const pts = [];
  for (let i = 0; i <= 12; i++) {                          // an egg, wider at the bottom
    const t = i / 12, y = t * 1.25, r = 0.5 * Math.sin(Math.PI * Math.min(1, t * 1.05 + 0.02)) * (1.08 - t * 0.35);
    pts.push(new THREE.Vector2(Math.max(0.02, r), y));
  }
  BODY_GEO = new THREE.LatheGeometry(pts, 16);
  HEAD_GEO = new THREE.SphereGeometry(0.36, 16, 12);
  HAND_GEO = new THREE.SphereGeometry(0.11, 8, 6);
}
function outlined(geo, mat, scale = 1.07) {
  const g = new THREE.Group();
  const m = mesh(geo, mat, { cast: true, receive: false });
  const o = new THREE.Mesh(geo, OUTLINE); o.scale.setScalar(scale);
  g.add(o, m); g.userData.inner = m;
  return g;
}

function hatMesh(kind, L) {
  const g = new THREE.Group();
  if (kind === "crown") {
    const band = mesh(new THREE.CylinderGeometry(0.27, 0.3, 0.16, 10, 1, true), M(C.gold, null, { metalness: 0.7, roughness: 0.3, side: THREE.DoubleSide }));
    g.add(band);
    for (let k = 0; k < 5; k++) { const p = mesh(new THREE.ConeGeometry(0.06, 0.16, 4), M(C.gold, null, { metalness: 0.7, roughness: 0.3 })); const a = k / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.27, 0.14, Math.sin(a) * 0.27); g.add(p); }
    g.position.y = 0.3;
  } else if (kind === "battered") {
    const crown = mesh(new THREE.CylinderGeometry(0.24, 0.28, 0.24, 10), M(0x4a3a2a)); crown.position.set(0.02, 0.12, 0);
    g.add(mesh(new THREE.CylinderGeometry(0.42, 0.44, 0.04, 12), M(0x4a3a2a)), crown);
    g.position.y = 0.27; g.rotation.z = 0.12;
  } else if (kind === "helmet") {
    g.add(mesh(new THREE.SphereGeometry(0.39, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2), M(L.accent, null, { metalness: 0.6, roughness: 0.35 })));
    g.position.y = 0.04;
  } else if (kind === "hood") {
    g.add(mesh(new THREE.SphereGeometry(0.41, 12, 10, 0, Math.PI * 2, 0, Math.PI * 0.62), M(L.outfit)));
    g.position.y = -0.02; g.rotation.x = -0.25;
  } else if (kind === "straw") {
    g.add(mesh(new THREE.ConeGeometry(0.62, 0.32, 14), M(C.thatch)));
    g.position.y = 0.32;
  } else if (kind === "cap") {
    g.add(mesh(new THREE.SphereGeometry(0.37, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.4), M(L.accent)));
    g.position.y = 0.06;
  } else if (kind === "jester") {
    for (const s of [-1, 1]) { const c = mesh(new THREE.ConeGeometry(0.1, 0.5, 6), M(s < 0 ? L.outfit : L.accent)); c.position.set(s * 0.22, 0.38, 0); c.rotation.z = -s * 0.7; g.add(c); }
    g.add(mesh(new THREE.SphereGeometry(0.37, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.4), M(L.outfit)));
  } else if (kind === "pointy") {
    const c = mesh(new THREE.ConeGeometry(0.3, 0.75, 10), M(L.outfit)); c.position.y = 0.45; c.rotation.z = 0.15;
    g.add(c, mesh(new THREE.CylinderGeometry(0.5, 0.5, 0.03, 14), M(L.outfit)));
    g.position.y = 0.12;
  } else if (kind === "none") {
    const hair = mesh(new THREE.SphereGeometry(0.37, 12, 8, 0, Math.PI * 2, 0, Math.PI * 0.45), M(L.hair));
    g.add(hair); g.position.y = 0.02;
  }
  return g;
}

// tools held in the right hand, by animation
function tool(kind) {
  const g = new THREE.Group();
  const handle = (len) => mesh(new THREE.CylinderGeometry(0.04, 0.04, len, 6).translate(0, len / 2 - 0.1, 0), M(C.trunk));
  if (kind === "chop") { g.add(handle(0.9)); const b = mesh(new THREE.BoxGeometry(0.28, 0.2, 0.05), M(C.iron, null, { metalness: 0.6 })); b.position.set(0.12, 0.7, 0); g.add(b); }
  else if (kind === "mine") { g.add(handle(0.9)); const b = mesh(new THREE.BoxGeometry(0.6, 0.07, 0.07), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.75; b.rotation.z = 0.15; g.add(b); }
  else if (kind === "dig") { g.add(handle(1.0)); const b = mesh(new THREE.BoxGeometry(0.22, 0.3, 0.04), M(C.iron, null, { metalness: 0.6 })); b.position.y = -0.15; g.add(b); }
  else if (kind === "hammer") { g.add(handle(0.5)); const b = mesh(new THREE.BoxGeometry(0.2, 0.1, 0.1), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.38; g.add(b); }
  else if (kind === "cut") { g.add(handle(0.3)); const b = mesh(new THREE.TorusGeometry(0.2, 0.025, 4, 12, Math.PI), M(C.iron, null, { metalness: 0.6 })); b.position.y = 0.35; g.add(b); }
  else if (kind === "fish") { const r = mesh(new THREE.CylinderGeometry(0.02, 0.03, 2.2, 5).translate(0, 1.0, 0), M(C.trunk)); r.rotation.x = -0.7; g.add(r); }
  else if (kind === "judge" || kind === "read") { const s = mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.34, 8), M(0xe9dfc4)); s.rotation.z = Math.PI / 2; g.add(s); }
  else if (kind === "eat") { const b = mesh(new THREE.SphereGeometry(0.13, 8, 6, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), M(0x7a5a3a)); g.add(b); }
  else if (kind === "forage" || kind === "twist") { const b = mesh(new THREE.CylinderGeometry(0.16, 0.12, 0.22, 8), M(0x9a7a4a)); b.position.y = -0.1; g.add(b); }
  return g;
}

export class Person {
  constructor({ role, handle, name, king = false, crowned = false }) {
    geos();
    this.L = look(king ? "king" : role, handle);
    this.root = new THREE.Group();
    this.pivot = new THREE.Group(); this.root.add(this.pivot);
    const body = outlined(BODY_GEO, M(this.L.outfit, null, { roughness: 0.85 }));
    body.scale.set(1, 1, 0.9);
    const belt = mesh(new THREE.CylinderGeometry(0.46, 0.47, 0.1, 16), M(this.L.accent)); belt.position.y = 0.55;
    this.head = outlined(HEAD_GEO, M(this.L.skin, null, { roughness: 0.7 }), 1.09); this.head.position.y = 1.45;
    const eyes = new THREE.Group();
    for (const s of [-1, 1]) { const e = mesh(new THREE.SphereGeometry(0.045, 6, 5), M(0x1b140f), { cast: false }); e.position.set(s * 0.12, 0.04, -0.32); eyes.add(e); }
    this.head.add(eyes);
    const hat = hatMesh(king ? (crowned ? "crown" : "battered") : this.L.hat, this.L); this.head.add(hat);
    this.handR = outlined(HAND_GEO, M(this.L.skin), 1.2); this.handL = outlined(HAND_GEO, M(this.L.skin), 1.2);
    this.handR.position.set(0.55, 0.62, -0.05); this.handL.position.set(-0.55, 0.62, -0.05);
    this.tools = {}; this.toolKind = null;
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.55, 16).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.28, depthWrite: false }));
    shadow.position.y = 0.03; this.root.add(shadow); this.shadow = shadow;
    this.pivot.add(body, belt, this.head, this.handR, this.handL);
    this.root.scale.setScalar(king ? 1.08 : 1);
    this.root.userData = { person: this, tip: name ? `<strong>${name}</strong>` : "" };
    this.root.traverse((o) => { o.userData.tip = this.root.userData.tip; o.userData.person = this; });
  }

  hold(kind) {
    if (kind === this.toolKind) return;
    if (this.toolKind && this.tools[this.toolKind]) this.tools[this.toolKind].visible = false;
    this.toolKind = kind;
    if (!kind) return;
    if (!this.tools[kind]) { this.tools[kind] = tool(kind); this.handR.add(this.tools[kind]); }
    this.tools[kind].visible = true;
  }

  // anim: walk, run, chop, mine, dig, hammer, cut, forage, twist, fish, eat, sleep, sit, read, craft, cook,
  // talk, speak, judge, sing, trade, think, pray, dance, idle
  pose(anim, t, heading = null) {
    const P = this.pivot, R = this.handR.position, Lh = this.handL.position;
    P.position.set(0, 0, 0); P.rotation.set(0, 0, 0); this.head.rotation.set(0, 0, 0);
    R.set(0.55, 0.62, -0.05); Lh.set(-0.55, 0.62, -0.05); this.handR.rotation.set(0, 0, 0);
    this.shadow.visible = true;
    if (heading !== null) this.root.rotation.y = heading;
    const s = Math.sin(t * 9), c = Math.cos(t * 9);
    this.hold(["chop", "mine", "dig", "hammer", "cut", "fish", "judge", "read", "eat", "forage", "twist"].includes(anim) ? anim : null);
    switch (anim) {
      case "walk": case "run": {
        const k = anim === "run" ? 1.7 : 1;
        P.position.y = Math.abs(Math.sin(t * 9 * k)) * 0.12; P.rotation.z = Math.sin(t * 9 * k) * 0.06; P.rotation.x = -0.08 * k;
        R.z = -0.05 - s * 0.25; Lh.z = -0.05 + s * 0.25; break;
      }
      case "chop": case "mine": case "hammer": {
        const sw = (Math.sin(t * 4.5) + 1) / 2;
        R.set(0.4, 0.9 + sw * 0.6, -0.35); this.handR.rotation.x = -0.3 - sw * 1.8; Lh.set(0.1, 0.8 + sw * 0.4, -0.4); P.rotation.x = -0.1 * sw; break;
      }
      case "dig": case "cut": { const sw = (Math.sin(t * 4) + 1) / 2; P.rotation.x = -0.35 * sw; R.set(0.35, 0.55, -0.45 - sw * 0.2); this.handR.rotation.x = -1.2; Lh.set(0.05, 0.7, -0.4); break; }
      case "forage": case "twist": P.rotation.x = -0.4 - Math.abs(s) * 0.1; R.set(0.35, 0.35 + Math.abs(s) * 0.2, -0.5); Lh.set(-0.3, 0.4, -0.45); break;
      case "fish": R.set(0.35, 0.8, -0.4); Lh.set(0.05, 0.75, -0.42); P.position.y = Math.sin(t) * 0.02; break;
      case "sleep": P.rotation.x = -Math.PI / 2; P.position.set(0, 0.45, 0.6); this.shadow.visible = false; break;
      case "sit": case "read": case "craft": case "cook": case "eat":
        P.position.y = -0.22; P.scale && (P.scale.y = 1);
        R.set(0.3, 0.75 + (anim === "eat" ? Math.max(0, s) * 0.5 : 0), -0.45); Lh.set(-0.3, 0.72, -0.45); this.head.rotation.x = 0.25; break;
      case "talk": case "speak": case "sing": case "trade":
        R.set(0.5, 0.9 + Math.max(0, s) * 0.35, -0.25); this.head.rotation.y = Math.sin(t * 1.3) * 0.25; P.position.y = Math.abs(c) * 0.02; break;
      case "judge": R.set(0.45, 1.0, -0.35); this.head.rotation.x = -0.1; break;
      case "think": R.set(0.25, 1.25, -0.35); this.head.rotation.x = 0.2; break;
      case "pray": R.set(0.08, 0.95, -0.42); Lh.set(-0.08, 0.95, -0.42); this.head.rotation.x = 0.35; break;
      case "dance": P.rotation.y = t * 3; P.position.y = Math.abs(s) * 0.25; R.y = 1.3; Lh.y = 1.3; break;
      default: P.position.y = Math.sin(t * 1.6) * 0.015; this.head.rotation.y = Math.sin(t * 0.4) * 0.3;
    }
  }
}

// everyone else: instanced bodies, heads and hands (hundreds of people for the price of a few draw calls)
export class Crowd {
  constructor(scene, max = 600) {
    geos();
    this.max = max;
    const bodyMat = new THREE.MeshStandardMaterial({ roughness: 0.85 });
    this.body = new THREE.InstancedMesh(BODY_GEO, bodyMat, max);
    this.outline = new THREE.InstancedMesh(BODY_GEO, OUTLINE, max);
    this.head = new THREE.InstancedMesh(HEAD_GEO, new THREE.MeshStandardMaterial({ roughness: 0.7 }), max);
    this.headOut = new THREE.InstancedMesh(HEAD_GEO, OUTLINE, max);
    this.hat = new THREE.InstancedMesh(new THREE.SphereGeometry(0.37, 10, 6, 0, Math.PI * 2, 0, Math.PI * 0.42), new THREE.MeshStandardMaterial({ roughness: 0.9 }), max);
    for (const m of [this.body, this.head, this.hat]) { m.castShadow = true; }
    this.group = new THREE.Group(); this.group.add(this.outline, this.body, this.headOut, this.head, this.hat);
    scene.add(this.group);
    this.people = [];
    this.o = new THREE.Object3D();
  }

  set(people) {   // [{role, handle, home:[x,z], work:[x,z]}]
    this.people = people.slice(0, this.max);
    const col = new THREE.Color();
    this.people.forEach((p, i) => {
      const L = look(p.role, p.handle);
      this.body.setColorAt(i, col.setHex(L.outfit)); this.head.setColorAt(i, col.setHex(L.skin));
      this.hat.setColorAt(i, col.setHex(L.hat === "none" ? L.hair : L.hat === "straw" ? C.thatch : L.accent));
    });
    for (const m of [this.body, this.head, this.hat]) if (m.instanceColor) m.instanceColor.needsUpdate = true;
    for (const m of [this.body, this.outline, this.head, this.headOut, this.hat]) m.count = this.people.length;
  }

  // positions: [{x, y, z, heading, bob, lie}]
  update(states) {
    const o = this.o;
    states.forEach((s, i) => {
      if (i >= this.people.length) return;
      const hide = s.hidden;
      o.position.set(s.x, s.y + (s.lie ? 0.45 : s.bob), s.z); o.rotation.set(s.lie ? -Math.PI / 2 : s.lean || 0, s.heading, 0);
      o.scale.set(hide ? 0 : 1, hide ? 0 : 1, hide ? 0 : 0.9); o.updateMatrix();
      this.body.setMatrixAt(i, o.matrix);
      o.scale.multiplyScalar(1.07); o.updateMatrix(); this.outline.setMatrixAt(i, o.matrix);
      const up = new THREE.Vector3(0, 1.45, 0).applyEuler(o.rotation);
      o.position.add(up); o.scale.setScalar(hide ? 0 : 1); o.updateMatrix(); this.head.setMatrixAt(i, o.matrix);
      o.scale.setScalar(hide ? 0 : 1.09); o.updateMatrix(); this.headOut.setMatrixAt(i, o.matrix);
      o.position.y += s.lie ? 0 : 0.05; o.scale.setScalar(hide ? 0 : 1.02); o.updateMatrix(); this.hat.setMatrixAt(i, o.matrix);
    });
    for (const m of [this.body, this.outline, this.head, this.headOut, this.hat]) m.instanceMatrix.needsUpdate = true;
  }
}
