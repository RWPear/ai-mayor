// People: a round head on a simple body, in one of three shapes - tall (a bowling pin), wide (a blob) or small
// (a bean). The body colour says what they do, the shape is just who they are. No arms, no legs, no tools: all
// the life is in how they move - a waddle when they walk, a bob as they work, a nod and a wobble when they talk.
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { C, M, mesh } from "./materials.js";
import { hash } from "./noise.js";

const SKIN = [0xf7e2c8, 0xf0cfaa, 0xdcae84, 0xbb8a62, 0x8f6244];
// role -> body colour (soft, so a crowd reads as a crowd and not a bag of sweets)
const ROLE = [
  [/king|aldric/, 0x4f78c4], [/smith|forge|miner|mason|quarry/, 0x8a8178], [/guard|soldier|warrior|mercenar|sellsword|knight|squire|captain/, 0xc0605a],
  [/archer|scout|hunter|ranger|trapper|woodcutter|lumberjack|carpenter/, 0x6f9a55], [/thief|pickpocket|burglar|cutpurse|spy|assassin|smuggler/, 0x55565e],
  [/priest|monk|nun|friar|cleric|healer|herbal|physician|doctor|alchemist|witch/, 0xe9e3d2], [/farmer|farmhand|shepherd|peasant/, 0xd1a95a],
  [/fisher|sailor|pirate/, 0x5f95b5], [/baker|cook|chef|miller|innkeeper|brewer|bartender|barmaid/, 0xe8b48a], [/bard|minstrel|jester|juggler/, 0xb56cc4],
  [/merchant|shopkeeper|trader|peddler|jeweler|tailor/, 0x9a5f88], [/steward/, 0x5d5f8f], [/scholar|scribe|wizard|mage|sorcerer|teacher|librarian/, 0x7a6cc8],
  [/beggar|homeless|vagrant|drifter|urchin|hermit/, 0x9a8a72],
];
const KINDS = ["tall", "tall", "wide", "wide", "small"];

export function look(role, handle) {
  const r = String(role || "").toLowerCase(), h = hash(handle || role || "pip");
  const base = (ROLE.find(([re]) => re.test(r)) || [null, 0xa08f78])[1];
  const hsl = {}; new THREE.Color(base).getHSL(hsl);     // each one a shade off, so twenty farmers aren't one colour
  const body = new THREE.Color().setHSL(hsl.h + ((h >>> 7) % 21 - 10) / 500, hsl.s, Math.min(0.8, Math.max(0.3, hsl.l + ((h >>> 12) % 13 - 6) / 110))).getHex();
  return { body, skin: SKIN[h % SKIN.length], kind: KINDS[(h >>> 3) % KINDS.length], size: 0.92 + ((h >>> 17) % 17) / 100 };
}

// the three bodies (low poly on purpose), each with where its head sits and how big the head is
let G = null;
function geos() {
  if (G) return G;
  const pin = [[0, 0], [0.34, 0.02], [0.45, 0.2], [0.46, 0.4], [0.37, 0.66], [0.26, 0.9], [0.17, 1.1], [0, 1.18]];
  G = {
    tall: { geo: new THREE.LatheGeometry(pin.map(([r, y]) => new THREE.Vector2(r, y)), 6), top: 1.1, head: 0.36 },
    wide: { geo: new THREE.SphereGeometry(1, 7, 4).scale(0.7, 0.44, 0.56).translate(0, 0.44, 0), top: 0.82, head: 0.37 },
    small: { geo: new THREE.SphereGeometry(1, 6, 4).scale(0.38, 0.38, 0.36).translate(0, 0.38, 0), top: 0.7, head: 0.32 },
  };
  G.head = new THREE.IcosahedronGeometry(1, 1);
  const eye = (x) => new THREE.SphereGeometry(0.12, 5, 3).scale(0.8, 1.3, 0.5).translate(x, 0.08, -0.93);
  G.eyes = mergeGeometries([eye(-0.33), eye(0.33)]);
  return G;
}
const solid = (geo, mat) => mesh(geo, mat, { cast: true, receive: false });

