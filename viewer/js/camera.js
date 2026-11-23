// Ways to watch: follow Aldric, let the director cut between what's happening, walk around at eye height,
// look down on the place like Prison Architect, orbit freely, or stand where a recorder stands.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { V } from "./terrain.js";

export const MODES = ["follow", "director", "walk", "top", "orbit", "recorder"];
const LABEL = { follow: "Following Aldric", director: "Director", walk: "Walking", top: "From above", orbit: "Free camera", recorder: "Recorder" };

export class Rig {
  constructor(camera, dom, land) {
    this.camera = camera; this.dom = dom; this.land = land;
    this.controls = new OrbitControls(camera, dom);
    this.controls.enableDamping = true; this.controls.maxPolarAngle = Math.PI * 0.48; this.controls.minDistance = 3; this.controls.maxDistance = 420;
    this.mode = "follow"; this.keys = {}; this.yaw = 0; this.pitch = -0.05;
    this.top = { x: 30, z: 0, h: 70 };
    this.shot = null; this.shotLeft = 0; this.recorder = null;
    this.lastTarget = null;
    addEventListener("keydown", (e) => { if (!/^(INPUT|SELECT|TEXTAREA)$/.test(e.target.tagName)) this.keys[e.code] = true; });
    addEventListener("keyup", (e) => { this.keys[e.code] = false; });
    let drag = null;
    dom.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; if (this.mode === "walk" && e.pointerType === "mouse") dom.requestPointerLock?.(); });
    addEventListener("pointerup", () => { drag = null; });
    addEventListener("pointermove", (e) => {
      const locked = document.pointerLockElement === dom;
      if (this.mode === "walk" && (locked || drag)) {
        const dx = locked ? e.movementX : e.clientX - drag.x, dy = locked ? e.movementY : e.clientY - drag.y;
        this.yaw -= dx * 0.0035; this.pitch = Math.max(-1.3, Math.min(1.2, this.pitch - dy * 0.0035));
        if (drag) drag = { x: e.clientX, y: e.clientY };
      } else if (this.mode === "top" && drag) {
        const k = this.top.h / 600;
        this.top.x -= (e.clientX - drag.x) * k; this.top.z += (e.clientY - drag.y) * k; drag = { x: e.clientX, y: e.clientY };
      }
    });
    dom.addEventListener("wheel", (e) => { if (this.mode === "top") { this.top.h = Math.max(18, Math.min(220, this.top.h * (1 + Math.sign(e.deltaY) * 0.1))); e.preventDefault(); } }, { passive: false });
  }

  label() { return this.mode === "recorder" && this.recorder ? `Recorder: ${this.recorder.name}` : LABEL[this.mode]; }

  set(mode, opts = {}) {
    this.mode = mode;
    this.controls.enabled = mode === "follow" || mode === "orbit";
    if (document.pointerLockElement && mode !== "walk") document.exitPointerLock?.();
    if (mode === "walk") {
      const p = opts.from || this.controls.target;
      this.walkPos = new THREE.Vector3(p.x, 0, p.z);
      const d = new THREE.Vector3().subVectors(this.controls.target, this.camera.position);
      this.yaw = Math.atan2(-d.x, -d.z); this.pitch = -0.05;
    }
    if (mode === "top") { const t = this.controls.target; this.top.x = t.x; this.top.z = -t.z; }
    if (mode === "recorder") this.recorder = opts.recorder || this.recorder;
    if (mode === "director") this.shotLeft = 0;
    this.camera.fov = mode === "top" ? 30 : mode === "recorder" && this.recorder?.fov ? this.recorder.fov : mode === "walk" ? 70 : 50;
    this.camera.updateProjectionMatrix();
  }

  lookAt(pos, dist = 14, height = null) {
    const t = V(pos[0], pos[1], this.land.height(pos[0], pos[1]) + 1.2);
    this.controls.target.copy(t);
    this.camera.position.copy(t).add(new THREE.Vector3(dist * 0.7, height ?? dist * 0.55, dist * 0.7));
  }

  // king: {pos:[x,z]}, director gets a list of candidate shots for "now"
  update(dt, king, director) {
    const c = this.camera, L = this.land;
    const kp = V(king.pos[0], king.pos[1], L.height(king.pos[0], king.pos[1]) + 1.2);
    if (this.mode === "follow") {
      if (this.lastTarget) c.position.add(new THREE.Vector3().subVectors(kp, this.lastTarget).multiplyScalar(1));
      this.controls.target.copy(kp);
      this.lastTarget = kp.clone();
      const ground = L.height(c.position.x, -c.position.z) + 1.5;
      if (c.position.y < ground) c.position.y = ground;
      this.controls.update();
      return;
    }
    this.lastTarget = null;
    if (this.mode === "orbit") { this.controls.update(); return; }
    if (this.mode === "walk") {
      const sp = (this.keys.ShiftLeft || this.keys.ShiftRight ? 7 : 2.6) * dt;
      const f = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw)), r = new THREE.Vector3(-f.z, 0, f.x);
      if (this.keys.KeyW || this.keys.ArrowUp) this.walkPos.addScaledVector(f, sp);
      if (this.keys.KeyS || this.keys.ArrowDown) this.walkPos.addScaledVector(f, -sp);
      if (this.keys.KeyA || this.keys.ArrowLeft) this.walkPos.addScaledVector(r, -sp);
      if (this.keys.KeyD || this.keys.ArrowRight) this.walkPos.addScaledVector(r, sp);
      const y = Math.max(L.height(this.walkPos.x, -this.walkPos.z), -0.4) + 1.7;
      c.position.set(this.walkPos.x, y + Math.sin(performance.now() / 160) * 0.015 * (sp > 0.05 ? 1 : 0), this.walkPos.z);
      c.rotation.set(this.pitch, this.yaw, 0, "YXZ");
      return;
    }
    if (this.mode === "top") {
      const sp = this.top.h * 0.9 * dt;
      if (this.keys.KeyW || this.keys.ArrowUp) this.top.z += sp;
      if (this.keys.KeyS || this.keys.ArrowDown) this.top.z -= sp;
      if (this.keys.KeyA || this.keys.ArrowLeft) this.top.x -= sp;
      if (this.keys.KeyD || this.keys.ArrowRight) this.top.x += sp;
      c.position.copy(V(this.top.x, this.top.z - this.top.h * 0.18, this.top.h));
      c.lookAt(V(this.top.x, this.top.z, 0));
      return;
    }
    if (this.mode === "recorder" && this.recorder) { this.applyRecorder(this.recorder, king); return; }
    if (this.mode === "director") {
      this.shotLeft -= dt;
      if (!this.shot || this.shotLeft <= 0) { this.shot = director(); this.shotLeft = this.shot.hold; this.shot.age = 0; }
      const s = this.shot; s.age += dt;
      const target = s.follow ? kp : V(s.pos[0], s.pos[1], L.height(s.pos[0], s.pos[1]) + (s.lift || 1.2));
      const a = s.angle + s.age * s.spin;
      const pos = target.clone().add(new THREE.Vector3(Math.cos(a) * s.dist, s.height + s.age * (s.rise || 0), Math.sin(a) * s.dist));
      const ground = L.height(pos.x, -pos.z) + 1.2;
      if (pos.y < ground) pos.y = ground;
      if (s.age < 0.05) c.position.copy(pos); else c.position.lerp(pos, Math.min(1, dt * 2));
      c.lookAt(target);
    }
  }

  applyRecorder(r, king) {
    const c = this.camera;
    if (r.follow === "king") {
      const kp = V(king.pos[0], king.pos[1], this.land.height(king.pos[0], king.pos[1]) + 1.2);
      c.position.copy(kp).add(new THREE.Vector3(...(r.offset || [10, 8, 10])));
      c.lookAt(kp);
    } else {
      c.position.copy(V(r.pos[0], r.pos[2], r.pos[1]));
      c.lookAt(V(r.look[0], r.look[2], r.look[1]));
    }
    if (r.fov && c.fov !== r.fov) { c.fov = r.fov; c.updateProjectionMatrix(); }
  }
}
