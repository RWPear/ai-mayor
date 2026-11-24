// Emberfall in 3D: loads a day (or a whole run of days), builds the world, and plays it back on the clock.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { GTAOPass } from "three/addons/postprocessing/GTAOPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { makeTextures, TEX, M } from "./materials.js";
import { Land, V } from "./terrain.js";
import { Nature } from "./nature.js";
import { buildingMesh, tentsMesh, pilesMesh, cartMesh, WIN_LIT, FLAME, esc } from "./buildings.js";
import { Person, Crowd, KitCrowd, makePerson } from "./people.js";
import { loadAssets, A as KIT } from "./assets.js";
import { Rig, MODES } from "./camera.js";
import { hash, rng, clamp } from "./noise.js";

import { startLive, api as liveApi } from "./live.js";
const params = new URLSearchParams(location.search);
const RECORD = params.has("record");
const LIVE = params.has("live");
const QUALITY = params.get("quality") || (matchMedia("(max-width: 700px)").matches ? "low" : "high");
const $ = (id) => document.getElementById(id);
if (RECORD || params.get("hud") === "0") document.body.classList.add("nohud");

// ------------------------------------------------------------------ renderer
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: RECORD });
renderer.setPixelRatio(RECORD ? 1 : Math.min(QUALITY === "low" ? 1.5 : 2, devicePixelRatio));
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.12;
renderer.outputColorSpace = THREE.SRGBColorSpace;
$("view").appendChild(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(50, 1, 0.3, 6000);
camera.position.set(40, 40, 60);
let composer = null, gtao = null;
makeTextures();

// ------------------------------------------------------------------ state
const index = { days: [], recorders: [] };
let S = null, land = null, nature = null, rig = null, town = null, people = [], crowd = null, king = null;
let now = 0, playing = !RECORD, speed = 6, lastEv = -1, captionUntil = 0, dayIx = 0;
let smoke = null, fires = [], flags = [], lights = [], timed = [], projects = [], staged = [], piles = null;
let live = null, liveClock = null, liveRate = 1;

async function loadIndex() {
  if (LIVE) {                                  // ./kingdom play: today so far, straight from the running world
    try { const d = await liveApi("/live/scene"); if (d) index.days = [{ day: d.day, data: d }]; } catch (e) { /* not running */ }
    try { const r = await fetch("recorders.json"); if (r.ok) index.recorders = await r.json(); } catch (e) { /* defaults */ }
    if (!index.recorders.length) index.recorders = DEFAULT_RECORDERS;
    return;
  }
  const embedded = JSON.parse($("scene-data").textContent || "null");
  if (embedded) index.days = (Array.isArray(embedded) ? embedded : [embedded]).map((d) => ({ day: d.day, data: d }));
  else {
    try {
      const r = await fetch("days/scenes.json", { cache: "no-store" });
      if (r.ok) index.days = (await r.json()).map((d) => ({ day: d.day, file: `days/${d.file}` }));
    } catch (e) { /* no server: drop a file instead */ }
  }
  try { const r = await fetch("recorders.json"); if (r.ok) index.recorders = await r.json(); } catch (e) { /* defaults below */ }
  if (!index.recorders.length) index.recorders = DEFAULT_RECORDERS;
}
const DEFAULT_RECORDERS = [
  { name: "overview", pos: [-70, 95, -150], look: [30, 0, 10], fov: 38 },
  { name: "the_field", pos: [5, 28, -40], look: [40, 0, 10], fov: 45 },
  { name: "the_camp", pos: [20, 22, -95], look: [46, 0, -64], fov: 45 },
  { name: "top", pos: [32, 160, -20], look: [32, 0, 8], fov: 40 },
  { name: "king", follow: "king", offset: [9, 7, 9], fov: 45 },
];

async function getDay(i) {
  const e = index.days[i];
  if (!e.data) e.data = await (await fetch(e.file)).json();
  return e.data;
}

// ------------------------------------------------------------------ building a day
async function showDay(i, keepTime = false) {
  dayIx = Math.max(0, Math.min(index.days.length - 1, i));
  const data = await getDay(dayIx);
  const t0 = keepTime && S ? now : 0;
  S = data;
  if (!land) {
    land = new Land(scene, S, QUALITY);
    land.recording = RECORD;
    nature = new Nature(scene, land, S);
    rig = new Rig(camera, renderer.domElement, land);
    crowd = KIT.chars ? new KitCrowd(scene, QUALITY === "low" ? 220 : 600) : new Crowd(scene, QUALITY === "low" ? 220 : 600);
    setupPost();
    const kp = S.actors.king.start.pos;
    rig.lookAt(kp, 18);
  } else {
    land.S = S;
  }
  if (town) scene.remove(town);              // (geometry is small and partly shared between days: let it go)
  town = new THREE.Group(); scene.add(town);
  fires = []; flags = []; timed = []; projects = []; staged = [];
  const smokeAnchors = [];
  const ctx = { smoke: smokeAnchors, fires, flags, crowned: S.settlement.crowned };
  const lots = [];
  const pitBuilt = S.buildings.some((x) => x.shape === "firepit" && x.state === "standing");
  for (const b of S.buildings) {
    if (b.id === "b0" && pitBuilt) b.noPit = true;                // his new fire pit replaces the old cold one
    if (b.shape !== "wall_ring" && b.pos) lots.push({ pos: b.pos, hw: (b.rot % 180 ? b.size[1] : b.size[0]) / 2, hd: (b.rot % 180 ? b.size[0] : b.size[1]) / 2 });
    const m = buildingMesh(b, land, ctx);
    town.add(m);
    const ups = (b.upgrades || []).filter((u) => u.t && u.t > S.start);
    if (ups.length) {                            // the shack as it was before today's fixes, then after each one
      const times = [...new Set(ups.map((u) => u.t))].sort((x, y) => x - y);
      const stages = [{ at: -Infinity, mesh: buildingMesh({ ...b, upgrades: b.upgrades.filter((u) => !u.t || u.t <= S.start) }, land, { ...ctx, smoke: [], fires: [], flags: [] }) }];
      times.slice(0, -1).forEach((tt) => stages.push({ at: tt, mesh: buildingMesh({ ...b, upgrades: b.upgrades.filter((u) => !u.t || u.t <= tt) }, land, { ...ctx, smoke: [], fires: [], flags: [] }) }));
      stages.push({ at: times[times.length - 1], mesh: m });
      stages.forEach((st) => { if (st.mesh !== m) town.add(st.mesh); });
      staged.push(stages);
    }
    const when = b.state === "ruin" ? b.t : b.built_t;
    if (when && when > S.start) {               // went up (or fell down) today: scaffolding until then
      const before = buildingMesh({ ...b, state: "scaffold", progress: 0.9 }, land, { ...ctx, smoke: [], fires: [], flags: [] });
      town.add(before);
      timed.push({ at: when, after: m, before });
    }
  }
  for (const p of S.projects) {
    lots.push({ pos: p.pos, hw: (p.rot % 180 ? p.size[1] : p.size[0]) / 2, hd: (p.rot % 180 ? p.size[0] : p.size[1]) / 2 });
    projects.push({ p, mesh: null, shown: -1 });
  }
  town.add(tentsMesh(S.tents, land, ctx));
  piles = pilesMesh(S.piles, land); town.add(piles);
  if (S.peddler) { const cart = cartMesh(S.peddler.pos, land); cart.userData.until = S.peddler.until; town.add(cart); timed.push({ at: S.peddler.until, after: new THREE.Group(), before: cart, peddler: true }); }
  land.paint(S.trails || [], lots);
  land.placeGrass(lots, S.trails || []);
  nature.clearAround(lots);
  addFires(); addSmoke(smokeAnchors); addPeople();
  addLabels();
  buildHud();
  now = clamp(t0, 0, S.end - S.start);
  if (!keepTime && !RECORD) now = firstInteresting();
  lastEv = -1;
  $("empty").classList.remove("show");
  window.__world = { land, nature, rig, get S() { return S; } };     // for poking at it from the console
}

function firstInteresting() {             // start the day where something is happening (06:00 at the latest)
  const six = (Math.floor((S.start + 600) / 1440) * 1440 + 6 * 60) - S.start;
  return clamp(six, 0, S.end - S.start);
}

function addFires() {
  for (const f of fires) {
    const flame = new THREE.Group();
    const outer = new THREE.Mesh(new THREE.ConeGeometry(0.32, 0.9, 7), FLAME); outer.position.y = 0.45;
    const logs = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.08, 0.9, 5), M(0x3a2a1e)); logs.rotation.z = Math.PI / 2; logs.position.y = 0.08;
    flame.add(outer, logs);
    f.obj.add(flame); f.flame = flame;
  }
  for (const l of lights) scene.remove(l);
  lights = [];
  for (let i = 0; i < (QUALITY === "low" ? 2 : 6); i++) { const l = new THREE.PointLight(0xff9a40, 0, 18, 1.6); scene.add(l); lights.push(l); }
}

