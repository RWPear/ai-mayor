// Ready-made models instead of hand-built ones: the KayKit packs by Kay Lousberg (CC0, www.kaylousberg.com).
//   - Medieval Hexagon Pack: houses, tavern, smithy, mill, market, church, towers, castle, well, building stages
//     and scaffolding, ruins, tents, lumber and stone piles, crates, barrels
//   - Character Pack: Adventures: the people (Knight, Barbarian, Mage, Rogue, Hooded Rogue), rigged, with a shared
//     set of animations (walk, idle, chop, pick up, use, cheer, sit, lie down...) and their tools
// Everything falls back to the hand-built kit if a file is missing, or with ?assets=off.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import * as SkeletonUtils from "three/addons/utils/SkeletonUtils.js";

export const USE_KIT = new URLSearchParams(location.search).get("assets") !== "off";
const BASE = "assets/kaykit/";
export const A = { ready: false, chars: false, world: {}, people: {}, clips: {}, tools: {} };

const COLORED = ["home_A", "home_B", "tavern", "blacksmith", "lumbermill", "market", "mine", "church", "castle", "barracks",
  "archeryrange", "windmill", "watermill", "well", "tower_A", "tower_B", "tower_base"];
const NEUTRAL = ["building_destroyed", "building_dirt", "building_grain", "building_scaffolding", "building_stage_A",
  "building_stage_B", "building_stage_C", "building_bridge_A", "fence_wood_straight", "fence_stone_straight", "wall_straight",
  "tent", "resource_lumber", "resource_stone", "barrel", "crate_A_big", "crate_B_big", "crate_open", "sack", "wheelbarrow",
  "pallet", "crate_long_A", "bucket_water", "flag_blue", "ladder", "weaponrack"];
const PEOPLE = ["Knight", "Barbarian", "Mage", "Rogue", "Rogue_Hooded"];
const TOOLS = ["axe_1handed", "sword_1handed", "staff", "mug_full", "shield_round", "dagger"];

export async function loadAssets(progress = () => {}) {
  if (!USE_KIT) return false;
  const loader = new GLTFLoader();
  const load = (url) => new Promise((res) => loader.load(url, res, undefined, () => res(null)));
  const names = [...COLORED.flatMap((n) => [`building_${n}_blue`, `building_${n}_red`]), ...NEUTRAL];
  let done = 0;
  const total = names.length + PEOPLE.length + TOOLS.length + 1;
  const tick = () => progress(++done / total);
  await Promise.all([
    ...names.map((n) => load(`${BASE}world/${n}.gltf`).then((g) => { if (g) A.world[n] = prep(g.scene); tick(); })),
    ...PEOPLE.map((n) => load(`${BASE}chars/${n}.glb`).then((g) => { if (g) A.people[n] = prep(g.scene, true); tick(); })),
    ...TOOLS.map((n) => load(`${BASE}tools/${n}.gltf`).then((g) => { if (g) A.tools[n] = prep(g.scene); tick(); })),
    load(`${BASE}chars/animations.glb`).then((g) => { if (g) for (const c of g.animations) A.clips[c.name] = c; tick(); }),
  ]);
  A.ready = Object.keys(A.world).length > 20;
  A.chars = Object.keys(A.people).length >= 3 && Object.keys(A.clips).length >= 5;
  return A.ready;
}

function prep(scene, rigged = false) {
  scene.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true; o.receiveShadow = !rigged;
      if (o.material) { o.material.roughness = 0.85; o.material.metalness = 0; }
    }
  });
  scene.updateMatrixWorld(true);
  scene.userData.box = new THREE.Box3().setFromObject(scene);
  return scene;
}

export const has = (name) => !!A.world[name];

// a copy (geometry and materials shared), with its size: {w, h, d} in model units and the lowest point
export function model(name) {
  const s = A.world[name];
  if (!s) return null;
  const m = s.clone(true);
  const b = s.userData.box;
  m.userData.size = { w: b.max.x - b.min.x, h: b.max.y - b.min.y, d: b.max.z - b.min.z, cx: (b.max.x + b.min.x) / 2, cz: (b.max.z + b.min.z) / 2, minY: b.min.y };
  return m;
}

// one mesh's geometry with its node transform baked in, and its material (for instancing hundreds of them)
const geoCache = new Map();
export function geometryOf(name) {
  if (geoCache.has(name)) return geoCache.get(name);
  const s = A.world[name];
  if (!s) return null;
  let found = null;
  s.traverse((o) => { if (!found && o.isMesh) found = { geometry: o.geometry.clone().applyMatrix4(o.matrixWorld), material: o.material }; });
  geoCache.set(name, found);
  return found;
}

// a rigged person: their own skeleton, sharing meshes and textures
export function person(kind) {
  const src = A.people[kind] || A.people.Barbarian || Object.values(A.people)[0];
  if (!src) return null;
  const p = SkeletonUtils.clone(src);
  const hide = /Shield|Sword|2H_|1H_|Axe|Staff|Crossbow|Dagger|Wand|Spellbook|Mug|Quiver|Arrow|Knife|Helmet|Hat|Cape/i;
  p.traverse((o) => {
    if (o.isMesh || o.isSkinnedMesh) o.frustumCulled = false;            // skinned bounds don't follow the rig
    if ((o.isMesh && !o.isSkinnedMesh) && hide.test(o.name)) o.visible = false;
  });
  return p;
}

export function tool(name) {
  const s = A.tools[name];
  return s ? s.clone(true) : null;
}

export function bone(root, name) {
  let b = null;
  root.traverse((o) => { if (!b && o.isBone && o.name === name) b = o; });
  return b;
}
