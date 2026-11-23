// People, low-poly: a six-sided tunic in a role's colours, a big faceted head, block legs that step when they
// walk, little floating hands (a nod to Prison Architect). Hats and tools say who they are and what they're doing.
import * as THREE from "three";
import { A, person as rig, tool as kitTool, bone } from "./assets.js";
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
  return { outfit: hit[1], accent: hit[2], hat: hit[3], skin: SKIN[h % SKIN.length], hair: HAIR[(h >>> 3) % HAIR.length] };
}

// low-poly, like everything else: a six-sided tunic, a twelve-faced head, little block legs, octahedron hands
let BODY_GEO = null, HEAD_GEO = null, HAND_GEO = null, LEG_GEO = null, HAT_GEO = null;
function geos() {
  if (BODY_GEO) return;
  BODY_GEO = new THREE.CylinderGeometry(0.3, 0.46, 0.95, 6).translate(0, 0.475, 0);
  HEAD_GEO = new THREE.DodecahedronGeometry(0.34, 0);
  HAND_GEO = new THREE.OctahedronGeometry(0.11, 0);
  LEG_GEO = new THREE.BoxGeometry(0.17, 0.34, 0.2).translate(0, -0.17, 0);         // pivots at the hip
  HAT_GEO = new THREE.SphereGeometry(0.36, 6, 2, 0, Math.PI * 2, 0, Math.PI * 0.45);  // a faceted cap of hair or cloth
}
const BODY_Y = 0.3, HEAD_Y = 1.55;
const solid = (geo, mat) => mesh(geo, mat, { cast: true, receive: false });