function addSmoke(anchors) {
  if (smoke) scene.remove(smoke);
  scene.updateMatrixWorld(true);
  const per = 10, n = Math.min(anchors.length, 60) * per;
  const pos = new Float32Array(n * 3), base = [];
  anchors.slice(0, 60).forEach((a) => { const w = a.getWorldPosition(new THREE.Vector3()); for (let k = 0; k < per; k++) base.push([w, k / per]); });
  const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  smoke = new THREE.Points(g, new THREE.PointsMaterial({ map: TEX.soft, color: 0xd8d4cc, size: 2.4, transparent: true, opacity: 0.35, depthWrite: false }));
  smoke.userData.base = base; smoke.frustumCulled = false;
  scene.add(smoke);
}

// ------------------------------------------------------------------ people
const WORK_ANIM = { woods: "chop", hill: "mine", river: "fish", field: "forage", road: "idle", camp: "idle", shack: "idle" };
const ROLE_AT = { woods: ["woodcutter", "lumberjack"], hill: ["mason", "miner"], river: ["fisher", "sailor"], field: ["farmer", "shepherd", "farmhand"], road: ["guard", "scout"] };

function addPeople() {
  spotPools = new Map();
  for (const p of people) town.remove(p.person.root);
  people = [];
  const placePos = Object.fromEntries(S.places.map((p) => [p.id, p.pos]));
  king = makePerson({ king: true, crowned: S.actors.king.crowned, name: "Aldric" + (S.actors.king.crowned ? ", King of Emberfall" : "") });
  king.root.traverse((o) => { o.userData.tip = `<strong>Aldric</strong>${S.actors.king.becoming ? `<br>${esc(S.actors.king.becoming)}` : ""}`; });
  town.add(king.root);
  for (const c of S.actors.court) {
    const p = makePerson({ role: c.id === "jester" ? "jester" : "steward", handle: c.id, name: c.name });
    town.add(p.root); people.push({ person: p, fixed: [c.pos[0] + 2.5, c.pos[1] - 2], anim: "talk", who: c, roam: c.id === "jester" });
  }
  const named = S.actors.settlers.slice(0, QUALITY === "low" ? 12 : 30);
  for (const s of named) {
    const p = makePerson({ role: s.role, handle: s.handle, name: `@${s.handle}` });
    p.root.traverse((o) => { o.userData.tip = `<strong>@${esc(s.handle)}</strong><br>${esc(s.name)}, ${esc(s.role)}${s.condition ? ` (${s.condition})` : ""}`; });
    town.add(p.root);
    const j = hash(s.handle), kings = S.projects.filter((x) => !x.owner), proj = kings.length && j % 3 === 0 ? kings[j % kings.length] : null;
    const own = S.projects.find((x) => x.owner === s.handle);
    people.push({ person: p, s, home: s.home_pos, work: s.work_pos, workPlace: s.work, tent: s.home.tent !== undefined, j, spots: workSpots(s.work, j, proj && !proj.owner ? proj : null), own });
  }
  // everyone else, as a crowd with homes (houses by residents, then tents) and work places
  const homes = [];
  for (const b of S.buildings) if (b.residents && b.residents.length) for (let k = 0; k < b.residents.length; k++) homes.push({ pos: b.pos, tent: false });
  S.tents.forEach((t) => { homes.push({ pos: t, tent: true }); homes.push({ pos: t, tent: true }); });
  const total = Object.values(S.actors.crowd.day || {}).reduce((a, b) => a + b, 0);
  const cap = crowd.max, want = Math.min(cap, Math.max(0, total - named.length));
  const list = [];
  const work = Object.entries(S.actors.crowd.day || {});
  const kingsP = S.projects.filter((x) => !x.owner), proj = kingsP.length ? kingsP : null, crew = new Map();
  for (let i = 0; i < want; i++) {
    const R = rng(i * 13 + S.day);
    let wp = "field", acc = 0, roll = R() * total;
    for (const [p, n] of work) { acc += n; if (roll <= acc) { wp = p; break; } }
    // only so many hands fit on one building (the same crew limit the simulation uses)
    const pj = proj ? proj[i % proj.length] : null;
    const onProject = pj && R() < 0.35 && (crew.get(pj.id) || 0) < (CREW[pj.scale] || 4);
    if (onProject) crew.set(pj.id, (crew.get(pj.id) || 0) + 1);
    const wpos = onProject ? pj.pos : placePos[wp] || placePos.field;
    const h = homes.length ? homes[i % homes.length] : { pos: placePos.field, tent: false };
    const roles = ROLE_AT[wp] || ["farmer"];
    const j = hash(i * 31 + 7);
    list.push({ role: onProject ? "mason" : roles[i % roles.length], handle: `c${i}`, home: h.pos, work: wpos, tent: h.tent, j, proj: onProject, workPlace: wp,
      spots: workSpots(wp, j, onProject ? pj : null), from: onProject ? pj.started_t : null, alt: onProject ? workSpots(wp, j, null) : null });
  }
  crowd.set(list);
  crowd.list = list;
}