// one motion vocabulary for both the named few and the crowd:
// {y, lean, sway, turn, sx, sy, nod, tilt, lie, blink}
function motion(kind, t, j = 0) {
  const m = { y: 0, lean: 0, sway: 0, turn: 0, sx: 1, sy: 1, nod: 0, tilt: 0, look: 0, lie: false };
  const breathe = Math.sin(t * 1.7 + j) * 0.02;
  switch (kind) {
    case "walk": case "run": {                      // a waddle: bob up each step, rock side to side
      const k = kind === "run" ? 1.7 : 1, ph = t * 7 * k + j, up = Math.abs(Math.sin(ph));
      m.y = up * 0.12 * k; m.sway = Math.sin(ph) * 0.13; m.lean = -0.08 * k;
      m.sy = 1 - (1 - up) * 0.07; m.sx = 1 + (1 - up) * 0.05; m.nod = Math.sin(ph * 2) * 0.06; break;
    }
    case "work": {                                  // bow into the job and come back up, squash on the down-beat
      const sw = (Math.sin(t * 4.2 + j) + 1) / 2;
      m.lean = -0.12 - sw * 0.38; m.sy = 1 - sw * 0.08; m.sx = 1 + sw * 0.05; m.nod = -sw * 0.2; break;
    }
    case "stoop": {                                 // bent over, little busy bobs (gardening, gathering, fishing)
      const sw = Math.abs(Math.sin(t * 3 + j));
      m.lean = -0.5 - sw * 0.1; m.nod = -0.15 - sw * 0.1; m.sy = 0.96; break;
    }
    case "talk": {                                  // nodding, a wobble, the odd turn of the head
      m.nod = Math.max(0, Math.sin(t * 5.5 + j)) * 0.22; m.tilt = Math.sin(t * 1.3 + j) * 0.15;
      m.sway = Math.sin(t * 2.2 + j) * 0.05; m.sy = 1 + Math.abs(Math.sin(t * 5.5 + j)) * 0.04; m.look = Math.sin(t * 0.7 + j) * 0.4; break;
    }
    case "sing": case "dance": {                    // bouncing on the spot, swaying
      const up = Math.abs(Math.sin(t * 5 + j));
      m.y = up * 0.16; m.sy = 1 + up * 0.08; m.sx = 1 - up * 0.04; m.sway = Math.sin(t * 2.5 + j) * 0.2; m.tilt = Math.sin(t * 2.5 + j) * 0.25;
      if (kind === "dance") m.turn = t * 2; break;
    }
    case "sit": {                                   // squashed down where they are
      m.sy = 0.78; m.sx = 1.12; m.y = -0.05; m.nod = Math.sin(t * 0.8 + j) * 0.05 + 0.05; m.look = Math.sin(t * 0.3 + j) * 0.5; break;
    }
    case "eat": { m.sy = 0.8; m.sx = 1.1; m.nod = Math.max(0, Math.sin(t * 3 + j)) * 0.25; break; }
    case "sleep": { m.lie = true; m.sx = 1 + breathe; m.sy = 1 + breathe; break; }
    case "pray": case "think": { m.nod = 0.3; m.lean = -0.08; m.sy = 1 + breathe; break; }
    default: {                                      // idle: breathing, looking about
      m.sy = 1 + breathe; m.look = Math.sin(t * 0.5 + j) * 0.6 * (Math.sin(t * 0.13 + j) > 0 ? 1 : 0); m.tilt = Math.sin(t * 0.9 + j) * 0.05;
    }
  }
  return m;
}
const WORK = new Set(["chop", "mine", "hammer", "craft", "cook", "dig"]);
const STOOP = new Set(["forage", "twist", "cut", "fish"]);
const TALK = new Set(["talk", "speak", "trade", "judge", "read"]);
const motionKind = (a) => WORK.has(a) ? "work" : STOOP.has(a) ? "stoop" : TALK.has(a) ? "talk" : a;

export class Person {
  constructor({ role, handle, name, king = false, crowned = false }) {
    const g = geos();
    this.L = look(king ? "king" : role, handle);
    if (king) this.L.kind = "tall";
    const V = g[this.L.kind];
    this.V = V;
    this.j = hash(handle || name || role || "pip") % 100;
    this.root = new THREE.Group();
    this.pivot = new THREE.Group(); this.root.add(this.pivot);        // the feet: the whole person tips about here
    this.body = solid(V.geo, M(this.L.body)); this.pivot.add(this.body);
    this.head = new THREE.Group(); this.pivot.add(this.head);
    const ball = solid(g.head, M(this.L.skin)); ball.scale.setScalar(V.head); this.head.add(ball);
    this.eyes = mesh(g.eyes, M(0x1d1915), { cast: false }); this.eyes.scale.setScalar(V.head); this.head.add(this.eyes);
    if (king && crowned) {                          // a little crown: a gold ring and five points
      const crown = new THREE.Group(), gold = M(C.gold, null, { metalness: 0.5, roughness: 0.4 });
      crown.add(solid(new THREE.CylinderGeometry(0.2, 0.22, 0.1, 6), gold));
      for (let k = 0; k < 5; k++) { const p = solid(new THREE.ConeGeometry(0.05, 0.14, 4), gold), a = k / 5 * Math.PI * 2; p.position.set(Math.cos(a) * 0.19, 0.11, Math.sin(a) * 0.19); crown.add(p); }
      crown.position.y = V.head * 0.88; this.head.add(crown);
    }
    const shadow = new THREE.Mesh(new THREE.CircleGeometry(0.5, 8).rotateX(-Math.PI / 2), new THREE.MeshBasicMaterial({ color: 0x1a2a40, transparent: true, opacity: 0.22, depthWrite: false }));
    shadow.position.y = 0.03; this.root.add(shadow); this.shadow = shadow;
    this.blink = 2.5 + (this.j % 30) / 10;
    this.root.scale.setScalar(this.L.size * (king ? 1.2 : 1));
    this.root.userData = { person: this, tip: name ? `<strong>${name}</strong>` : "" };
    this.root.traverse((o) => { o.userData.tip = this.root.userData.tip; o.userData.person = this; });
  }