function hatMesh(kind, L) {
  const g = new THREE.Group();
  const metal = (c) => M(c, null, { metalness: 0.5, roughness: 0.45 });
  if (kind === "crown") {
    g.add(solid(new THREE.CylinderGeometry(0.27, 0.3, 0.16, 6, 1, true), M(C.gold, null, { metalness: 0.6, roughness: 0.35, side: THREE.DoubleSide })));
    for (let k = 0; k < 5; k++) { const p = solid(new THREE.ConeGeometry(0.07, 0.18, 4), metal(C.gold)); const a = k / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.27, 0.15, Math.sin(a) * 0.27); g.add(p); }
    g.position.y = 0.3;
  } else if (kind === "battered") {
    const top = solid(new THREE.CylinderGeometry(0.22, 0.27, 0.26, 6), M(0x5a4532)); top.position.set(0.02, 0.13, 0);
    g.add(solid(new THREE.CylinderGeometry(0.44, 0.46, 0.05, 7), M(0x5a4532)), top);
    g.position.y = 0.26; g.rotation.z = 0.12;
  } else if (kind === "helmet") {
    g.add(solid(new THREE.SphereGeometry(0.39, 6, 2, 0, Math.PI * 2, 0, Math.PI / 2), metal(L.accent)));
    const nose = solid(new THREE.BoxGeometry(0.06, 0.26, 0.06), metal(L.accent)); nose.position.set(0, -0.1, -0.36); g.add(nose);
    g.position.y = 0.04;
  } else if (kind === "hood") {
    g.add(solid(new THREE.SphereGeometry(0.42, 6, 3, 0, Math.PI * 2, 0, Math.PI * 0.62), M(L.outfit)));
    const tip = solid(new THREE.ConeGeometry(0.16, 0.3, 4), M(L.outfit)); tip.position.set(0, 0.2, 0.3); tip.rotation.x = 1.2; g.add(tip);
    g.position.y = -0.02; g.rotation.x = -0.25;
  } else if (kind === "straw") {
    g.add(solid(new THREE.ConeGeometry(0.64, 0.34, 8), M(C.thatch)));
    g.position.y = 0.32;
  } else if (kind === "cap") {
    g.add(solid(HAT_GEO, M(L.accent)));
    g.position.y = 0.06;
  } else if (kind === "jester") {
    for (const s of [-1, 1]) { const c = solid(new THREE.ConeGeometry(0.11, 0.5, 4), M(s < 0 ? L.outfit : L.accent)); c.position.set(s * 0.22, 0.38, 0); c.rotation.z = -s * 0.7; g.add(c); const b = solid(new THREE.OctahedronGeometry(0.07, 0), M(C.gold)); b.position.set(s * 0.42, 0.55, 0); g.add(b); }
    g.add(solid(HAT_GEO, M(L.outfit)));
  } else if (kind === "pointy") {
    const c = solid(new THREE.ConeGeometry(0.3, 0.78, 5), M(L.outfit)); c.position.y = 0.45; c.rotation.z = 0.15;
    g.add(c, solid(new THREE.CylinderGeometry(0.52, 0.52, 0.04, 8), M(L.outfit)));
    g.position.y = 0.12;
  } else if (kind === "apron" || kind === "none") {
    g.add(solid(HAT_GEO, M(L.hair))); g.position.y = 0.02;
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
    this.root = new THREE.Group();
    this.pivot = new THREE.Group(); this.root.add(this.pivot);
    const body = solid(BODY_GEO, M(this.L.outfit)); body.position.y = BODY_Y;
    const belt = solid(new THREE.CylinderGeometry(0.42, 0.44, 0.1, 6), M(this.L.accent)); belt.position.y = BODY_Y + 0.3;
    const collar = solid(new THREE.CylinderGeometry(0.22, 0.31, 0.12, 6), M(this.L.accent)); collar.position.y = BODY_Y + 0.92;
    this.head = new THREE.Group(); this.head.position.y = HEAD_Y;
    this.head.add(solid(HEAD_GEO, M(this.L.skin)));
    for (const sx of [-1, 1]) { const e = mesh(new THREE.BoxGeometry(0.07, 0.09, 0.04), M(0x1b140f), { cast: false }); e.position.set(sx * 0.12, 0.03, -0.31); this.head.add(e); }
    if (king) { const beard = solid(new THREE.ConeGeometry(0.2, 0.32, 5), M(0x8a6a4a)); beard.rotation.x = Math.PI; beard.position.set(0, -0.3, -0.12); this.head.add(beard); }
    const hat = hatMesh(king ? (crowned ? "crown" : "battered") : this.L.hat, this.L); this.head.add(hat);
    this.handR = solid(HAND_GEO, M(this.L.skin)); this.handL = solid(HAND_GEO, M(this.L.skin));
    this.handR.position.set(0.55, 0.72, -0.05); this.handL.position.set(-0.55, 0.72, -0.05);
    this.legL = solid(LEG_GEO, M(0x4a3a2c)); this.legR = solid(LEG_GEO, M(0x4a3a2c));
    this.legL.position.set(-0.15, 0.34, 0); this.legR.position.set(0.15, 0.34, 0);
    this.tools = {}; this.toolKind = null;
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.55, 8).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x1a2a40, transparent: true, opacity: 0.25, depthWrite: false }));
    shadow.position.y = 0.03; this.root.add(shadow); this.shadow = shadow;
    this.pivot.add(body, belt, collar, this.head, this.handR, this.handL, this.legL, this.legR);
    this.root.scale.setScalar(king ? 1.1 : 1);
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
    R.set(0.55, 0.72, -0.05); Lh.set(-0.55, 0.72, -0.05); this.handR.rotation.set(0, 0, 0);
    this.legL.rotation.set(0, 0, 0); this.legR.rotation.set(0, 0, 0);
    this.shadow.visible = true;
    if (heading !== null) this.root.rotation.y = heading;
    const s = Math.sin(t * 9), c = Math.cos(t * 9);
    this.hold(["chop", "mine", "dig", "hammer", "cut", "fish", "judge", "read", "eat", "forage", "twist"].includes(anim) ? anim : null);
    switch (anim) {
      case "walk": case "run": {
        const k = anim === "run" ? 1.7 : 1;
        const ph = Math.sin(t * 9 * k);
        P.position.y = Math.abs(ph) * 0.06; P.rotation.z = ph * 0.04; P.rotation.x = -0.06 * k;
        this.legL.rotation.x = ph * 0.7; this.legR.rotation.x = -ph * 0.7;
        R.z = -0.05 - ph * 0.28; Lh.z = -0.05 + ph * 0.28; break;
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
        P.position.y = -0.3; this.legL.rotation.x = this.legR.rotation.x = -1.45;
        R.set(0.3, 0.75 + (anim === "eat" ? Math.max(0, s) * 0.5 : 0), -0.45); Lh.set(-0.3, 0.72, -0.45); this.head.rotation.x = 0.25; break;
      case "talk": case "speak": case "sing": case "trade":
        R.set(0.5, 0.9 + Math.max(0, s) * 0.35, -0.25); this.head.rotation.y = Math.sin(t * 1.3) * 0.25; P.position.y = Math.abs(c) * 0.02; break;
      case "judge": R.set(0.45, 1.0, -0.35); this.head.rotation.x = -0.1; break;
      case "think": R.set(0.25, 1.25, -0.35); this.head.rotation.x = 0.2; break;
      case "pray": R.set(0.08, 0.95, -0.42); Lh.set(-0.08, 0.95, -0.42); this.head.rotation.x = 0.35; break;
      case "dance": P.rotation.y = Math.sin(t * 2) * 0.6; P.position.y = Math.abs(s) * 0.12; this.legL.rotation.x = s * 0.6; this.legR.rotation.x = -s * 0.6; R.y = 1.35; Lh.y = 1.35; break;
      default: P.position.y = Math.sin(t * 1.6) * 0.015; this.head.rotation.y = Math.sin(t * 0.4) * 0.3;
    }
  }
}