// where a settler is at minute t. Mornings they walk from home to their first work spot (a standing tree, a
// rock on the hill, a place on the river bank, a side of the scaffolding, a row in the garden), work there a
// while, walk to the next, break for a bite at midday, and walk home in the evening. They only bob when they
// walk; at a spot they work at it, facing it.
const WALK = 70;                                              // metres a minute, an easy stroll
const CREW = { tiny: 1, small: 3, medium: 5, large: 8, huge: 14 };
function settlerAt(p, t, eventFor) {
  const m = (((t % 1440) + 1440) % 1440), j = p.j;
  const ev = eventFor && eventFor(p);
  if (ev) return { pos: ev.pos, anim: "talk", walk: false, heading: null };
  if (p.s && p.s.condition === "jailed") return { hidden: true };
  if (p.s && p.s.condition === "wounded") return { pos: p.home, anim: "sleep", lie: true };
  const mine = p.from && t < p.from && p.alt && p.alt.length ? p.alt : p.spots;      // the job hasn't started yet
  const spots = mine && mine.length ? mine : [{ pos: p.work, face: null, anim: WORK_ANIM[p.workPlace] || "idle" }];
  const seg = 50 + (j % 40);                                  // minutes at each spot
  const spotAt = (k) => spots[(hash(j * 7 + k * 13) >>> 0) % spots.length];
  const leave = 396 + (j % 90), back = 1110 + ((j >>> 7) % 90);
  const first = spotAt(0).pos, toWork = Math.hypot(first[0] - p.home[0], first[1] - p.home[1]) / WALK + 2;
  if (m >= leave && m < leave + toWork) { const f = (m - leave) / toWork; return { pos: lerp2(p.home, first, f), anim: "walk", walk: true, from: p.home, to: first }; }
  if (m >= leave + toWork && m < back) {
    const k = Math.floor((m - leave - toWork) / seg), into = (m - leave - toWork) - k * seg;
    const cur = spotAt(k), prev = k ? spotAt(k - 1) : cur;
    const d = Math.hypot(cur.pos[0] - prev.pos[0], cur.pos[1] - prev.pos[1]), walkT = d / WALK;
    if (into < walkT) return { pos: lerp2(prev.pos, cur.pos, into / walkT), anim: "walk", walk: true, from: prev.pos, to: cur.pos };
    const lunch = 720 + (j % 30);
    if (m >= lunch && m < lunch + 30) return { pos: cur.pos, anim: "eat", walk: false, heading: cur.face ? headingTo(cur.pos, cur.face) : null, sit: true };
    return { pos: cur.pos, anim: cur.anim, walk: false, heading: cur.face ? headingTo(cur.pos, cur.face) : (j % 628) / 100 };
  }
  const lastK = Math.max(0, Math.floor((back - leave - toWork) / seg)), last = spotAt(lastK).pos;
  const toHome = Math.hypot(last[0] - p.home[0], last[1] - p.home[1]) / WALK + 2;
  if (m >= back && m < back + toHome) { const f = (m - back) / toHome; return { pos: lerp2(last, p.home, f), anim: "walk", walk: true, from: last, to: p.home }; }
  if (p.own && m >= back + toHome && m < 1290) {             // evenings on their own build, by their home
    const o = p.own, a = (j % 628) / 100, r = Math.max(o.size[0], o.size[1]) / 2 + 0.9;
    const pos = [o.pos[0] + Math.cos(a) * r, o.pos[1] + Math.sin(a) * r];
    return { pos, anim: o.shape === "plot" ? "dig" : "hammer", walk: false, heading: headingTo(pos, o.pos) };
  }
  if (p.tent && m >= back + toHome && m < 1350) { const a = j % 628 / 100; return { pos: [p.home[0] + 1.6 + Math.cos(a) * 1.8, p.home[1] - 2.2 + Math.sin(a) * 1.8], anim: "sit", walk: false, heading: a + Math.PI, sit: true }; }
  return { hidden: true };
}