  // anim: walk, run, chop/mine/hammer/dig/craft/cook (work), forage/cut/fish (stoop), talk/speak/trade/judge,
  // sing, dance, sit, eat, sleep, pray, think, idle
  pose(anim, t, heading = null) {
    const m = motion(motionKind(anim), t, this.j), V = this.V, P = this.pivot;
    if (heading !== null) this.root.rotation.y = heading;
    P.position.set(0, m.lie ? 0.4 : m.y, 0);
    P.rotation.set(m.lie ? Math.PI / 2 : m.lean, m.turn, m.sway, "YXZ");
    this.body.scale.set(m.sx, m.sy, m.sx);
    this.head.position.set(0, V.top * m.sy + V.head * 0.78, 0);
    this.head.rotation.set(-m.nod, m.look, m.tilt, "YXZ");
    this.eyes.scale.set(V.head, V.head * (m.lie || (t % this.blink) < 0.12 ? 0.12 : 1), V.head);
    this.shadow.visible = !m.lie;
  }
}

// everyone else: instanced, five draw calls for hundreds of people (three bodies, heads, eyes)
export class Crowd {
  constructor(scene, max = 600) {
    const g = geos();
    this.max = max;
    const flat = (c) => new THREE.MeshStandardMaterial({ color: c ?? 0xffffff, roughness: 1, flatShading: true });
    const im = (geo, mat) => { const m = new THREE.InstancedMesh(geo, mat, max); m.castShadow = true; m.frustumCulled = false; m.count = 0; return m; };
    this.bodies = { tall: im(g.tall.geo, flat()), wide: im(g.wide.geo, flat()), small: im(g.small.geo, flat()) };
    this.heads = im(g.head, flat());
    this.eyes = im(g.eyes, flat(0x1d1915)); this.eyes.castShadow = false;
    this.all = [...Object.values(this.bodies), this.heads, this.eyes];
    this.group = new THREE.Group(); this.group.add(...this.all);
    scene.add(this.group);
    this.people = []; this.looks = [];
    this.o = new THREE.Object3D(); this.o.rotation.order = "YXZ";
    this.m = new THREE.Matrix4(); this.l = new THREE.Matrix4(); this.r = new THREE.Matrix4(); this.e = new THREE.Euler(0, 0, 0, "YXZ");
    this.col = new THREE.Color();
  }

  set(people) {   // [{role, handle, ...}]
    this.people = people.slice(0, this.max);
    this.looks = this.people.map((p) => look(p.role, p.handle));
  }

  // states: [{x, y, z, heading, walkPose, work: "swing"|"stoop"|null, talk, sit, lie, kind (sing/dance/eat), hidden}]
  update(states) {
    const o = this.o, m = this.m, l = this.l, r = this.r, e = this.e, col = this.col, t = performance.now() / 1000, g = geos();
    const n = { tall: 0, wide: 0, small: 0, head: 0 };
    states.forEach((s, i) => {
      if (i >= this.people.length || s.hidden) return;
      const L = this.looks[i], V = g[L.kind], j = (this.people[i].j || i) % 100;
      const kind = s.lie ? "sleep" : s.kind ? s.kind : s.walkPose ? "walk" : s.work === "swing" ? "work" : s.work === "stoop" ? "stoop" : s.sit ? "sit" : s.talk ? "talk" : "idle";
      const q = motion(kind, t, j);
      o.position.set(s.x, s.y + (q.lie ? 0.4 : q.y) * L.size, s.z);
      o.rotation.set(q.lie ? Math.PI / 2 : q.lean, s.heading + q.turn, q.sway, "YXZ");
      o.scale.setScalar(L.size); o.updateMatrix();
      m.copy(o.matrix);
      const body = this.bodies[L.kind], k = n[L.kind]++;
      body.setMatrixAt(k, l.makeScale(q.sx, q.sy, q.sx).premultiply(m));
      body.setColorAt(k, col.setHex(L.body));
      // head: up on top of the (squashed) body, nodding and looking about
      e.set(-q.nod, q.look, q.tilt);
      l.makeTranslation(0, V.top * q.sy + V.head * 0.78, 0).multiply(r.makeRotationFromEuler(e)).multiply(r.makeScale(V.head, V.head, V.head)).premultiply(m);
      const h = n.head++;
      this.heads.setMatrixAt(h, l); this.heads.setColorAt(h, col.setHex(L.skin));
      if (q.lie || (t + j) % (2.5 + (j % 5) / 2) < 0.12) l.multiply(r.makeScale(1, 0.12, 1));   // blink
      this.eyes.setMatrixAt(h, l);
    });
    for (const k of ["tall", "wide", "small"]) this.bodies[k].count = n[k];
    this.heads.count = this.eyes.count = n.head;
    for (const im of this.all) { im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true; }
  }
}

export function makePerson(opts) { return new Person(opts); }