// everyone else: instanced bodies, heads, hats and legs (hundreds of people for a handful of draw calls)
export class Crowd {
  constructor(scene, max = 600) {
    geos();
    this.max = max;
    const flat = () => new THREE.MeshStandardMaterial({ roughness: 1, flatShading: true });
    this.body = new THREE.InstancedMesh(BODY_GEO, flat(), max);
    this.head = new THREE.InstancedMesh(HEAD_GEO, flat(), max);
    this.hat = new THREE.InstancedMesh(HAT_GEO, flat(), max);
    this.legs = new THREE.InstancedMesh(LEG_GEO, new THREE.MeshStandardMaterial({ color: 0x4a3a2c, roughness: 1, flatShading: true }), max * 2);
    for (const m of [this.body, this.head, this.hat, this.legs]) { m.castShadow = true; }
    this.group = new THREE.Group(); this.group.add(this.body, this.head, this.hat, this.legs);
    scene.add(this.group);
    this.people = [];
    this.o = new THREE.Object3D(); this.o.rotation.order = "YXZ";    // turn to face, then lean forward
    this.m = new THREE.Matrix4(); this.l = new THREE.Matrix4(); this.r = new THREE.Matrix4(); this.zero = new THREE.Matrix4().makeScale(0, 0, 0);
  }

  set(people) {   // [{role, handle, home:[x,z], work:[x,z]}]
    this.people = people.slice(0, this.max);
    const col = new THREE.Color();
    this.people.forEach((p, i) => {
      const L = look(p.role, p.handle);
      this.body.setColorAt(i, col.setHex(L.outfit)); this.head.setColorAt(i, col.setHex(L.skin));
      this.hat.setColorAt(i, col.setHex(L.hat === "none" || L.hat === "apron" ? L.hair : L.hat === "straw" ? C.thatch : L.accent));
    });
    for (const m of [this.body, this.head, this.hat]) if (m.instanceColor) m.instanceColor.needsUpdate = true;
    for (const m of [this.body, this.head, this.hat]) m.count = this.people.length;
    this.legs.count = this.people.length * 2;
  }