// the places someone works today: real things to stand at. Each place has a pool of spots (one per standing
// tree, one per rock, a step apart around the scaffolding, a row in each garden, ...) and people are dealt
// spots from it in turn, so a crowd spreads out instead of piling onto one spot.
let spotPools = new Map();
function workSpots(where, j, proj) {
  const key = proj ? `p:${proj.id}` : where;
  if (!spotPools.has(key)) spotPools.set(key, { spots: makePool(where, proj), next: 0 });
  const pool = spotPools.get(key), all = pool.spots, ex = all.excl || 0;
  if (!all.length) return [];
  const q = pool.next++, out = [];
  if (q < ex) return [all[q]];                                          // one tender per garden row
  const rest = all.slice(ex), L = rest.length;
  for (let k = 0; k < 6; k++) out.push(rest[(q + k * 37 + (j % 7) * k) % L]);
  return out;
}
function makePool(where, proj) {
  const R = rng(hash(String(where) + (proj ? proj.id : ""))), out = [];
  const near = (a, b, d) => { const L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1; return [a[0] + (b[0] - a[0]) / L * d, a[1] + (b[1] - a[1]) / L * d]; };
  if (proj) {                                              // around the scaffolding, facing the walls, a step apart
    const [w, d] = proj.size, rot = (proj.rot || 0) % 180 ? 1 : 0, hw = (rot ? d : w) / 2 + 1.1, hd = (rot ? w : d) / 2 + 1.1;
    const per = 2 * (hw + hd) * 2 / 1.4;
    for (let k = 0; k < per; k++) {
      const u = (k / per) * 4, side = Math.floor(u), f = (u % 1) * 2 - 1;
      const pos = side === 0 ? [proj.pos[0] + f * hw, proj.pos[1] - hd] : side === 1 ? [proj.pos[0] + hw, proj.pos[1] + f * hd]
        : side === 2 ? [proj.pos[0] - f * hw, proj.pos[1] + hd] : [proj.pos[0] - hw, proj.pos[1] - f * hd];
      out.push({ pos, face: proj.pos, anim: R() < 0.75 ? "hammer" : "dig" });
    }
    return out;
  }
  if (where === "woods") {
    const ts = S.trees_all || S.trees, felled = Math.round(S.trees_felled || 0);
    for (const tr of ts.slice(felled, felled + 120)) out.push({ pos: near([tr[0], tr[1]], land.woods.pos, -1.3), face: [tr[0], tr[1]], anim: "chop" });
  } else if (where === "hill") {
    for (const st of (S.stones_all || S.stones).slice(Math.round(S.stones_hauled || 0)).slice(0, 160)) {
      const a = R() * 6.28, x = st[0] + Math.cos(a) * 1.3, z = st[1] + Math.sin(a) * 1.3, y = land.height(x, z);
      const slope = Math.max(Math.abs(land.height(x + 1.5, z) - y), Math.abs(land.height(x, z + 1.5) - y)) / 1.5;
      if (slope < 0.3) out.push({ pos: [x, z], face: [st[0], st[1]], anim: "mine" });   // not halfway up a cliff
      if (out.length >= 120) break;
    }
  } else if (where === "river") {
    const P = S.terrain.river.path, w = S.terrain.river.width / 2 + 1.6;
    for (let k = 0; k < 120; k++) {
      const i = Math.floor(R() * (P.length - 1)), f = R(), a = P[i], b = P[i + 1];
      const x = a[0] + (b[0] - a[0]) * f, z = a[1] + (b[1] - a[1]) * f, L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const nx = -(b[1] - a[1]) / L, nz = (b[0] - a[0]) / L, sgn = (x + nx - land.field[0]) ** 2 + (z + nz - land.field[1]) ** 2 < (x - nx - land.field[0]) ** 2 + (z - nz - land.field[1]) ** 2 ? 1 : -1;
      out.push({ pos: [x + nx * w * sgn, z + nz * w * sgn], face: [x, z], anim: R() < 0.6 ? "fish" : "dig" });
    }
  } else if (where === "field") {
    for (const b of S.buildings.filter((x) => x.shape === "plot" && x.state === "standing")) {      // one per row-step
      const [w, d] = (b.rot || 0) % 180 ? [b.size[1], b.size[0]] : b.size, hw = w / 2 + 0.9, hd = d / 2 + 0.9;
      for (let x = -hw + 0.8; x < hw; x += 2.2) for (const sz of [-1, 1]) out.push({ pos: [b.pos[0] + x, b.pos[1] + sz * hd], face: [b.pos[0] + x, b.pos[1]], anim: "forage" });   // along the beds' edges
      for (let z = -hd + 2; z < hd - 1; z += 2.4) for (const sx of [-1, 1]) out.push({ pos: [b.pos[0] + sx * hw, b.pos[1] + z], face: [b.pos[0], b.pos[1] + z], anim: "forage" });
    }
    out.excl = out.length;
    for (let k = 0; k < 140; k++) { const a = R() * 6.28, r = 14 + R() * 40; out.push({ pos: [land.field[0] + Math.cos(a) * r, land.field[1] + Math.sin(a) * r], face: null, anim: R() < 0.5 ? "cut" : "forage" }); }
  } else if (where === "road") {                          // guards and scouts walk the old road
    const P = S.terrain.road.path;
    for (let k = 0; k < 60; k++) {
      const i = Math.floor(R() * (P.length - 1)), f = R(), a = P[i], b = P[i + 1];
      out.push({ pos: [a[0] + (b[0] - a[0]) * f + (R() - 0.5) * 6, a[1] + (b[1] - a[1]) * f + (R() - 0.5) * 6], face: null, anim: "idle" });
    }
  } else {
    const c = (S.places.find((x) => x.id === where) || {}).pos || land.field;
    for (let k = 0; k < 40; k++) { const a = R() * 6.28, r = 3 + R() * 12; out.push({ pos: [c[0] + Math.cos(a) * r, c[1] + Math.sin(a) * r], face: c, anim: "idle" }); }
  }
  return out;
}

const lerp2 = (a, b, f) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
const headingTo = (a, b) => Math.atan2(-(b[0] - a[0]), (b[1] - a[1]));     // local -z faces (dx, dz) in world terms

