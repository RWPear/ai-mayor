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
import { Person, Crowd } from "./people.js";
import { Rig, MODES } from "./camera.js";
import { hash, rng, clamp } from "./noise.js";

const params = new URLSearchParams(location.search);
const RECORD = params.has("record");
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
let smoke = null, fires = [], flags = [], lights = [], timed = [], projects = [];

async function loadIndex() {
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
    crowd = new Crowd(scene, QUALITY === "low" ? 220 : 600);
    setupPost();
    const kp = S.actors.king.start.pos;
    rig.lookAt(kp, 18);
  } else {
    land.S = S;
  }
  if (town) scene.remove(town);              // (geometry is small and partly shared between days: let it go)
  town = new THREE.Group(); scene.add(town);
  fires = []; flags = []; timed = []; projects = [];
  const smokeAnchors = [];
  const ctx = { smoke: smokeAnchors, fires, flags, crowned: S.settlement.crowned };
  const lots = [];
  for (const b of S.buildings) {
    if (b.shape !== "wall_ring" && b.pos) lots.push({ pos: b.pos, hw: (b.rot % 180 ? b.size[1] : b.size[0]) / 2, hd: (b.rot % 180 ? b.size[0] : b.size[1]) / 2 });
    const m = buildingMesh(b, land, ctx);
    town.add(m);
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
  town.add(pilesMesh(S.piles, land));
  if (S.peddler) { const cart = cartMesh(S.peddler.pos, land); cart.userData.until = S.peddler.until; town.add(cart); timed.push({ at: S.peddler.until, after: new THREE.Group(), before: cart, peddler: true }); }
  land.paint(S.trails || [], lots);
  land.placeGrass(lots, S.trails || []);
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
  for (const p of people) town.remove(p.person.root);
  people = [];
  const placePos = Object.fromEntries(S.places.map((p) => [p.id, p.pos]));
  king = new Person({ king: true, crowned: S.actors.king.crowned, name: "Aldric" + (S.actors.king.crowned ? ", King of Emberfall" : "") });
  king.root.traverse((o) => { o.userData.tip = `<strong>Aldric</strong>${S.actors.king.becoming ? `<br>${esc(S.actors.king.becoming)}` : ""}`; });
  town.add(king.root);
  for (const c of S.actors.court) {
    const p = new Person({ role: c.id === "jester" ? "jester" : "steward", handle: c.id, name: c.name });
    town.add(p.root); people.push({ person: p, fixed: [c.pos[0] + 2.5, c.pos[1] - 2], anim: c.id === "jester" ? "dance" : "talk", who: c });
  }
  const named = S.actors.settlers.slice(0, QUALITY === "low" ? 12 : 30);
  for (const s of named) {
    const p = new Person({ role: s.role, handle: s.handle, name: `@${s.handle}` });
    p.root.traverse((o) => { o.userData.tip = `<strong>@${esc(s.handle)}</strong><br>${esc(s.name)}, ${esc(s.role)}${s.condition ? ` (${s.condition})` : ""}`; });
    town.add(p.root);
    people.push({ person: p, s, home: s.home_pos, work: s.work_pos, workPlace: s.work, tent: s.home.tent !== undefined, j: hash(s.handle) });
  }
  // everyone else, as a crowd with homes (houses by residents, then tents) and work places
  const homes = [];
  for (const b of S.buildings) if (b.residents && b.residents.length) for (let k = 0; k < b.residents.length; k++) homes.push({ pos: b.pos, tent: false });
  S.tents.forEach((t) => { homes.push({ pos: t, tent: true }); homes.push({ pos: t, tent: true }); });
  const total = Object.values(S.actors.crowd.day || {}).reduce((a, b) => a + b, 0);
  const cap = crowd.max, want = Math.min(cap, Math.max(0, total - named.length));
  const list = [];
  const work = Object.entries(S.actors.crowd.day || {});
  const proj = S.projects.length ? S.projects : null;
  for (let i = 0; i < want; i++) {
    const R = rng(i * 13 + S.day);
    let wp = "field", acc = 0, roll = R() * total;
    for (const [p, n] of work) { acc += n; if (roll <= acc) { wp = p; break; } }
    const onProject = proj && R() < 0.35;
    const wpos = onProject ? proj[i % proj.length].pos : placePos[wp] || placePos.field;
    const h = homes.length ? homes[i % homes.length] : { pos: placePos.field, tent: false };
    const roles = ROLE_AT[wp] || ["farmer"];
    list.push({ role: onProject ? "mason" : roles[i % roles.length], handle: `c${i}`, home: h.pos, work: wpos, tent: h.tent, j: hash(i * 31 + 7), proj: onProject, workPlace: wp });
  }
  crowd.set(list);
  crowd.list = list;
}