  // positions: [{x, y, z, heading, bob, lean, stride, lie, hidden}]
  update(states) {
    const o = this.o, m = this.m, l = this.l, r = this.r;
    states.forEach((s, i) => {
      if (i >= this.people.length) return;
      if (s.hidden) { for (const k of [this.body, this.head, this.hat]) k.setMatrixAt(i, this.zero); this.legs.setMatrixAt(i * 2, this.zero); this.legs.setMatrixAt(i * 2 + 1, this.zero); return; }
      o.position.set(s.x, s.y + (s.lie ? 0.5 : s.bob), s.z); o.rotation.set(s.lie ? -Math.PI / 2 : s.lean || 0, s.heading, 0, "YXZ"); o.scale.set(1, 1, 1); o.updateMatrix();
      m.copy(o.matrix);
      this.body.setMatrixAt(i, l.makeTranslation(0, BODY_Y, 0).premultiply(m));
      this.head.setMatrixAt(i, l.makeTranslation(0, HEAD_Y, 0).premultiply(m));
      this.hat.setMatrixAt(i, l.makeTranslation(0, HEAD_Y + 0.07, 0).premultiply(m));
      const sw = s.sit ? -1.45 : (s.stride || 0);
      for (const [k, sx, a] of [[0, -0.15, sw], [1, 0.15, s.sit ? sw : -sw]]) {
        l.makeTranslation(sx, 0.34, 0).multiply(r.makeRotationX(a)).premultiply(m);
        this.legs.setMatrixAt(i * 2 + k, l);
      }
    });
    for (const k of [this.body, this.head, this.hat, this.legs]) k.instanceMatrix.needsUpdate = true;
  }
}

// ---------------------------------------------------------------- the KayKit people (when the models loaded)
// Knight, Barbarian, Mage, Rogue, Hooded Rogue - by role. One shared set of animations; tools in the right hand.
const KIND = [
  [/guard|soldier|captain|knight|sentry|watch|warlord/, "Knight"],
  [/thief|poacher|spy|scout|smuggler|assassin|outlaw|cutpurse/, "Rogue_Hooded"],
  [/priest|healer|monk|nun|scholar|scribe|mage|wizard|witch|teacher|steward|physician|alchemist|herbal|seer|druid/, "Mage"],
  [/smith|miner|woodcutter|lumber|mason|builder|labou?r|quarry|warrior|hunter|butcher|brawler|carpenter/, "Barbarian"],
];
const CLIP = { walk: "Walking_A", run: "Running_A", chop: "1H_Melee_Attack_Chop", hammer: "1H_Melee_Attack_Chop",
  mine: "2H_Melee_Attack_Chop", dig: "PickUp", cut: "PickUp", forage: "PickUp", twist: "Use_Item", fish: "Use_Item",
  judge: "Interact", read: "Interact", talk: "Interact", sing: "Cheer", dance: "Cheer", cheer: "Cheer", pray: "Spellcasting",
  sit: "Sit_Floor_Idle", eat: "Sit_Floor_Idle", sleep: "Lie_Idle", idle: "Idle" };
const HOLD = { chop: "axe_1handed", hammer: "axe_1handed", mine: "axe_1handed", fish: "staff", judge: "staff", eat: "mug_full" };
const SHOW = { Knight: /Knight_Cape/, Mage: /Mage_Hat|Mage_Cape/, Barbarian: /$^/, Rogue: /Rogue_Cape/, Rogue_Hooded: /Rogue_Cape/ };
let HEIGHT = null;

