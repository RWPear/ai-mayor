// The land: height, ground colour (with paths worn by people), the river, grass in the wind, sky, sun, weather.
import * as THREE from "three";
import { C, TEX, FLAT } from "./materials.js";
import { fbm, smoothstep, distToPath, distToSeg, rng, clamp, hash } from "./noise.js";

export const V = (x, z, y = 0) => new THREE.Vector3(x, y, -z);   // world (x east, z north) -> three (x, y, -z)

export function farColor(x, z, c = new THREE.Color()) {
  return c.setHex(C.grass).lerp(new THREE.Color(C.grassDry), clamp(fbm(x * 0.04 + 9, z * 0.04, 3) + 0.35, 0, 1) * 0.7)
    .lerp(new THREE.Color(C.grassDark), clamp(fbm(x * 0.006, z * 0.006, 2) + 0.2, 0, 1) * 0.5);
}

// the country beyond the map: flat at the edge, rolling further out, blue hills on the horizon
export function farHeight(x, z) {
  const r = Math.hypot(x, z);
  return -0.6 + fbm(x * 0.004, z * 0.004, 3) * 14 * smoothstep(240, 900, r) + Math.max(0, fbm(x * 0.0015 + 4, z * 0.0015, 3) + 0.2) * 220 * smoothstep(650, 1500, r);
}

export class Land {
  constructor(scene, S, quality) {
    this.scene = scene; this.S = S; this.q = quality;
    this.group = new THREE.Group(); scene.add(this.group);
    this.uniforms = { uTime: { value: 0 }, uWind: { value: 0.6 } };
    this.lots = [];
    this.setTerrain(S);
    this.buildGround();
    this.buildWater();
    this.buildGrass();
    this.buildSky();
    this.buildRain();
  }

  setTerrain(S) {
    this.river = S.terrain.river; this.road = S.terrain.road; this.hill = S.terrain.hill; this.woods = S.terrain.woods;
    this.field = (S.places.find((p) => p.id === "field") || { pos: [38, 6] }).pos;
  }

  // the one height function everything stands on
  height(x, z) {
    const H = this.hill;
    let h = fbm(x * 0.012, z * 0.012, 4) * 2.4 + fbm(x * 0.05, z * 0.05, 2) * 0.35;
    const flat = smoothstep(30, 70, Math.hypot(x - this.field[0], z - this.field[1])) * smoothstep(8, 24, Math.hypot(x, z));
    h *= 0.25 + 0.75 * flat;                                         // the field and the shack sit on flat ground
    const dh = Math.hypot(x - H.pos[0], z - H.pos[1]) / (H.r * 1.35);
    if (dh < 1) h += H.height * Math.pow(1 - dh * dh, 1.6) + fbm(x * 0.15, z * 0.15, 2) * 0.8 * (1 - dh);
    const dr = distToPath(x, z, this.river.path);
    const w = this.river.width / 2;
    h -= 2.4 * (1 - smoothstep(w * 0.6, w + 5, dr));                 // the river cuts a bed
    if (dr < w + 9) h = Math.min(h, 0.2 + (dr - w) * 0.12);           // gentle banks
    const dw = Math.hypot(x - this.woods.pos[0], z - this.woods.pos[1]) / (this.woods.r * 1.3);
    if (dw < 1) h += 0.8 * (1 - dw);                                 // the woods rise a little
    const r = Math.hypot(x, z);
    if (r > 175) h = h + (farHeight(x, z) - h) * smoothstep(175, 202, r);   // blend into the country beyond
    return h;
  }

