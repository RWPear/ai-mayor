// The woods and the stones on the hill. Trees come down in the order the scene says (nearest the shack
// first) and leave stumps; stones disappear from the hill as they're hauled away.
import * as THREE from "three";
import { C, M } from "./materials.js";
import { rng, hash } from "./noise.js";
import { V } from "./terrain.js";

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
        col.setHex([C.leaf1, C.leaf2, C.leaf3][(i + k) % 3]).offsetHSL((R() - 0.5) * 0.03, 0, (R() - 0.5) * 0.08);
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
      this.outcrop.setColorAt(i, col.setHex(C.rock).offsetHSL(0, -0.02, (Rr() - 0.6) * 0.15));
    }
    this.outcrop.castShadow = this.outcrop.receiveShadow = true;
    this.group.add(this.trunk, this.blob, this.cone, this.stump, this.rock, this.outcrop);
    this.felled = -1; this.hauled = -1;
    this.setFelled(S.trees_felled || 0); this.setHauled(S.stones_hauled || 0);
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