export class RigPerson {
  constructor({ role = "", handle = "", name, king = false, crowned = false }) {
    const r = String(role).toLowerCase();
    const kind = king ? "Knight" : role === "jester" ? "Rogue" : (KIND.find(([re]) => re.test(r)) || [null, ["Rogue", "Barbarian", "Rogue"][hashStr(handle) % 3]])[1];
    this.root = new THREE.Group();
    this.model = rig(kind);
    this.model.rotation.y = Math.PI;                       // they face +z; our people face -z
    this.model.traverse((o) => { if (o.isMesh && !o.isSkinnedMesh && SHOW[kind] && SHOW[kind].test(o.name)) o.visible = true; });
    if (/guard|soldier|captain|knight|warlord/.test(r)) this.model.traverse((o) => { if (o.isMesh && /Helmet|1H_Sword$|Round_Shield/.test(o.name)) o.visible = true; });
    if (HEIGHT === null) { const b = new THREE.Box3().setFromObject(this.model); HEIGHT = Math.max(1, b.max.y - b.min.y); }
    this.model.scale.setScalar((king ? 1.95 : 1.8) / HEIGHT);
    this.root.add(this.model);
    this.mixer = new THREE.AnimationMixer(this.model);
    this.actions = {}; this.cur = null; this.lastT = null;
    this.hand = bone(this.model, "handslot.r");
    this.tools = {}; this.toolKind = null;
    if (king && crowned) {
      const head = bone(this.model, "head"), crown = new THREE.Group(), gold = new THREE.MeshStandardMaterial({ color: 0xf2c24e, metalness: 0.6, roughness: 0.35, flatShading: true });
      crown.add(new THREE.Mesh(new THREE.CylinderGeometry(0.33, 0.36, 0.2, 6, 1, true), gold));
      for (let k = 0; k < 5; k++) { const p = new THREE.Mesh(new THREE.ConeGeometry(0.08, 0.22, 4), gold); const a = k / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.33, 0.18, Math.sin(a) * 0.33); crown.add(p); }
      crown.position.y = 0.95; if (head) head.add(crown);
    }
    this.root.userData = { person: this, tip: name ? `<strong>${name}</strong>` : "" };
    this.root.traverse((o) => { o.userData.tip = this.root.userData.tip; o.userData.person = this; });
  }

  pose(anim, t, heading = null) {
    if (heading !== null) this.root.rotation.y = heading;
    const name = A.clips[CLIP[anim] || "Idle"] ? CLIP[anim] || "Idle" : "Idle";
    if (name !== this.cur) {
      const next = this.actions[name] || (this.actions[name] = this.mixer.clipAction(A.clips[name]));
      next.reset().setEffectiveWeight(1).play();
      if (this.cur && this.actions[this.cur]) this.actions[this.cur].crossFadeTo(next, 0.25, false);
      this.cur = name;
    }
    this.hold(HOLD[anim] || null);
    const dt = this.lastT === null ? 0 : Math.min(0.1, Math.max(0, t - this.lastT));
    this.lastT = t;
    this.mixer.update(dt);
  }

  hold(kind) {
    if (kind === this.toolKind || !this.hand) return;
    if (this.toolKind && this.tools[this.toolKind]) this.tools[this.toolKind].visible = false;
    this.toolKind = kind;
    if (!kind) return;
    if (!this.tools[kind]) { const m = kitTool(kind); if (!m) return; this.tools[kind] = m; this.hand.add(m); }
    this.tools[kind].visible = true;
  }
}

function hashStr(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }

// the KayKit person when the models are there, the hand-built one otherwise
export function makePerson(opts) { return A.chars ? new RigPerson(opts) : new Person(opts); }

// ---------------------------------------------------------------- the crowd in KayKit people, baked
// Hundreds of rigged people would be too much to animate, so each kind of person is baked once into a handful of
// poses (standing, two steps of a walk, the top of a swing, bent over, sitting, lying) and drawn instanced: a
// walk alternates its two steps, work swings between standing and the swing.
const POSES = [["idle", "Idle", 0], ["walk1", "Walking_A", 0.25], ["walk2", "Walking_A", 0.75], ["swing", "1H_Melee_Attack_Chop", 0.38],
  ["stoop", "PickUp", 0.45], ["sit", "Sit_Floor_Idle", 0], ["lie", "Lie_Idle", 0]];
const KINDS = ["Barbarian", "Rogue", "Rogue_Hooded", "Mage", "Knight"];