function kingAt(t) {
  const tr = S.actors.king.track;
  if (!tr.length || t < tr[0].t) {
    const h = (((t % 1440) + 1440) % 1440) / 60;
    return { pos: S.actors.king.start.pos, anim: h < 6 || h >= 23 ? "sleep" : "idle", text: "" };
  }
  let i = 0;
  while (i + 1 < tr.length && tr[i + 1].t <= t) i++;
  const e = tr[i], prev = i ? tr[i - 1].pos : S.actors.king.start.pos;
  const d = Math.hypot(e.pos[0] - prev[0], e.pos[1] - prev[1]);
  const span = e.anim === "walk" ? Math.max(1, e.dur) : Math.min(e.dur, Math.max(1, d / 75));
  const f = clamp((t - e.t) / span, 0, 1);
  const pos = lerp2(prev, e.pos, f);
  const moving = f < 1 && d > 0.5;
  const busy = t < e.t + e.dur;
  return { pos, anim: moving ? "walk" : busy ? e.anim : "idle", text: busy ? e.text : "", heading: d > 0.5 ? headingTo(prev, e.pos) : null, entry: e };
}

// ------------------------------------------------------------------ post-processing
function setupPost() {
  if (QUALITY === "low") return;
  composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  gtao = new GTAOPass(scene, camera, innerWidth, innerHeight);
  gtao.updateGtaoMaterial({ radius: 1.4, distanceExponent: 1.4, thickness: 1.2, scale: 1.1, samples: 12 });
  gtao.blendIntensity = 0.85;
  composer.addPass(gtao);
  composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.32, 0.5, 0.86));
  composer.addPass(new OutputPass());
}

// ------------------------------------------------------------------ the loop
let last = performance.now();
const tmp = new THREE.Vector3();
function step(dtReal) {
  if (!S) return;
  if (LIVE) {                                  // follow the world's clock: smoothly up to where it is now
    const target = (liveClock ?? S.end) - S.start;
    now = Math.min(target, now + dtReal * Math.max(liveRate, (target - now) > 45 ? 30 : 0));
    if (target - now > 150) now = target - 30;
  } else if (playing) now += dtReal * speed;
  if (!LIVE && now >= S.end - S.start) {
    if (playing && dayIx < index.days.length - 1 && $("cont").checked) { showDay(dayIx + 1); return; }
    now = S.end - S.start; playing = false; syncPlay();
  }
  const t = S.start + now, h = (((t % 1440) + 1440) % 1440) / 60;
  const wx = (S.weather.filter((w) => w.t <= t).pop() || S.weather[0] || {}).weather || "a mild day";
  const kingS = kingAt(t);
  const focus = rig.mode === "follow" || rig.mode === "director" ? V(kingS.pos[0], kingS.pos[1], 0) : rig.controls.target.clone();
  if (rig.mode === "top") focus.copy(V(rig.top.x, rig.top.z, 0));
  const { day: daylight } = land.update(h, wx, focus, camera.position, dtReal);
  const night = 1 - daylight;
  // the day's hourly samples: trees, stones
  const sm = (S.samples || []).filter((x) => x.t <= t).pop();
  if (sm) { nature.setFelled(sm.felled); nature.setHauled(sm.hauled); }
  else { nature.setFelled(S.trees_felled); nature.setHauled(S.stones_hauled); }
  for (const x of timed) { const after = t >= x.at; x.after.visible = after; x.before.visible = !after; }
  for (const stages of staged) { let cur = stages[0]; for (const st of stages) if (t >= st.at) cur = st; for (const st of stages) st.mesh.visible = st === cur; }
  for (const pr of projects) {
    const pts = pr.p.progress_at || [];
    let prog = pr.p.progress;
    if (pts.length) { prog = pts[0][1]; for (const [tt, v] of pts) if (tt <= t) prog = v; }
    if (pr.shown < 0 || Math.abs(prog - pr.shown) >= 0.04) {
      if (pr.mesh) town.remove(pr.mesh);
      pr.mesh = buildingMesh({ ...pr.p, progress: prog }, land, { smoke: [], fires: [], flags: [], crowned: false });
      town.add(pr.mesh); pr.shown = prog;
    }
    pr.mesh.visible = !(pr.p.started_t && t < pr.p.started_t);       // not pegged out yet
  }
  // the king
  king.root.position.copy(V(kingS.pos[0], kingS.pos[1], land.height(kingS.pos[0], kingS.pos[1])));
  king.root.visible = !(kingS.anim === "sleep" && Math.hypot(kingS.pos[0], kingS.pos[1]) < 8);   // asleep inside the shack
  king.pose(kingS.anim, performance.now() / 1000, kingS.heading);
  // settlers
  const evNow = S.events.filter((e) => e.handles && e.handles.length && e.pos && t >= e.t && t < e.t + 45);
  const eventFor = (p) => p.s && evNow.find((e) => e.handles.includes(p.s.handle));
  const clock = performance.now() / 1000;
  for (const p of people) {
    if (p.fixed) {
      let pos = p.fixed, anim = h > 7 && h < 21 ? p.anim : "sleep", head = Math.PI;
      if (p.roam && h > 7 && h < 21) {                     // the jester strolls about, stopping to perform
        const cyc = (t % 20) / 20, a = Math.floor(t / 20) * 2.4;
        const A = [p.fixed[0] + Math.cos(a) * 6, p.fixed[1] + Math.sin(a) * 6], B = [p.fixed[0] + Math.cos(a + 2.4) * 6, p.fixed[1] + Math.sin(a + 2.4) * 6];
        if (cyc < 0.45) { pos = lerp2(A, B, cyc / 0.45); anim = "walk"; head = headingTo(A, B); } else { pos = B; anim = "sing"; head = headingTo(B, p.fixed); }
      }
      p.person.root.position.copy(V(pos[0], pos[1], land.height(pos[0], pos[1]))); p.person.pose(anim, clock + 3, head); p.person.root.visible = h > 6 && h < 22; continue;
    }
    const st = settlerAt(p, t, eventFor);
    p.person.root.visible = !st.hidden;
    if (st.hidden) continue;
    p.person.root.position.copy(V(st.pos[0], st.pos[1], land.height(st.pos[0], st.pos[1])));
    p.person.pose(st.anim, clock + (p.j % 100) / 10, st.walk ? headingTo(st.from, st.to) : st.heading ?? null);
  }
  if (crowd.list) {
    crowd.update(crowd.list.map((p) => {
      const st = settlerAt(p, t);
      if (st.hidden) return { hidden: true, x: 0, y: -50, z: 0, heading: 0, bob: 0 };
      const y = land.height(st.pos[0], st.pos[1]);
      const bob = st.walk ? Math.abs(Math.sin(clock * 9 + p.j)) * 0.05 : 0;           // only walking bobs (and steps)
      const swing = (Math.sin(clock * 4.5 + p.j) + 1) / 2;
      const lean = st.walk ? -0.08 : st.anim === "chop" || st.anim === "mine" || st.anim === "hammer" ? -0.05 - swing * 0.22
        : st.anim === "forage" || st.anim === "dig" || st.anim === "cut" ? -0.3 - swing * 0.12 : st.anim === "fish" ? -0.05 : 0;
      return { x: st.pos[0], y: y + (st.sit || st.anim === "sit" ? -0.3 : 0), z: -st.pos[1], heading: st.walk ? headingTo(st.from, st.to) : st.heading ?? (p.j % 628) / 100, bob, lean, lie: st.lie,
        stride: st.walk ? Math.sin(clock * 9 + p.j) * 0.7 : 0, sit: st.sit || st.anim === "sit" || st.anim === "eat",
        walkPose: !!st.walk, work: ["chop", "mine", "hammer"].includes(st.anim) ? "swing" : ["forage", "dig", "cut", "fish"].includes(st.anim) ? "stoop" : null };
    }));
  }
  // night: windows, fires, smoke
  WIN_LIT.emissiveIntensity = night > 0.35 && (h > 16 || h < 7.5) ? 1.8 * night : 0;
  FLAME.emissiveIntensity = 2.2 + Math.sin(clock * 13) * 0.4;
  const lit = fires.filter((f) => f.camp ? (h > 17.5 || h < 6.5) : f.small ? (h > 18 || h < 7) : true);
  for (const f of fires) { f.flame.visible = lit.includes(f); if (f.flame.visible) { f.flame.scale.set(1, 0.85 + Math.sin(clock * 11 + f.obj.id) * 0.15, 1); } }
  const cam = camera.position;
  const near = lit.map((f) => ({ f, d: f.obj.getWorldPosition(tmp).distanceTo(cam), p: tmp.clone() })).sort((a, b) => a.d - b.d);
  lights.forEach((l, i) => { const n = near[i]; if (n && night > 0.3 && n.d < 120) { l.position.copy(n.p).add(new THREE.Vector3(0, 1, 0)); l.intensity = (6 + Math.sin(clock * 9 + i) * 1.5) * night; } else l.intensity = 0; });
  if (smoke) {
    const smoking = (h > 5.5 && h < 9.5) || (h > 16.5 && h < 23.5);
    smoke.visible = smoking;
    if (smoking) {
      const p = smoke.geometry.attributes.position, wind = land.uniforms.uWind.value;
      smoke.userData.base.forEach(([w, ph], i) => { const k = (ph + clock * 0.08) % 1; p.setXYZ(i, w.x + k * 3 * wind + Math.sin(k * 6 + i) * 0.3, w.y + k * 7, w.z - k * 1.2 * wind); });
      p.needsUpdate = true; smoke.material.opacity = 0.32 * (1 - night * 0.5);
    }
  }
  for (const f of flags) f.rotation.y = Math.sin(clock * 2 + f.id) * 0.25 * land.uniforms.uWind.value;
  // camera
  rig.update(dtReal, kingS, () => directorShot(t, kingS));
  if (!RECORD) hud(t, h, wx, kingS);
}

