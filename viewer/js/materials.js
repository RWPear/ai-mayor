// The palette and the hand-painted textures (drawn on canvases at startup - no image files needed).
// Two looks: "flat" (the default - clean, flat-shaded pastel colours in the spirit of Thronefall: no textures,
// faceted shapes, warm light) and "textured" (?style=textured: the painted planks, stones and thatch).
import * as THREE from "three";
import { rng } from "./noise.js";

export const STYLE = new URLSearchParams(location.search).get("style") === "textured" ? "textured" : "flat";
export const FLAT = STYLE === "flat";

const PAINTED = {
  grass: 0x6f9149, grassDry: 0x93a25a, grassDark: 0x4f7337, mud: 0x6b5236, dirt: 0x8a6c47, sand: 0xb59a6c,
  rock: 0x8e8d86, water: 0x3b6f86, plaster: 0xe3d6ba, plaster2: 0xd8c39b, plaster3: 0xcfd2c4, timber: 0x4a3222,
  plank: 0x8c6239, plankDark: 0x6b4a2c, thatch: 0xc7a457, thatchOld: 0x9c8550, stone: 0x9a968c, slate: 0x56606a,
  clay: 0xa95f3b, iron: 0x5d6368, canvas: 0xe0d5b8, gold: 0xe2b448, leaf1: 0x3f7a35, leaf2: 0x5a8f3a, leaf3: 0x2f6131,
  pine: 0x2c5a3a, trunk: 0x5c3d24, crop: 0x8dbb4c, banner: 0x274b8a, fire: 0xffa13d, glass: 0x2a2f33,
  windowLit: 0xffc977, autumn1: 0xb8862f, autumn2: 0xa5532c, soil: 0x6a4c2e, roofRed: 0x9c4b32,
};
// Thronefall-ish: deep teal grass, warm orange timber, cream stone and cliffs, lime pines, bright blue water -
// and (with the lights in terrain.js) navy shadows
const PASTEL = {
  grass: 0x2f6f60, grassDry: 0x3b7c64, grassDark: 0x255d55, mud: 0x8a5a3c, dirt: 0xb07650, sand: 0xd8c79c,
  rock: 0xe4d6ae, water: 0x46aee8, plaster: 0xe9a463, plaster2: 0xdf9658, plaster3: 0xefb578, timber: 0x8a4a26,
  plank: 0xd9863f, plankDark: 0xb5652c, thatch: 0xc1582d, thatchOld: 0xa84b28, stone: 0xdccfac, slate: 0x4766b0,
  clay: 0xc45f35, iron: 0x5e6680, canvas: 0xf1e2c2, gold: 0xf2c24e, leaf1: 0x7cc84e, leaf2: 0x98d85a, leaf3: 0x5fb046,
  pine: 0x76c24c, trunk: 0x6b3a20, crop: 0xe9c46a, banner: 0x2f55b0, fire: 0xffa13d, glass: 0x23305a,
  windowLit: 0xffd27f, autumn1: 0xeaa53c, autumn2: 0xdb7342, soil: 0x9a5c36, roofRed: 0xb94a2a,
};
export const C = FLAT ? PASTEL : PAINTED;
// in the flat look a texture name just means "the colour that thing is"
const TEX_COLOR = { stone: "stone", thatch: "thatch", slate: "slate", brick: "clay", soil: "soil" };

function canvasTex(w, h, draw, repeat = true) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 8;
  return t;
}
const hex = (n) => "#" + n.toString(16).padStart(6, "0");
function shade(n, f) { const c = new THREE.Color(n); c.multiplyScalar(f); return "#" + c.getHexString(); }

// texture scale: 1 texture tile = TILE metres
export const TILE = 2.0;