function bake(kind, clipName, frac) {
  const m = rig(kind);
  const holder = new THREE.Group(); holder.add(m);
  m.rotation.y = Math.PI;
  const mixer = new THREE.AnimationMixer(m), clip = A.clips[clipName] || A.clips.Idle;
  if (clip) { const a = mixer.clipAction(clip); a.play(); mixer.setTime(clip.duration * frac); }
  holder.updateMatrixWorld(true);
  const parts = [], v = new THREE.Vector3();
  let material = null;
  m.traverse((o) => {
    if (!o.isMesh || !o.visible || /Helmet|Hat|Cape|Shield|Sword|Axe|Staff|Wand|Spellbook|Mug|Knife|Crossbow|Throwable|Quiver/i.test(o.name)) return;
    const src = o.geometry, pos = src.attributes.position, out = new Float32Array(pos.count * 3);
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      if (o.isSkinnedMesh) o.applyBoneTransform(i, v);
      v.applyMatrix4(o.matrixWorld);
      out[i * 3] = v.x; out[i * 3 + 1] = v.y; out[i * 3 + 2] = v.z;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(out, 3));
    if (src.attributes.uv) g.setAttribute("uv", src.attributes.uv.clone());
    if (src.index) g.setIndex(src.index.clone());
    parts.push(g);
    material = material || o.material;
  });
  if (!parts.length) return null;
  const geo = mergeGeometries(parts.map((p) => (p.index ? p : p)), false);
  geo.computeVertexNormals(); geo.computeBoundingBox();
  const h = geo.boundingBox.max.y - geo.boundingBox.min.y;
  return { geo, material: material.clone(), minY: geo.boundingBox.min.y, h };
}

export class KitCrowd {
  constructor(scene, max = 600) {
    this.max = max;
    this.group = new THREE.Group(); scene.add(this.group);
    this.meshes = {};                // kind -> pose -> InstancedMesh
    let unit = null;
    for (const kind of KINDS) {
      this.meshes[kind] = {};
      for (const [pose, clip, frac] of POSES) {
        const b = bake(kind, clip, frac);
        if (!b) continue;
        if (pose === "idle" && unit === null) unit = 1.8 / b.h;
        const s = unit || 1.8 / b.h;
        b.geo.translate(0, -b.minY, 0).scale(s, s, s);
        if (pose === "lie" || pose === "sit") b.geo.translate(0, 0, 0);
        const im = new THREE.InstancedMesh(b.geo, b.material, max);
        im.count = 0; im.castShadow = true; im.frustumCulled = false;
        this.meshes[kind][pose] = im; this.group.add(im);
      }
    }
    this.people = []; this.kinds = [];
    this.o = new THREE.Object3D(); this.o.rotation.order = "YXZ";
  }

  set(people) {
    this.people = people.slice(0, this.max);
    this.kinds = this.people.map((p) => {
      const r = String(p.role || "").toLowerCase();
      return (KIND.find(([re]) => re.test(r)) || [null, ["Rogue", "Barbarian", "Rogue"][hashStr(p.handle) % 3]])[1];
    });
  }

  update(states) {
    for (const k of KINDS) for (const im of Object.values(this.meshes[k] || {})) im.count = 0;
    const o = this.o, t = performance.now() / 1000;
    states.forEach((s, i) => {
      if (i >= this.people.length || s.hidden) return;
      const kind = this.kinds[i], j = this.people[i].j || i;
      let pose = "idle";
      if (s.lie) pose = "lie";
      else if (s.sit) pose = "sit";
      else if (s.walkPose) pose = (Math.floor(t * 4 + j) % 2) ? "walk1" : "walk2";
      else if (s.work === "swing") pose = (Math.floor(t * 2 + j * 0.37) % 2) ? "swing" : "idle";
      else if (s.work === "stoop") pose = (Math.floor(t * 0.7 + j * 0.3) % 3) ? "stoop" : "idle";
      const im = (this.meshes[kind] || {})[pose] || (this.meshes[kind] || {}).idle;
      if (!im) return;
      o.position.set(s.x, s.y + (s.sit ? 0.3 : 0), s.z); o.rotation.set(0, s.heading, 0, "YXZ"); o.scale.set(1, 1, 1); o.updateMatrix();
      im.setMatrixAt(im.count++, o.matrix);
    });
    for (const k of KINDS) for (const im of Object.values(this.meshes[k] || {})) im.instanceMatrix.needsUpdate = true;
  }
}