// where a settler is at minute t: home -> work at 7, work -> home at 19 (each a little early or late), around
// the camp fires in the evening if they live in a tent
function settlerAt(p, t, eventFor) {
  const h = (((t % 1440) + 1440) % 1440) / 60, j = p.j;
  const leave = 6.6 + (j % 90) / 60, back = 18.5 + ((j >>> 7) % 90) / 60;
  const dist = Math.hypot(p.work[0] - p.home[0], p.work[1] - p.home[1]);
  const travel = dist / 75 / 60 + 0.05;                    // hours, at a walk
  const ev = eventFor && eventFor(p);
  if (ev) return { pos: ev.pos, anim: "talk", walk: false, heading: null };
  if (p.s && p.s.condition === "jailed") return { hidden: true };
  if (p.s && p.s.condition === "wounded") return { pos: p.home, anim: "sleep", lie: true };
  const wander = (base, r, speedK) => { const a = j % 628 / 100 + t * speedK; return [base[0] + Math.cos(a) * r, base[1] + Math.sin(a * 0.8) * r]; };
  if (h >= leave && h < leave + travel) { const f = (h - leave) / travel; return { pos: lerp2(p.home, p.work, f), anim: "walk", walk: true, from: p.home, to: p.work }; }
  if (h >= leave + travel && h < back) {
    const r = p.proj ? 4 + (j % 5) : 3 + (j % 9);
    const pos = wander(p.work, r, 0.004 + (j % 5) * 0.0008);
    return { pos, anim: p.proj ? "hammer" : (WORK_ANIM[p.workPlace] || "idle"), walk: false };
  }
  if (h >= back && h < back + travel) { const f = (h - back) / travel; return { pos: lerp2(p.work, p.home, f), anim: "walk", walk: true, from: p.work, to: p.home }; }
  if (p.tent && h >= back + travel && h < 22.5) { const a = j % 628 / 100; return { pos: [p.home[0] + 1.6 + Math.cos(a) * 1.8, p.home[1] - 2.2 + Math.sin(a) * 1.8], anim: "sit", walk: false, heading: a + Math.PI }; }
  return { hidden: true };
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
  if (playing) now += dtReal * speed;
  if (now >= S.end - S.start) {
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
  for (const pr of projects) {
    const pts = pr.p.progress_at || [];
    let prog = pr.p.progress;
    if (pts.length) { prog = pts[0][1]; for (const [tt, v] of pts) if (tt <= t) prog = v; }
    if (pr.shown < 0 || Math.abs(prog - pr.shown) >= 0.04) {
      if (pr.mesh) town.remove(pr.mesh);
      pr.mesh = buildingMesh({ ...pr.p, progress: prog }, land, { smoke: [], fires: [], flags: [], crowned: false });
      town.add(pr.mesh); pr.shown = prog;
    }
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
    if (p.fixed) { p.person.root.position.copy(V(p.fixed[0], p.fixed[1], land.height(p.fixed[0], p.fixed[1]))); p.person.pose(h > 7 && h < 21 ? p.anim : "sleep", clock + 3, Math.PI); p.person.root.visible = h > 6 && h < 22; continue; }
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
      const bob = st.walk ? Math.abs(Math.sin(clock * 9 + p.j)) * 0.12 : (st.anim === "chop" || st.anim === "mine" || st.anim === "hammer") ? Math.abs(Math.sin(clock * 4.5 + p.j)) * 0.06 : 0;
      const lean = st.anim === "forage" || st.anim === "dig" ? -0.35 : st.walk ? -0.08 : 0;
      return { x: st.pos[0], y: y + (st.anim === "sit" ? -0.2 : 0), z: -st.pos[1], heading: st.walk ? headingTo(st.from, st.to) : (p.j % 628) / 100 + clock * 0.05, bob, lean, lie: st.lie };
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
  $("title").textContent = `${S.city}, day ${S.day}`;
  const chips = [[st.crowned ? "crowned" : "not crowned"], [st.stage], [`${st.settled} settlers`], [`${st.beds} beds, ${st.free_beds} free`],
    st.tents ? [`${st.tents} in tents`, "warn"] : null, st.on_road ? [`${st.on_road} on the road`] : null, [`arrivals day ${st.next_arrival}`]].filter(Boolean);
  $("stats").innerHTML = chips.map(([t, c]) => `<span class="chip ${c || ""}">${esc(t)}</span>`).join("");
  $("events").innerHTML = S.events.map((e, i) => `<button class="ev ${e.public ? "public" : ""} d${e.drama}" data-i="${i}" type="button"><span class="t">${esc(e.time.split(", ")[1])}</span>${esc(e.text)}</button>`).join("");
  document.querySelectorAll(".ev").forEach((el) => el.addEventListener("click", () => { const e = S.events[+el.dataset.i]; now = e.t - S.start - 2; if (e.pos) { rig.set("orbit"); rig.lookAt(e.pos, 16); syncMode(); } }));
  $("shotbtns").innerHTML = S.shots.map((s, i) => `<button type="button" data-i="${i}">${i + 1}. ${esc(s.text.slice(0, 60))}${s.text.length > 60 ? "..." : ""}</button>`).join("");
  document.querySelectorAll("#shotbtns button").forEach((b) => b.addEventListener("click", () => { const s = S.shots[+b.dataset.i]; now = s.t - S.start - 1; rig.set("orbit"); rig.lookAt(s.target, s.distance); syncMode(); showCaption(s.text, true); }));
  $("scrub").max = S.end - S.start;
  $("daylabel").textContent = `Day ${S.day}` + (index.days.length > 1 ? ` of ${index.days[index.days.length - 1].day}` : "");
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
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
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
  await loadIndex();
  if (!index.days.length) { $("empty").classList.add("show"); $("doing").textContent = "No scene loaded yet."; requestAnimationFrame(frame); return; }
  await showDay(index.days.length - 1);
  if (!RECORD) { rig.set("follow"); syncMode(); }
  syncPlay();
  document.body.classList.add("ready");
  window.kingdom.ready = true;
  requestAnimationFrame(frame);
})();