// the director: mostly Aldric, cutting to whatever's happening when something is
let dirIx = 0;
function directorShot(t, k) {
  const R = rng(Math.floor(t) + dirIx++);
  const upcoming = S.events.filter((e) => e.public && e.pos && e.t >= t - 30 && e.t <= t + 90 && e.drama >= 1).sort((a, b) => b.drama - a.drama);
  const roll = R();
  if (upcoming.length && roll < 0.45) { const e = upcoming[0]; showCaption(e.text, e.drama >= 2); return { pos: e.pos, dist: 12 + e.drama * 3, height: 6 + e.drama * 2, angle: R() * 6, spin: 0.05, hold: 7 + R() * 3 }; }
  if (roll < 0.62) return { pos: S.places.find((p) => p.id === "field")?.pos || [38, 6], dist: 70, height: 45, angle: R() * 6, spin: 0.03, hold: 8, rise: 0.4 };
  if (roll < 0.75 && people.length) { const p = people[Math.floor(R() * people.length)]; const pos = p.person.root.position; if (p.person.root.visible) return { pos: [pos.x, -pos.z], dist: 6, height: 2.5, angle: R() * 6, spin: 0.08, hold: 6 }; }
  return { follow: true, dist: 4.5 + R() * 6, height: 1.6 + R() * 3, angle: R() * 6, spin: 0.06 * (R() < 0.5 ? -1 : 1), hold: 7 + R() * 4 };
}

