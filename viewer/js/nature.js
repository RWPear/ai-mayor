// The woods and the stones on the hill. Trees come down in the order the scene says (nearest the shack
// first) and leave stumps; stones disappear from the hill as they're hauled away.
import * as THREE from "three";
import { C, M } from "./materials.js";
import { rng, hash, distToPath, fbm } from "./noise.js";
import { V } from "./terrain.js";
import * as BufferGeometryUtils from "three/addons/utils/BufferGeometryUtils.js";

export class Nature {
  constructor(scene, land, S) {
    this.land = land; this.group = new THREE.Group(); scene.add(this.group);
    this.trees = S.trees_all || S.trees;
    this.stones = S.stones_all || S.stones;
    const n = this.trees.length;
    const flat = { flatShading: true, roughness: 0.95 };
    this.trunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.22, 0.38, 3, 6).translate(0, 1.5, 0), M(C.trunk, null, flat), n);
    this.blob = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1.6, 0), M(0xffffff, null, flat), n * 3);
    this.cone = new THREE.InstancedMesh(new THREE.ConeGeometry(2.1, 3.6, 7), M(0xffffff, null, flat), n * 3);
    this.stump = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.34, 0.42, 0.5, 7).translate(0, 0.25, 0), M(0x8a6a45, null, flat), n);
    for (const m of [this.trunk, this.blob, this.cone]) { m.castShadow = true; m.receiveShadow = true; }
    this.stump.receiveShadow = true;
    this.rock = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(0.8, 0), M(0xffffff, null, flat), this.stones.length);
    this.rock.castShadow = this.rock.receiveShadow = true;
    const col = new THREE.Color();
    this.kind = this.trees.map((t, i) => (hash(i * 7 + 3) % 10 < 4 ? "pine" : "leaf"));
    this.trees.forEach((t, i) => {
      const R = rng(i + 100);
      for (let k = 0; k < 3; k++) {
        const autumn = hash(i * 13 + 5) % 100 < 12;                  // a few trees turning, for colour
        col.setHex(autumn ? [C.autumn1, C.autumn2][(i + k) % 2] : [C.leaf1, C.leaf2, C.leaf3][(i + k) % 3]).offsetHSL((R() - 0.5) * 0.03, 0, (R() - 0.5) * 0.08);
        this.blob.setColorAt(i * 3 + k, col);
        col.setHex(C.pine).offsetHSL(0, 0, (R() - 0.5) * 0.06);
        this.cone.setColorAt(i * 3 + k, col);
      }
    });
    this.stones.forEach((s, i) => { col.setHex(C.rock).offsetHSL(0, 0, (rng(i)() - 0.5) * 0.15); this.rock.setColorAt(i, col); });
    // outcrops: big grey rocks that stay however much stone is hauled, so the hill always reads as rocky
    const H = S.terrain.hill, Rr = rng(77), n2 = 26;
    this.outcrop = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 0), M(0xffffff, null, flat), n2);
    const o2 = new THREE.Object3D();
    for (let i = 0; i < n2; i++) {
      const a = Rr() * Math.PI * 2, d = H.r * Math.sqrt(Rr()) * 0.85, x = H.pos[0] + Math.cos(a) * d, z = H.pos[1] + Math.sin(a) * d;
      const s = 1.4 + Rr() * 2.6 * (1 - d / H.r);
      o2.position.copy(V(x, z, land.height(x, z) + s * 0.25)); o2.rotation.set(Rr() * 3, Rr() * 3, Rr() * 3); o2.scale.set(s * (0.9 + Rr() * 0.5), s * (0.6 + Rr() * 0.5), s * (0.9 + Rr() * 0.5));
      o2.updateMatrix(); this.outcrop.setMatrixAt(i, o2.matrix);
      this.outcrop.setColorAt(i, col.setHex(C.rock).offsetHSL(0, -0.02, (Rr() - 0.45) * 0.12));
    }
    this.outcrop.castShadow = this.outcrop.receiveShadow = true;
    this.group.add(this.trunk, this.blob, this.cone, this.stump, this.rock, this.outcrop);
    this.felled = -1; this.hauled = -1;
    this.setFelled(S.trees_felled || 0); this.setHauled(S.stones_hauled || 0);
    this.buildDecor(S);
    this.buildFarForest();
  }

  // trees on the land that rose from the clouds: a whole forest on the silver grove, a scatter elsewhere
  buildFarForest() {
    const I = this.land.island, R = rng(77), spots = [];
    const per = { grove: 260, meadow: 30, skygarden: 60, springs: 25, ruins: 40, point: 15, cliffs: 10, crystals: 8 };
    for (const L of I.lobes) {
      const want = per[L.id] ?? 30;
      for (let k = 0, n = 0; k < want * 30 && n < want; k++) {
        const a = R() * 6.283, r = L.r * Math.sqrt(R()) * 0.95, x = L.pos[0] + Math.cos(a) * r, z = L.pos[1] + Math.sin(a) * r;
        if (I.sd(x, z) < 6 || I.base_sd(x, z) > -4) continue;
        if (L.id !== "grove" && fbm(x * 0.03 + 40, z * 0.03, 2) < 0.05) continue;
        spots.push([x, z, this.land.height(x, z), 0.7 + R() * 0.7, L.id]); n++;
      }
    }
    const n = Math.max(1, spots.length);
    const cone = (r, h, y) => new THREE.ConeGeometry(r, h, 5).translate(0, y, 0);
    const geo = BufferGeometryUtils.mergeGeometries([new THREE.CylinderGeometry(0.5, 0.7, 3, 4).translate(0, 1.5, 0), cone(3.4, 6, 5), cone(2.6, 5, 8.2), cone(1.7, 4, 11)]);
    const mesh = new THREE.InstancedMesh(geo, M(0xffffff, null, { flatShading: true }), n);
    const o = new THREE.Object3D(), col = new THREE.Color();
    spots.forEach(([x, z, y, sc, id], i) => {
      o.position.copy(V(x, z, y - 0.3)); o.rotation.set(0, i, 0); o.scale.set(sc * 0.9, sc * 1.1, sc * 0.9); o.updateMatrix(); mesh.setMatrixAt(i, o.matrix);
      mesh.setColorAt(i, col.setHex(id === "grove" ? (i % 3 ? 0xa9cdb4 : 0x8fbf98) : id === "skygarden" ? C.leaf1 : C.pine).offsetHSL(0, 0, ((hash(i) % 100) / 100 - 0.5) * 0.08));
    });
    mesh.count = spots.length;
    mesh.castShadow = true; mesh.receiveShadow = true;
    this.group.add(mesh); this.farForest = mesh;
  }

  // the little things that make a field look lived-in from far off: bushes, flowers, pebbles, a lone tree here
  // and there. Never on the river, the road, or (see clearAround) under anything built.
  buildDecor(S) {
    const land = this.land, R = rng(2024), flat = { flatShading: true, roughness: 1 };
    const spots = { bush: [], flower: [], pebble: [], lone: [] };
    const okAt = (x, z, gap) => distToPath(x, z, land.river.path) > land.river.width / 2 + gap && distToPath(x, z, land.road.path) > land.road.width + gap
      && Math.hypot(x, z) > 10 && Math.hypot(x - land.woods.pos[0], z - land.woods.pos[1]) > land.woods.r * 1.05;
    for (let k = 0; k < 20000 && spots.bush.length + spots.flower.length < 560; k++) {
      const x = (R() - 0.5) * 620, z = (R() - 0.5) * 620;
      if (land.island.sd(x, z) < 5 || !okAt(x, z, 2)) continue;
      if (fbm(x * 0.03 + 5, z * 0.03, 2) + 0.15 < R() * 0.9) continue;          // in clumps, with open meadow between
      const roll = R();
      if (roll < 0.42) spots.bush.push([x, z, 0.6 + R() * 0.7]);
      else if (roll < 0.8) spots.flower.push([x, z, R()]);
      else if (roll < 0.93) spots.pebble.push([x, z, 0.3 + R() * 0.5]);
      else if (Math.hypot(x - land.field[0], z - land.field[1]) > 45) spots.lone.push([x, z, 0.8 + R() * 0.4]);
    }
    this.decor = spots;
    const n = (a) => Math.max(1, a.length);
    this.bush = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1, 0), M(0xffffff, null, flat), n(spots.bush));
    this.flower = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(0.14, 0), M(0xffffff, null, flat), n(spots.flower) * 5);
    this.pebble = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 0), M(0xffffff, null, flat), n(spots.pebble));
    this.loneTrunk = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.22, 0.38, 3, 6).translate(0, 1.5, 0), M(C.trunk, null, flat), n(spots.lone));
    this.loneTop = new THREE.InstancedMesh(new THREE.IcosahedronGeometry(1.7, 0), M(0xffffff, null, flat), n(spots.lone));
    const col = new THREE.Color(), FL = [0xf4f1e8, 0xf2d24b, 0xe8789a, 0x9fb8f0, 0xf09a4a];
    spots.bush.forEach((b, i) => this.bush.setColorAt(i, col.setHex([C.leaf1, C.leaf2, C.leaf3][i % 3]).offsetHSL(0, 0, (rng(i)() - 0.5) * 0.08)));
    spots.flower.forEach((f, i) => { for (let k = 0; k < 5; k++) this.flower.setColorAt(i * 5 + k, col.setHex(FL[Math.floor(f[2] * FL.length)])); });
    spots.pebble.forEach((p, i) => this.pebble.setColorAt(i, col.setHex(C.rock).offsetHSL(0, 0, (rng(i + 5)() - 0.3) * 0.1)));
    spots.lone.forEach((t, i) => this.loneTop.setColorAt(i, col.setHex(hash(i * 3) % 5 === 0 ? C.autumn1 : [C.leaf1, C.leaf2][i % 2])));
    for (const m of [this.bush, this.pebble, this.loneTrunk, this.loneTop]) { m.castShadow = true; m.receiveShadow = true; }
    this.group.add(this.bush, this.flower, this.pebble, this.loneTrunk, this.loneTop);
    this.clearAround([]);
  }

  clearAround(lots) {
    const land = this.land, o = new THREE.Object3D(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
    const under = (x, z) => lots.some((L) => Math.abs(x - L.pos[0]) < L.hw + 2.5 && Math.abs(z - L.pos[1]) < L.hd + 2.5);
    const { bush, flower, pebble, lone } = this.decor;
    bush.forEach(([x, z, s], i) => {
      if (under(x, z)) { this.bush.setMatrixAt(i, zero); return; }
      const R = rng(i + 7); o.position.copy(V(x, z, land.height(x, z) + s * 0.3)); o.rotation.set(R() * 3, R() * 3, R() * 3); o.scale.set(s * 1.2, s * 0.8, s); o.updateMatrix(); this.bush.setMatrixAt(i, o.matrix);
    });
    flower.forEach(([x, z], i) => {
      const R = rng(i + 99), gone = under(x, z);
      for (let k = 0; k < 5; k++) {
        if (gone) { this.flower.setMatrixAt(i * 5 + k, zero); continue; }
        const fx = x + (R() - 0.5) * 1.4, fz = z + (R() - 0.5) * 1.4;
        o.position.copy(V(fx, fz, land.height(fx, fz) + 0.16)); o.rotation.set(0, 0, 0); o.scale.setScalar(0.8 + R() * 0.6); o.updateMatrix(); this.flower.setMatrixAt(i * 5 + k, o.matrix);
      }
    });
    pebble.forEach(([x, z, s], i) => {
      if (under(x, z)) { this.pebble.setMatrixAt(i, zero); return; }
      const R = rng(i + 3); o.position.copy(V(x, z, land.height(x, z) + s * 0.15)); o.rotation.set(R() * 3, R() * 3, R() * 3); o.scale.set(s * 1.3, s * 0.6, s); o.updateMatrix(); this.pebble.setMatrixAt(i, o.matrix);
    });
    lone.forEach(([x, z, s], i) => {
      if (under(x, z)) { this.loneTrunk.setMatrixAt(i, zero); this.loneTop.setMatrixAt(i, zero); return; }
      const y = land.height(x, z);
      o.position.copy(V(x, z, y - 0.1)); o.rotation.set(0, i, 0); o.scale.setScalar(s); o.updateMatrix(); this.loneTrunk.setMatrixAt(i, o.matrix);
      o.position.copy(V(x, z, y + 4.1 * s)); o.scale.set(s * 1.2, s * 1.35, s * 1.2); o.updateMatrix(); this.loneTop.setMatrixAt(i, o.matrix);
    });
    for (const m of [this.bush, this.flower, this.pebble, this.loneTrunk, this.loneTop]) m.instanceMatrix.needsUpdate = true;
  }

  setFelled(f) {
    f = Math.max(0, Math.min(this.trees.length, Math.round(f)));
    if (f === this.felled) return;
    this.felled = f;
    const o = new THREE.Object3D(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
    this.trees.forEach(([x, z, s], i) => {
      const y = this.land.height(x, z), R = rng(i + 100), gone = i < f, pine = this.kind[i] === "pine";
      o.position.copy(V(x, z, y - 0.1)); o.rotation.set(0, R() * 6, 0); o.scale.setScalar(gone ? 0.0001 : s * (pine ? 1.15 : 1));
      o.updateMatrix(); this.trunk.setMatrixAt(i, o.matrix);
      o.scale.setScalar(gone ? s : 0.0001); o.updateMatrix(); this.stump.setMatrixAt(i, o.matrix);
      for (let k = 0; k < 3; k++) {
        if (gone) { this.blob.setMatrixAt(i * 3 + k, zero); this.cone.setMatrixAt(i * 3 + k, zero); continue; }
        if (pine) {
          o.position.copy(V(x, z, y + (2.6 + k * 1.7) * s)); o.scale.set(s * (1.25 - k * 0.3), s * 1, s * (1.25 - k * 0.3)); o.rotation.set(0, R() * 6, 0);
          o.updateMatrix(); this.cone.setMatrixAt(i * 3 + k, o.matrix); this.blob.setMatrixAt(i * 3 + k, zero);
        } else {
          const a = k * 2.1 + R(), r = k ? 0.9 : 0;
          o.position.copy(V(x + Math.cos(a) * r * s, z + Math.sin(a) * r * s, y + (3.6 + (k ? 0.2 : 1.1) + R() * 0.4) * s));
          o.scale.setScalar(s * (k ? 0.85 : 1.15) * (0.9 + R() * 0.25)); o.rotation.set(R() * 3, R() * 3, R() * 3);
          o.updateMatrix(); this.blob.setMatrixAt(i * 3 + k, o.matrix); this.cone.setMatrixAt(i * 3 + k, zero);
        }
      }
    });
    for (const m of [this.trunk, this.blob, this.cone, this.stump]) m.instanceMatrix.needsUpdate = true;
  }

  setHauled(h) {
    h = Math.max(0, Math.min(this.stones.length, Math.round(h)));
    if (h === this.hauled) return;
    this.hauled = h;
    const o = new THREE.Object3D(), zero = new THREE.Matrix4().makeScale(0, 0, 0);
    this.stones.forEach(([x, z, s], i) => {
      if (i < h) { this.rock.setMatrixAt(i, zero); return; }
      const R = rng(i + 50);
      o.position.copy(V(x, z, this.land.height(x, z) + 0.2)); o.rotation.set(R() * 3, R() * 3, R() * 3);
      o.scale.set(s * (0.8 + R() * 0.6), s * (0.5 + R() * 0.4), s * (0.8 + R() * 0.6)); o.updateMatrix(); this.rock.setMatrixAt(i, o.matrix);
    });
    this.rock.instanceMatrix.needsUpdate = true;
  }
}