  buildGround() {
    // the flat look: big low-poly facets (each triangle one colour, a little lift and tilt to catch the light)
    const size = this.S.terrain.ground.size[0], seg = FLAT ? (this.q === "low" ? 120 : 210) : (this.q === "low" ? 160 : 300);
    let g = new THREE.PlaneGeometry(size, size, seg, seg);
    g.rotateX(-Math.PI / 2);
    const pos = g.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i), z = -pos.getZ(i); const r = Math.hypot(x, z);
      const jig = FLAT ? (hash(Math.round(x * 10) * 7919 + Math.round(z * 10)) % 1000 / 1000 - 0.5) * 0.22 : 0;
      pos.setY(i, r > 205 ? farHeight(x, z) - 0.35 : this.height(x, z) + jig + (r > 196 ? 0.06 : 0));
    }
    if (FLAT) g = g.toNonIndexed();
    g.computeVertexNormals();
    g.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(g.attributes.position.count * 3), 3));
    this.ground = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: FLAT }));
    this.ground.receiveShadow = true;
    this.group.add(this.ground);
    this.paint([]);
  }

  // ground colour: grass with patches, sand at the river, rock on the hill, mud at the camp, and the paths
  // people wear (from the scene's trails: the more feet, the browner and wider)
  paint(trails, lots = []) {
    const g = this.ground.geometry, pos = g.attributes.position, col = g.attributes.color;
    const c = new THREE.Color(), grass = new THREE.Color(C.grass), dry = new THREE.Color(C.grassDry), dark = new THREE.Color(C.grassDark);
    const sand = new THREE.Color(C.sand), rock = new THREE.Color(C.rock), mud = new THREE.Color(C.mud), dirt = new THREE.Color(C.dirt);
    const maxWear = Math.max(1, ...trails.map((t) => t.wear));
    const camp = (this.S.places.find((p) => p.id === "camp") || {}).pos;
    const stepN = FLAT ? 3 : 1;                                   // flat look: one colour per triangle, at its middle
    for (let i0 = 0; i0 < pos.count; i0 += stepN) {
      let x = pos.getX(i0), z = -pos.getZ(i0), y = pos.getY(i0);
      if (FLAT) { x = (x + pos.getX(i0 + 1) + pos.getX(i0 + 2)) / 3; z = -(pos.getZ(i0) + pos.getZ(i0 + 1) + pos.getZ(i0 + 2)) / 3; y = (y + pos.getY(i0 + 1) + pos.getY(i0 + 2)) / 3; }
      const i = i0;
      const n = fbm(x * 0.04 + 9, z * 0.04, 3);
      c.copy(grass).lerp(dry, clamp(n + 0.35, 0, 1) * 0.7);
      const dw = Math.hypot(x - this.woods.pos[0], z - this.woods.pos[1]);
      c.lerp(dark, (1 - smoothstep(this.woods.r * 0.6, this.woods.r * 1.25, dw)) * 0.75);
      const dr = distToPath(x, z, this.river.path);
      c.lerp(sand, 1 - smoothstep(this.river.width / 2, this.river.width / 2 + 4, dr));
      const hillUp = clamp((y - 3.5) / 7, 0, 1) * (1 - smoothstep(this.hill.r * 1.1, this.hill.r * 1.5, Math.hypot(x - this.hill.pos[0], z - this.hill.pos[1])));
      c.lerp(rock, hillUp * (0.45 + 0.4 * clamp(fbm(x * 0.2, z * 0.2) + 0.5, 0, 1)));
      const droad = distToPath(x, z, this.road.path);
      c.lerp(dirt, (1 - smoothstep(this.road.width * 0.35, this.road.width * 0.75, droad)) * 0.95);
      if (camp && (this.S.tents || []).length) c.lerp(mud, (1 - smoothstep(10, 26, Math.hypot(x - camp[0], z - camp[1]))) * 0.75);
      if (Math.hypot(x, z) < 9) c.lerp(dirt, (1 - Math.hypot(x, z) / 9) * 0.7);         // trodden around the shack
      for (const t of trails) {
        const w = 0.6 + 1.6 * t.wear / maxWear;
        const d = distToSeg(x, z, t.from, t.to);
        if (d < w + 1) c.lerp(dirt, (1 - smoothstep(w * 0.4, w + 1, d)) * (0.35 + 0.55 * t.wear / maxWear));
      }
      const rr = Math.hypot(x, z);
      if (rr > 165) c.lerp(farColor(x, z), smoothstep(165, 200, rr));                 // meet the country beyond seamlessly
      for (const L of lots) {                                                        // bare earth under buildings
        if (Math.abs(x - L.pos[0]) < L.hw + 1.5 && Math.abs(z - L.pos[1]) < L.hd + 1.5) c.lerp(dirt, 0.55);
      }
      if (FLAT) {                                                                    // a touch of variety per facet
        const v = (hash(i0 * 31 + 7) % 1000) / 1000 - 0.5;
        c.offsetHSL(v * 0.012, 0, v * 0.035);
        for (let k = 0; k < 3; k++) col.setXYZ(i + k, c.r, c.g, c.b);
      } else col.setXYZ(i, c.r, c.g, c.b);
    }
    col.needsUpdate = true;
    this.lots = lots;
  }

  buildWater() {
    const P = this.river.path, w = this.river.width / 2 + 1.5;
    const pts = [];
    for (let i = 0; i < P.length - 1; i++) for (let k = 0; k < 12; k++) {
      const t = k / 12; pts.push([P[i][0] + (P[i + 1][0] - P[i][0]) * t, P[i][1] + (P[i + 1][1] - P[i][1]) * t]);
    }
    pts.push(P[P.length - 1]);
    const verts = [], uvs = [], idx = [];
    let along = 0;
    pts.forEach((p, i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      const dx = b[0] - a[0], dz = b[1] - a[1], L = Math.hypot(dx, dz) || 1, nx = -dz / L * w, nz = dx / L * w;
      if (i) along += Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]);
      verts.push(p[0] + nx, -0.55, -(p[1] + nz), p[0] - nx, -0.55, -(p[1] - nz));
      uvs.push(0, along / 12, 1, along / 12);
      if (i) { const k = i * 2; idx.push(k - 2, k - 1, k, k - 1, k + 1, k); }
    });
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    g.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    g.setIndex(idx); g.computeVertexNormals();
    TEX.water.wrapS = TEX.water.wrapT = THREE.RepeatWrapping;
    this.water = new THREE.Mesh(g, FLAT
      ? new THREE.MeshStandardMaterial({ color: C.water, roughness: 0.35, metalness: 0, transparent: true, opacity: 0.92,
        normalMap: TEX.water, normalScale: new THREE.Vector2(0.12, 0.12), emissive: 0x0b3540, emissiveIntensity: 0.6 })
      : new THREE.MeshStandardMaterial({
        color: C.water, roughness: 0.12, metalness: 0.05, transparent: true, opacity: 0.88, normalMap: TEX.water,
        normalScale: new THREE.Vector2(0.35, 0.35) }));
    this.water.receiveShadow = true;
    this.group.add(this.water);
  }

  // grass: a dense patch that travels with the camera. Each blade's place, height and colour come from a texture
  // of the land (height, where grass grows, how dry it is), so it hugs the ground, stops at paths, the river and
  // buildings, and costs nothing beyond the 45 m you can actually see it in.
  buildGrass() {
    this.gN = 384;
    this.gData = new Float32Array(this.gN * this.gN * 4);
    this.gTex = new THREE.DataTexture(this.gData, this.gN, this.gN, THREE.RGBAFormat, THREE.FloatType);
    this.gTex.minFilter = this.gTex.magFilter = THREE.NearestFilter;
    const blades = 6, v = [], shade = [];
    const R = rng(4);
    for (let k = 0; k < blades; k++) {
      const a = R() * Math.PI, ox = (R() - 0.5) * 0.35, oz = (R() - 0.5) * 0.35, h = 0.28 + R() * 0.32, w = 0.035 + R() * 0.02, bend = (R() - 0.5) * 0.25;
      const cx = Math.cos(a) * w, cz = Math.sin(a) * w;
      // two triangles, narrowing to a tip that leans a little
      v.push(ox - cx, 0, oz - cz, ox + cx, 0, oz + cz, ox + cx * 0.4 + bend * 0.5, h * 0.55, oz + cz * 0.4,
             ox - cx, 0, oz - cz, ox + cx * 0.4 + bend * 0.5, h * 0.55, oz + cz * 0.4, ox + bend, h, oz);
      shade.push(0, 0, 0.55, 0, 0.55, 1);
    }
    const base = new THREE.BufferGeometry();
    base.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
    base.setAttribute("aShade", new THREE.Float32BufferAttribute(shade, 1));
    const nrm = []; for (let i = 0; i < v.length / 3; i++) nrm.push(0, 1, 0);       // lit like the ground under it
    base.setAttribute("normal", new THREE.Float32BufferAttribute(nrm, 3));
    const geo = new THREE.InstancedBufferGeometry().copy(base);
    this.gSpacing = this.q === "low" ? 0.9 : 0.55;
    const half = Math.floor((this.q === "low" ? 32 : 44) / this.gSpacing);
    const cells = [];
    for (let i = -half; i <= half; i++) for (let j = -half; j <= half; j++) if (i * i + j * j <= half * half) cells.push(i, j);
    geo.setAttribute("aCell", new THREE.InstancedBufferAttribute(new Float32Array(cells), 2));
    geo.instanceCount = cells.length / 2;
    this.gU = { uGround: { value: this.gTex }, uOrigin: { value: new THREE.Vector2() }, uSpacing: { value: this.gSpacing },
      uRadius: { value: half * this.gSpacing }, uSize: { value: this.S.terrain.ground.size[0] },
      uGreen: { value: new THREE.Color(C.grass) }, uDry: { value: new THREE.Color(C.grassDry) } };
    const mat = new THREE.MeshLambertMaterial({ color: 0xffffff, side: THREE.DoubleSide });
    mat.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, this.gU, { uTime: this.uniforms.uTime, uWind: this.uniforms.uWind });
      sh.vertexShader = `
        uniform sampler2D uGround; uniform vec2 uOrigin; uniform float uSpacing, uRadius, uSize, uTime, uWind;
        uniform vec3 uGreen, uDry;
        attribute vec2 aCell; attribute float aShade; varying vec3 vGrass;
        float gh(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        vec4 ground(vec2 xz) {                      // manual bilinear (float textures sample nearest)
          float n = float(textureSize(uGround, 0).x);
          vec2 t = (xz / uSize + 0.5) * n - 0.5, i = floor(t), f = t - i;
          vec4 a = texelFetch(uGround, ivec2(clamp(i, 0.0, n - 1.0)), 0), b = texelFetch(uGround, ivec2(clamp(i + vec2(1, 0), 0.0, n - 1.0)), 0);
          vec4 c = texelFetch(uGround, ivec2(clamp(i + vec2(0, 1), 0.0, n - 1.0)), 0), d = texelFetch(uGround, ivec2(clamp(i + vec2(1, 1), 0.0, n - 1.0)), 0);
          return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
        }
      ` + sh.vertexShader.replace("#include <begin_vertex>", `
        vec2 cell = uOrigin + aCell * uSpacing;
        vec2 id = floor(cell / uSpacing + 0.5);
        float r1 = gh(id), r2 = gh(id + 7.13), r3 = gh(id + 3.71), r4 = gh(id + 9.97), r5 = gh(id + 1.37);
        vec2 xz = cell + (vec2(r1, r2) - 0.5) * uSpacing * 1.6;
        vec4 g = ground(xz);
        float dist = distance(xz, cameraPosition.xz);
        float s = step(r3, g.g) * (1.0 - smoothstep(uRadius * 0.45, uRadius, dist)) * (0.5 + r4 * 0.6) * (0.75 + g.b * 0.4);
        float ang = r5 * 6.2831;
        vec3 p = position * s;
        p.xz = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * p.xz;
        float sway = sin(uTime * 1.6 + xz.x * 0.21 + xz.y * 0.13) * 0.6 + sin(uTime * 3.3 + xz.x * 0.7) * 0.2;
        p.x += sway * uWind * 0.18 * aShade * s; p.z += sway * uWind * 0.08 * aShade * s;
        vec3 transformed = vec3(xz.x, g.r - 0.02, xz.y) + p;
        vGrass = mix(uGreen, uDry, clamp(g.b, 0.0, 1.0)) * (0.62 + 0.55 * aShade) * (0.9 + r4 * 0.2);
      `);
      sh.fragmentShader = "varying vec3 vGrass;\n" + sh.fragmentShader
        .replace("vec4 diffuseColor = vec4( diffuse, opacity );", "vec4 diffuseColor = vec4( diffuse * vGrass, opacity );")
        .replace("#include <normal_fragment_begin>", "#include <normal_fragment_begin>\n normal = normalize(vNormal);");   // both sides lit like the ground
    };
    this.grass = new THREE.Mesh(geo, mat);
    this.grass.frustumCulled = false; this.grass.receiveShadow = true;
    this.group.add(this.grass);
    this.placeGrass([], []);
  }

  // where grass grows: not on the river, the road, worn paths, the hilltop rock or under buildings
  placeGrass(lots, paths = []) {
    const N = this.gN, size = this.S.terrain.ground.size[0], d = this.gData;
    const maxWear = Math.max(1, ...paths.map((t) => t.wear));
    const camp = (this.S.places.find((p) => p.id === "camp") || {}).pos;
    for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
      const tx = (i + 0.5) / N * size - size / 2, tz = (j + 0.5) / N * size - size / 2;   // three.js x, z
      const x = tx, z = -tz;                                                            // world x, z
      const y = this.height(x, z);
      let g = 1;
      if (distToPath(x, z, this.river.path) < this.river.width / 2 + 2) g = 0;
      if (distToPath(x, z, this.road.path) < this.road.width * 0.7) g = 0;
      if (Math.hypot(x, z) < 7) g *= 0.2;
      if (camp && Math.hypot(x - camp[0], z - camp[1]) < 22) g *= 0.35;
      g *= 1 - clamp((y - 6) / 6, 0, 1) * smoothstep(this.hill.r * 1.3, this.hill.r * 0.5, Math.hypot(x - this.hill.pos[0], z - this.hill.pos[1]));
      for (const L of lots) if (Math.abs(x - L.pos[0]) < L.hw + 1 && Math.abs(z - L.pos[1]) < L.hd + 1) { g = 0; break; }
      if (g > 0) for (const t of paths) {
        const w = 0.6 + 1.6 * t.wear / maxWear;
        if (distToSeg(x, z, t.from, t.to) < w + 0.4) { g *= 0.15 + 0.85 * (1 - t.wear / maxWear); }
      }
      const k = (j * N + i) * 4;
      d[k] = y; d[k + 1] = g * (FLAT ? 0.16 * clamp(fbm(x * 0.09 + 3, z * 0.09, 2) * 2 + 0.6, 0, 1.4) : 0.92); d[k + 2] = clamp(fbm(x * 0.04 + 9, z * 0.04, 3) + 0.35, 0, 1) * 0.7; d[k + 3] = 1;
    }
    this.gTex.needsUpdate = true;
  }

  // the sky: a gradient dome with a sun, slow clouds (thicker when it's grey) and the horizon colour the fog uses
  buildSky() {
    this.skyU = { top: { value: new THREE.Color() }, horizon: { value: new THREE.Color() }, sunDir: { value: new THREE.Vector3(0, 1, 0) },
      sunCol: { value: new THREE.Color() }, cover: { value: 0.3 }, night: { value: 0 }, time: this.uniforms.uTime };
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(4000, 32, 16), new THREE.ShaderMaterial({
      uniforms: this.skyU, side: THREE.BackSide, depthWrite: false, fog: false,
      vertexShader: `varying vec3 vDir; void main(){ vDir = normalize(position); gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); gl_Position.z = gl_Position.w; }`,
      fragmentShader: `
        uniform vec3 top, horizon, sunDir, sunCol; uniform float cover, night, time; varying vec3 vDir;
        float h(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float n(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
          return mix(mix(h(i), h(i+vec2(1,0)), f.x), mix(h(i+vec2(0,1)), h(i+vec2(1,1)), f.x), f.y); }
        float fbm(vec2 p){ float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { s += a * n(p); p *= 2.07; a *= 0.5; } return s; }
        void main(){
          vec3 d = normalize(vDir); float y = max(d.y, 0.0);
          vec3 col = mix(horizon, top, pow(y, 0.55));
          float s = max(dot(d, normalize(sunDir)), 0.0);
          col += sunCol * (pow(s, 900.0) * 6.0 + pow(s, 12.0) * 0.35) * (1.0 - night);
          if (d.y > 0.0) {
            vec2 uv = d.xz / (d.y + 0.15) * 1.6 + vec2(time * 0.006, time * 0.002);
            float c = smoothstep(1.0 - cover - 0.25, 1.0 - cover + 0.35, fbm(uv));
            vec3 cloud = mix(vec3(1.0), horizon * 0.85, 0.35) * (0.55 + 0.45 * (1.0 - night)) + sunCol * pow(s, 4.0) * 0.4;
            col = mix(col, cloud * (1.0 - 0.8 * night), c * smoothstep(0.0, 0.15, d.y) * 0.9);
          }
          gl_FragColor = vec4(col, 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }` }));
    this.sky.frustumCulled = false;
    this.scene.add(this.sky);
    // the land doesn't stop at the edge of the map: rolling country and blue hills to the horizon
    const far = new THREE.PlaneGeometry(5000, 5000, 120, 120); far.rotateX(-Math.PI / 2);
    const fp = far.attributes.position, fc = new Float32Array(fp.count * 3), g1 = new THREE.Color(C.grass), g2 = new THREE.Color(C.grassDark);
    for (let i = 0; i < fp.count; i++) {
      const x = fp.getX(i), z = -fp.getZ(i), r = Math.hypot(x, z);
      fp.setY(i, r < 232 ? farHeight(x, z) - 2.5 : farHeight(x, z));      // tucked just under the map's edge
      const c = farColor(x, z);
      fc[i * 3] = c.r; fc[i * 3 + 1] = c.g; fc[i * 3 + 2] = c.b;
    }
    far.setAttribute("color", new THREE.BufferAttribute(fc, 3)); far.computeVertexNormals();
    this.far = new THREE.Mesh(far, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 1, flatShading: FLAT }));
    this.far.receiveShadow = true;
    this.group.add(this.far);
    const R = rng(5), sp = [];
    for (let i = 0; i < 1400; i++) {
      const th = R() * Math.PI * 2, ph = Math.acos(R() * 0.95);
      sp.push(Math.sin(ph) * Math.cos(th) * 2000, Math.cos(ph) * 2000, Math.sin(ph) * Math.sin(th) * 2000);
    }
    const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.Float32BufferAttribute(sp, 3));
    this.stars = new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 2.2, sizeAttenuation: false, transparent: true, opacity: 0, fog: false }));
    this.scene.add(this.stars);
    this.hemi = FLAT ? new THREE.HemisphereLight(0xdcefff, 0xa89a6a, 1.0) : new THREE.HemisphereLight(0xcfe3ff, 0x40502c, 0.8);
    this.sun = new THREE.DirectionalLight(0xfff1dc, 2.4);
    this.sun.castShadow = true;
    const sm = this.q === "low" ? 1024 : 4096;
    this.sun.shadow.mapSize.set(sm, sm);
    Object.assign(this.sun.shadow.camera, { left: -90, right: 90, top: 90, bottom: -90, near: 1, far: 700 });
    this.sun.shadow.bias = -0.0004; this.sun.shadow.normalBias = 0.6;
    this.moon = new THREE.DirectionalLight(0x8fa8ff, 0.0);
    this.scene.add(this.hemi, this.sun, this.sun.target, this.moon);
    this.scene.fog = new THREE.FogExp2(0xcfd9e2, 0.0012);
  }

  buildRain() {
    const n = 2500, g = new THREE.BufferGeometry(), p = new Float32Array(n * 6);
    this.rainSeed = [];
    const R = rng(3);
    for (let i = 0; i < n; i++) this.rainSeed.push([R() * 80 - 40, R() * 40, R() * 80 - 40]);
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    this.rain = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0xaab8c8, transparent: true, opacity: 0.5 }));
    this.rain.frustumCulled = false; this.rain.visible = false;
    this.scene.add(this.rain);
  }

  // time in hours (0-24), weather text, where the camera is looking (the sun's shadow box follows it)
  update(hour, weather, focus, cam, dtReal) {
    this.uniforms.uTime.value += dtReal;
    if (this.gU) { const sp = this.gSpacing; this.gU.uOrigin.value.set(Math.round(cam.x / sp) * sp, Math.round(cam.z / sp) * sp); }
    const wet = /rain|drizzle/.test(weather), fog = /fog/.test(weather), grey = /grey|drizzle|rain|fog/.test(weather);
    this.uniforms.uWind.value = /windy/.test(weather) ? 1.8 : wet ? 1.1 : 0.5;
    const elev = Math.sin((hour - 6) / 12 * Math.PI);                  // -1 at midnight, 1 at noon
    const az = (hour - 6) / 12 * Math.PI;
    const sunDir = new THREE.Vector3(Math.cos(az) * 0.8, Math.max(-0.4, elev), -0.45).normalize();
    const day = clamp(elev * 3 + 0.25, 0, 1);
    const U = this.skyU, warmS = clamp(1 - Math.abs(elev) * 2.6, 0, 1);
    U.sunDir.value.copy(sunDir); U.night.value = 1 - day; U.cover.value = fog ? 0.95 : wet ? 0.85 : grey ? 0.7 : /windy/.test(weather) ? 0.45 : 0.25;
    if (FLAT) {                                                        // a soft cyan sky, pale at the horizon
      U.top.value.setHSL(0.57, grey ? 0.2 : 0.62, 0.05 + day * (grey ? 0.5 : 0.55));
      U.horizon.value.setHSL(0.52, grey ? 0.12 : 0.45, 0.08 + day * (grey ? 0.62 : 0.74)).lerp(new THREE.Color(0xf6b27a), warmS * 0.6 * (elev > -0.25 ? 1 : 0));
    } else {
      U.top.value.setHSL(0.6, grey ? 0.15 : 0.55, 0.04 + day * (grey ? 0.42 : 0.46));
      U.horizon.value.setHSL(0.58, grey ? 0.1 : 0.35, 0.07 + day * (grey ? 0.58 : 0.68)).lerp(new THREE.Color(0xf0a868), warmS * 0.55 * (elev > -0.25 ? 1 : 0));
    }
    U.sunCol.value.setHSL(0.09, 0.8, 0.55 + 0.3 * (1 - warmS));
    this.sun.position.copy(focus).addScaledVector(sunDir, 300); this.sun.target.position.copy(focus);
    this.sun.intensity = day * (grey ? 0.9 : FLAT ? 2.3 : 2.6);
    const warm = clamp(1 - Math.abs(elev) * 3, 0, 1);
    this.sun.color.setHSL(0.09, 0.6 * warm + (FLAT ? 0.25 : 0.1), 0.75 + 0.2 * (1 - warm));
    this.hemi.intensity = 0.15 + day * (grey ? 0.9 : FLAT ? 1.05 : 0.75);
    if (FLAT) this.hemi.color.setHSL(0.58, 0.45, 0.6 + 0.28 * day);  // shadows go a soft blue, not black
    this.moon.intensity = (1 - day) * 0.35;
    this.moon.position.copy(focus).add(new THREE.Vector3(-120, 200, 80)); this.moon.target = this.sun.target;
    this.stars.material.opacity = (1 - day) * (grey ? 0.15 : 0.9);
    const fc = U.horizon.value.clone();
    this.scene.fog.color.copy(fc);
    this.scene.fog.density = fog ? 0.02 : wet ? 0.0045 : grey ? 0.0018 : FLAT ? 0.0008 : 0.0011;
    if (this.recording) this.scene.fog.density = Math.min(this.scene.fog.density, 0.0035);   // a timelapse must see the town
    this.sky.visible = true;
    this.scene.background = null;
    if (TEX.water) { TEX.water.offset.y = this.uniforms.uTime.value * 0.04; TEX.water.offset.x = Math.sin(this.uniforms.uTime.value * 0.2) * 0.02; }
    this.rain.visible = wet;
    if (wet) {
      const p = this.rain.geometry.attributes.position, t = this.uniforms.uTime.value;
      const heavy = /heavy/.test(weather) ? 1 : 0.45;
      for (let i = 0; i < this.rainSeed.length; i++) {
        const [x, y0, z] = this.rainSeed[i];
        if (i / this.rainSeed.length > heavy) { p.setXYZ(i * 2, 0, -999, 0); p.setXYZ(i * 2 + 1, 0, -999, 0); continue; }
        const y = 40 - ((y0 + t * 22) % 40);
        const X = cam.x + x, Z = cam.z + z;
        p.setXYZ(i * 2, X, cam.y - 10 + y, Z); p.setXYZ(i * 2 + 1, X + 0.15, cam.y - 10 + y - 0.9, Z);
      }
      p.needsUpdate = true;
    }
    return { day, elev };
  }
}