// ------------------------------------------------------------------ HUD
function buildHud() {
  const st = S.settlement;
  $("title").textContent = `${S.city}, day ${LIVE ? S.day + 1 : S.day}`;
  const chips = [[st.crowned ? "crowned" : "not crowned"], [st.stage], [`${st.settled} settlers`], [`${st.beds} beds, ${st.free_beds} free`],
    st.tents ? [`${st.tents} in tents`, "warn"] : null, st.on_road ? [`${st.on_road} on the road`] : null, st.next_arrival ? [`arrivals day ${st.next_arrival}`] : null].filter(Boolean);
  $("stats").innerHTML = chips.map(([t, c]) => `<span class="chip ${c || ""}">${esc(t)}</span>`).join("");
  $("events").innerHTML = S.events.map((e, i) => `<button class="ev ${e.public ? "public" : ""} d${e.drama}" data-i="${i}" type="button"><span class="t">${esc(e.time.split(", ")[1])}</span>${esc(e.text)}</button>`).join("");
  document.querySelectorAll(".ev").forEach((el) => el.addEventListener("click", () => { const e = S.events[+el.dataset.i]; now = e.t - S.start - 2; if (e.pos) { rig.set("orbit"); rig.lookAt(e.pos, 16); syncMode(); } }));
  $("shotbtns").innerHTML = S.shots.map((s, i) => `<button type="button" data-i="${i}">${i + 1}. ${esc(s.text.slice(0, 60))}${s.text.length > 60 ? "..." : ""}</button>`).join("");
  document.querySelectorAll("#shotbtns button").forEach((b) => b.addEventListener("click", () => { const s = S.shots[+b.dataset.i]; now = s.t - S.start - 1; rig.set("orbit"); rig.lookAt(s.target, s.distance); syncMode(); showCaption(s.text, true); }));
  $("scrub").max = S.end - S.start;
  $("daylabel").textContent = `Day ${LIVE ? S.day + 1 : S.day}` + (index.days.length > 1 ? ` of ${index.days[index.days.length - 1].day}` : "");
  $("prev").disabled = dayIx === 0; $("next").disabled = dayIx >= index.days.length - 1;
}
function hud(t, h, wx, k) {
  $("scrub").value = now;
  $("clock").textContent = `${String(Math.floor(h)).padStart(2, "0")}:${String(Math.floor((h % 1) * 60)).padStart(2, "0")} · ${wx}`;
  $("doing").textContent = k.text || (k.anim === "sleep" ? "Aldric is asleep." : k.anim === "walk" ? "Aldric is walking." : "Aldric is between things.");
  const sm = (S.samples || []).filter((x) => x.t <= t).pop();
  const stores = (sm && sm.stores) || S.settlement.stores;
  $("stores").innerHTML = Object.entries(stores).map(([m, v]) => `<span class="chip">${v} ${esc(m)}</span>`).join("") + `<span class="chip">${S.settlement.gold} gold</span>`;
  let idx = -1;
  for (let i = 0; i < S.events.length; i++) if (S.events[i].t <= t) idx = i;
  if (idx !== lastEv) {
    document.querySelectorAll(".ev").forEach((el, i) => el.classList.toggle("past", i < idx));
    if (idx > lastEv && idx >= 0 && S.events[idx].public && S.events[idx].drama >= 1 && rig.mode !== "director") showCaption(S.events[idx].text, S.events[idx].drama >= 2);
    const cur = document.querySelector(`.ev[data-i="${idx}"]`); if (cur && playing) cur.scrollIntoView({ block: "nearest" });
    lastEv = idx;
  }
  if (performance.now() > captionUntil) $("caption").classList.remove("show");
}
function showCaption(text, big) { if (RECORD) return; $("caption").textContent = text; $("caption").classList.toggle("big", !!big); $("caption").classList.add("show"); captionUntil = performance.now() + 6500; }
function syncPlay() { $("play").textContent = playing ? "Pause" : "Play"; $("play").setAttribute("aria-pressed", String(playing)); }
function syncMode() { document.querySelectorAll("#modes button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === rig.mode))); $("modehint").textContent = HINT[rig.mode] || ""; }
const HINT = { follow: "Drag to look around him, scroll to zoom.", director: "Sit back: the camera picks the shots.", walk: "WASD or arrows to walk, drag (or click) to look, Shift to run.", top: "Drag or WASD to pan, scroll to zoom.", orbit: "Drag to orbit, right-drag to pan, scroll to zoom.", recorder: "A fixed recorder camera. R for the next one." };

let labels = [];
function addLabels() {
  labels.forEach((l) => l.el.remove()); labels = [];
  for (const p of S.places) {
    const el = document.createElement("div"); el.className = "label"; el.textContent = p.name; $("labels").appendChild(el);
    labels.push({ el, pos: V(p.pos[0], p.pos[1], land.height(p.pos[0], p.pos[1]) + 8) });
  }
}
function drawLabels() {
  const w = innerWidth, h = innerHeight, show = rig && (rig.mode === "top" || rig.mode === "orbit" || rig.mode === "follow");
  for (const l of labels) {
    const p = l.pos.clone().project(camera), vis = show && p.z < 1 && Math.abs(p.x) < 1.05 && Math.abs(p.y) < 1.05;
    l.el.style.display = vis ? "block" : "none";
    if (vis) l.el.style.transform = `translate(${(p.x + 1) / 2 * w}px, ${(1 - p.y) / 2 * h}px) translate(-50%, -50%)`;
  }
}

function frame(ms) {
  const dt = Math.min(0.1, (ms - last) / 1000); last = ms;
  step(dt);
  if (composer) composer.render(); else renderer.render(scene, camera);
  drawLabels();
  requestAnimationFrame(frame);
}
function resize() {
  const w = innerWidth, h = innerHeight;
  renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix();
  if (composer) { composer.setSize(w, h); gtao?.setSize(w, h); }
}
addEventListener("resize", resize);

// ------------------------------------------------------------------ controls
function bindUi() {
  $("play").addEventListener("click", () => { if (S && now >= S.end - S.start) now = 0; playing = !playing; syncPlay(); });
  $("speed").addEventListener("change", (e) => { speed = +e.target.value; });
  $("scrub").addEventListener("input", (e) => { now = +e.target.value; });
  $("prev").addEventListener("click", () => showDay(dayIx - 1));
  $("next").addEventListener("click", () => showDay(dayIx + 1));
  document.querySelectorAll("#modes button").forEach((b) => b.addEventListener("click", () => { setMode(b.dataset.mode); }));
  addEventListener("keydown", (e) => {
    if (/^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(e.target.tagName) || e.target.isContentEditable) return;   // typing, not playing
    if (e.code === "Space") { e.preventDefault(); $("play").click(); }
    const n = { Digit1: "follow", Digit2: "director", Digit3: "walk", Digit4: "top", Digit5: "orbit", Digit6: "recorder" }[e.code];
    if (n) setMode(n);
    if (e.code === "KeyR") { const i = index.recorders.indexOf(rig.recorder); rig.set("recorder", { recorder: index.recorders[(i + 1) % index.recorders.length] }); syncMode(); }
    if (e.code === "KeyH") document.body.classList.toggle("nohud");
    if (e.code === "BracketLeft") showDay(dayIx - 1);
    if (e.code === "BracketRight") showDay(dayIx + 1);
  });
  const tip = $("tip"), ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  renderer.domElement.addEventListener("pointermove", (ev) => {
    if (!S || rig.mode === "walk") { tip.style.display = "none"; return; }
    mouse.set(ev.clientX / innerWidth * 2 - 1, -(ev.clientY / innerHeight) * 2 + 1);
    ray.setFromCamera(mouse, camera);
    const hit = ray.intersectObjects(town.children, true).find((x) => x.object.userData && x.object.userData.tip && x.object.visible);
    if (hit) { tip.innerHTML = hit.object.userData.tip; tip.style.display = "block"; tip.style.left = `${Math.min(ev.clientX + 14, innerWidth - 300)}px`; tip.style.top = `${ev.clientY + 14}px`; }
    else tip.style.display = "none";
  });
  const load = (text) => { try { const d = JSON.parse(text); index.days = [{ day: d.day, data: d }]; showDay(0); } catch (e) { $("doing").textContent = `That file isn't a scene: ${e.message}`; } };
  $("file").addEventListener("change", (e) => e.target.files[0]?.text().then(load));
  addEventListener("dragover", (e) => { e.preventDefault(); $("drop").classList.add("show"); });
  addEventListener("dragleave", (e) => { if (e.target === $("drop")) $("drop").classList.remove("show"); });
  addEventListener("drop", (e) => { e.preventDefault(); $("drop").classList.remove("show"); e.dataTransfer.files[0]?.text().then(load); });
}
function setMode(m) {
  if (m === "recorder") rig.set("recorder", { recorder: rig.recorder || index.recorders[0] });
  else rig.set(m, m === "walk" ? { from: king.root.position.clone().add(new THREE.Vector3(3, 0, 3)) } : {});
  syncMode();
}

// ------------------------------------------------------------------ live (./kingdom play)
// A new scene arrives every tick. Only rebuild the town when something you'd see changed shape (a building
// finished, a project started, a tent went up, new people); otherwise swap the data in place so nothing pops.
const shapeOf = (d) => JSON.stringify([d.day, d.start, d.settlement.crowned, d.tents.length, d.actors.settlers.length,
  Object.values(d.actors.crowd.day || {}).reduce((a, b) => a + b, 0) >> 3,
  d.buildings.map((b) => [b.id, b.state, b.built_t, (b.upgrades || []).length]), d.projects.map((p) => p.id), !!d.peddler]);
let liveShape = "";
async function liveScene(d) {
  const sh = shapeOf(d);
  if (!S || sh !== liveShape) {
    liveShape = sh;
    const keep = S && S.start === d.start ? now : null;
    index.days = [{ day: d.day, data: d }];
    await showDay(0, true);
    if (keep !== null) now = keep; else now = Math.max(0, (liveClock ?? d.end) - d.start - 60);
    return;
  }
  const old = S;
  S = d; land.S = d;
  for (const pr of projects) pr.p = d.projects.find((p) => p.id === pr.p.id) || pr.p;
  if (piles) town.remove(piles);
  piles = pilesMesh(S.piles, land); town.add(piles);
  if (old.events.length !== d.events.length) buildHud();
}
function liveState(st) {
  if (liveClock === null && S) now = Math.max(0, st.clock - S.start - 1);   // open on "now", not the start of the day
  liveClock = st.clock; liveRate = st.paused ? 0 : st.tick_min / st.tick_s;
}

// ------------------------------------------------------------------ the recorder's handle (headless capture)
window.kingdom = {
  days: () => index.days.map((d) => d.day),
  recorders: () => index.recorders.map((r) => r.name),
  async show({ day, minute = 12 * 60, recorder = "overview", frames = 6 }) {
    const i = index.days.findIndex((d) => d.day === day);
    if (i < 0) throw new Error(`no day ${day}`);
    if (i !== dayIx || !S) await showDay(i);
    let t = Math.floor(S.start / 1440) * 1440 + minute;          // the first time of day `minute` inside this post
    if (t < S.start) t += 1440;
    now = clamp(t - S.start, 0, S.end - S.start);
    const r = typeof recorder === "object" ? recorder : index.recorders.find((x) => x.name === recorder) || index.recorders[0];
    rig.set("recorder", { recorder: r });
    for (let k = 0; k < frames; k++) { step(0.016); if (composer) composer.render(); else renderer.render(scene, camera); await new Promise((res) => requestAnimationFrame(res)); }
    return { day: S.day, t: S.start + now, recorder: r.name };
  },
};

// ------------------------------------------------------------------ start
(async () => {
  bindUi(); resize();
  await Promise.all([loadIndex(), loadAssets((f) => { const el = document.getElementById("loading"); if (el) el.dataset.kit = Math.round(f * 100); })]);
  window.__kit = { ready: KIT.ready, chars: KIT.chars };
  if (!index.days.length) { $("empty").classList.add("show"); $("doing").textContent = "No scene loaded yet."; requestAnimationFrame(frame); return; }
  await showDay(index.days.length - 1);
  if (LIVE) { liveShape = shapeOf(S); live = startLive({ onScene: (d) => liveScene(d), onState: liveState }); }
  if (!RECORD) { rig.set("follow"); syncMode(); }
  syncPlay();
  document.body.classList.add("ready");
  window.kingdom.ready = true;
  requestAnimationFrame(frame);
})();