export const TEX = {};
export function makeTextures() {
  const R = rng(7);
  TEX.plank = canvasTex(256, 256, (x, w, h) => {      // light and neutral: the material's colour tints it
    for (let i = 0; i < 8; i++) {
      x.fillStyle = shade(0xf2ece4, 0.86 + R() * 0.16); x.fillRect(0, i * 32, w, 32);
      x.fillStyle = "rgba(40,25,10,.35)"; x.fillRect(0, i * 32, w, 2);
      for (let k = 0; k < 6; k++) { x.fillStyle = `rgba(60,35,15,${0.06 + R() * 0.1})`; x.fillRect(R() * w, i * 32 + 4 + R() * 24, 30 + R() * 60, 1); }
      x.fillStyle = "rgba(30,20,10,.3)"; x.fillRect(R() * w, i * 32, 2, 32);
    }
  });
  TEX.plaster = canvasTex(256, 256, (x, w, h) => {
    x.fillStyle = "#ffffff"; x.fillRect(0, 0, w, h);
    for (let k = 0; k < 2200; k++) { x.fillStyle = `rgba(120,100,70,${R() * 0.07})`; x.fillRect(R() * w, R() * h, 3 + R() * 6, 3 + R() * 6); }
  });
  TEX.stone = canvasTex(256, 256, (x, w, h) => {
    x.fillStyle = "#6f6a60"; x.fillRect(0, 0, w, h);
    let y = 0;
    while (y < h) {
      const rh = 22 + R() * 18; let xx = -R() * 30;
      while (xx < w) {
        const rw = 30 + R() * 40;
        x.fillStyle = shade(C.stone, 0.75 + R() * 0.4);
        x.beginPath(); x.roundRect(xx + 2, y + 2, rw - 4, rh - 4, 6); x.fill();
        xx += rw;
      }
      y += rh;
    }
  });
  TEX.thatch = canvasTex(256, 256, (x, w, h) => {
    x.fillStyle = hex(C.thatch); x.fillRect(0, 0, w, h);
    for (let k = 0; k < 3000; k++) {
      x.strokeStyle = `rgba(${90 + R() * 80},${70 + R() * 60},${20 + R() * 30},${0.25 + R() * 0.4})`;
      const px = R() * w, py = R() * h; x.beginPath(); x.moveTo(px, py); x.lineTo(px + (R() - 0.5) * 4, py + 10 + R() * 14); x.stroke();
    }
    for (let i = 0; i < 8; i++) { x.fillStyle = "rgba(60,45,15,.25)"; x.fillRect(0, i * 32 + 28, w, 4); }
  });
  TEX.slate = canvasTex(256, 256, (x, w, h) => {
    for (let r = 0; r < 12; r++) for (let k = 0; k < 9; k++) {
      x.fillStyle = shade(C.slate, 0.8 + R() * 0.35);
      x.fillRect(k * 30 + (r % 2) * 15 - 15, r * 22, 28, 20);
    }
  });
  TEX.brick = canvasTex(256, 256, (x, w, h) => {
    x.fillStyle = "#a99a85"; x.fillRect(0, 0, w, h);
    for (let r = 0; r < 16; r++) for (let k = 0; k < 9; k++) { x.fillStyle = shade(C.clay, 0.8 + R() * 0.35); x.fillRect(k * 32 + (r % 2) * 16 - 16, r * 16, 30, 14); }
  });
  TEX.canvas = canvasTex(128, 128, (x, w, h) => {
    x.fillStyle = "#fff"; x.fillRect(0, 0, w, h);
    for (let k = 0; k < 400; k++) { x.fillStyle = `rgba(110,90,60,${R() * 0.08})`; x.fillRect(R() * w, R() * h, 6, 6); }
    x.fillStyle = "rgba(90,70,40,.15)"; for (let i = 0; i < 8; i++) x.fillRect(i * 16, 0, 1, h);
  });
  TEX.soil = canvasTex(128, 128, (x, w, h) => {
    x.fillStyle = "#6a4c2e"; x.fillRect(0, 0, w, h);
    for (let k = 0; k < 900; k++) { x.fillStyle = `rgba(${R() < 0.5 ? "30,20,10" : "150,120,80"},${R() * 0.25})`; x.fillRect(R() * w, R() * h, 2, 2); }
  });
  TEX.soft = canvasTex(64, 64, (x, w, h) => {       // a soft round blob: smoke, blob shadows, glows
    const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, w, h);
  }, false);
  TEX.water = canvasTex(256, 256, (x, w, h) => {     // ripples, used as a scrolling normal-ish detail
    x.fillStyle = "#8080ff"; x.fillRect(0, 0, w, h);
    for (let k = 0; k < 500; k++) {
      x.strokeStyle = `rgba(${150 + R() * 80},${150 + R() * 80},255,${0.25 + R() * 0.3})`; x.lineWidth = 1 + R() * 2;
      x.beginPath(); const px = R() * w, py = R() * h; x.ellipse(px, py, 6 + R() * 18, 2 + R() * 4, 0, 0, Math.PI * 2); x.stroke();
    }
  });
  TEX.water.colorSpace = THREE.NoColorSpace;
  return TEX;
}

const cache = new Map();
// shared materials by key: colour + texture, so hundreds of buildings cost a handful of materials
const OURS = new Set(Object.values(PASTEL));
const tmpC = new THREE.Color(), hsl = {};
function pastel(hexN) {                                   // one-off colours in the kit: a little brighter and softer
  if (OURS.has(hexN) || hexN === 0xffffff) return hexN;
  tmpC.setHex(hexN).getHSL(hsl);
  return tmpC.setHSL(hsl.h, Math.min(1, hsl.s * 1.12 + 0.04), 0.1 + hsl.l * 0.92).getHex();
}
export function M(color, tex = null, opts = {}) {
  if (FLAT) color = pastel(color);
  if (FLAT && tex && tex !== "soft") {                     // no textures: the colour of the thing, flat-shaded
    if (color === 0xffffff && TEX_COLOR[tex]) color = C[TEX_COLOR[tex]];
    tex = null;
    opts = { flatShading: true, roughness: 1, ...opts, metalness: 0 };
  } else if (FLAT) opts = { flatShading: true, roughness: 1, ...opts };
  const key = `${color}|${tex}|${JSON.stringify(opts)}`;
  if (!cache.has(key)) {
    cache.set(key, new THREE.MeshStandardMaterial({ color, map: tex ? TEX[tex] : null, roughness: 0.92, metalness: 0, ...opts }));
  }
  return cache.get(key);
}

// geometry helpers with UVs scaled to metres, so every wall shows planks/stones at the same size
export function box(w, h, d) {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.attributes.uv, n = g.attributes.normal;
  for (let i = 0; i < uv.count; i++) {
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i));
    const su = ax > 0.5 ? d : w, sv = ay > 0.5 ? d : h;
    uv.setXY(i, uv.getX(i) * su / TILE, uv.getY(i) * sv / TILE);
  }
  return g;
}

export function mesh(geo, mat, { cast = true, receive = true } = {}) {
  const m = new THREE.Mesh(geo, mat); m.castShadow = cast; m.receiveShadow = receive; return m;
}
