/**
 * 小博士 3D 模型（全部程序化生成，无外部美术资源）
 *
 * 造型：毛绒小猫学者。参考毛绒机器人玩偶的比例：
 * - 白色长绒“兜帽”包住头部，顶端一个柔软的尖，两侧是猫耳（内耳粉色）；
 * - 兜帽里嵌着象牙色的光面脸盘：大而亮的深蓝眼睛、粉色猫鼻、ω 形猫嘴、胡须；
 * - 黑色细框圆眼镜；
 * - 灰色针织菱格背心（菱格用品牌海军蓝），V 领、罗纹边、三颗纽扣，口袋里插一支笔；
 * - 毛绒短手，掌心有粉色肉垫；石板灰小靴子；身后一条会摇的毛绒尾巴。
 *
 * 毛绒质感用“壳层法”实现：同一几何体沿法线外扩多层，每层用噪声 alphaTest 裁出更稀疏的毛尖，
 * 由内到外颜色由灰变白（自带接触阴影），轮廓边缘自然发虚。
 *
 * 坐标：y 向上，角色面朝 +z，脚底在 y = 0。"L" / "R" 指屏幕左 / 右（L 在 x<0）。
 */
import * as THREE from 'three';
import { buildGlasses } from './glasses.js';
import { buildOutfit } from './outfits.js';

export const PALETTE = {
  fur: 0xf6f7fa,
  furDeep: 0xb8bfcb,
  face: 0xf3ece2,
  innerEar: 0xf2c3c6,
  pad: 0xeea7ad,
  nose: 0xe58e98,
  eye: 0x0c1630,
  iris: 0x2a4f9e,
  mouth: 0x5a2a36,
  tongue: 0xef8f9b,
  line: 0x3b3640,
  whisker: 0x8d96a6,
  frame: 0x15171c,
  vest: 0xa4acb8,
  argyle: 0x2f4c7f,
  rib: 0x7c8593,
  boot: 0x5b6678,
  blush: 0xf0a19c,
  page: 0xfbfaf6,
  navy: 0x1e3457,
  accent: 0x2f5bd3,
};

// 兜帽（头）椭球半径
const HA = 0.7;
const HB = 0.66;
const HC = 0.66;
// 脸盘：嵌在兜帽前方的扁椭球
const FA = 0.5;
const FB = 0.44;
const FC = 0.15;
const FY = -0.05;
const FZ = 0.5;
// 眼睛尺寸
const EW = 0.092;
const EH = 0.112;

const Z = new THREE.Vector3(0, 0, 1);
const Y = new THREE.Vector3(0, 1, 0);
const smooth = (a, b, x) => {
  const t = Math.min(Math.max((x - a) / (b - a), 0), 1);
  return t * t * (3 - 2 * t);
};
const lerp = (a, b, t) => a + (b - a) * t;

function hoodZ(x, y) {
  const k = 1 - (x * x) / (HA * HA) - (y * y) / (HB * HB);
  return HC * Math.sqrt(Math.max(k, 0));
}
const faceE = (x, y) => (x * x) / (FA * FA) + ((y - FY) * (y - FY)) / (FB * FB);

/** 脸盘表面 (x, y) 处的点与法线 */
function onFace(x, y, out = 0) {
  const e = faceE(x, y);
  const z = FZ + FC * Math.sqrt(Math.max(1 - e, 1e-4));
  const n = new THREE.Vector3(x / (FA * FA), (y - FY) / (FB * FB), (z - FZ) / (FC * FC)).normalize();
  return { p: new THREE.Vector3(x, y, z).addScaledVector(n, out), n };
}

// ---------- 贴图 ----------
function canvasTex(size, draw, { srgb = true, repeat = true } = {}) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  draw(c.getContext('2d'), size);
  const tex = new THREE.CanvasTexture(c);
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  if (repeat) tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  return tex;
}

function radialTexture(rgb) {
  return canvasTex(128, (g) => {
    const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, `rgba(${rgb},1)`);
    grd.addColorStop(0.45, `rgba(${rgb},0.55)`);
    grd.addColorStop(1, `rgba(${rgb},0)`);
    g.fillStyle = grd;
    g.fillRect(0, 0, 128, 128);
  }, { repeat: false });
}

/** 毛发噪声：每个像素一根“毛”，取值越大毛越长；带轻微成簇 */
function furNoise() {
  return canvasTex(96, (g, s) => {
    const img = g.createImageData(s, s);
    const clump = [];
    for (let i = 0; i < 40; i++) clump.push([Math.random() * s, Math.random() * s, 6 + Math.random() * 10]);
    for (let y = 0; y < s; y++) {
      for (let x = 0; x < s; x++) {
        let c = 0;
        for (const [cx, cy, r] of clump) {
          const dx = Math.min(Math.abs(x - cx), s - Math.abs(x - cx));
          const dy = Math.min(Math.abs(y - cy), s - Math.abs(y - cy));
          c = Math.max(c, 1 - Math.hypot(dx, dy) / r);
        }
        const v = Math.pow(Math.random(), 0.75) * (0.75 + 0.25 * c);
        const i = (y * s + x) * 4;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = Math.round(v * 255);
        img.data[i + 3] = 255;
      }
    }
    g.putImageData(img, 0, 0);
  }, { srgb: false });
}

// ---------- 几何工具 ----------
/** 合并重合顶点的法线（球体接缝处），避免毛发壳层在接缝裂开 */
function smoothNormals(geo) {
  geo.computeVertexNormals();
  const pos = geo.attributes.position;
  const nor = geo.attributes.normal;
  const map = new Map();
  const key = (i) => `${pos.getX(i).toFixed(4)},${pos.getY(i).toFixed(4)},${pos.getZ(i).toFixed(4)}`;
  for (let i = 0; i < pos.count; i++) {
    const k = key(i);
    const v = map.get(k) || [0, 0, 0];
    v[0] += nor.getX(i);
    v[1] += nor.getY(i);
    v[2] += nor.getZ(i);
    map.set(k, v);
  }
  const n = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    const v = map.get(key(i));
    n.set(v[0], v[1], v[2]).normalize();
    nor.setXYZ(i, n.x, n.y, n.z);
  }
  return geo;
}

function offsetGeometry(geo, d) {
  const g = geo.clone();
  const pos = g.attributes.position;
  const nor = g.attributes.normal;
  for (let i = 0; i < pos.count; i++) {
    pos.setXYZ(i, pos.getX(i) + nor.getX(i) * d, pos.getY(i) + nor.getY(i) * d, pos.getZ(i) + nor.getZ(i) * d);
  }
  return g;
}

/** 渐细的管状体 */
function taperedTube(points, radius, tipScale = 0.25, segs = 24, radial = 12) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
  const geo = new THREE.TubeGeometry(curve, segs, radius, radial, false);
  const pos = geo.attributes.position;
  const P = new THREE.Vector3();
  const v = new THREE.Vector3();
  for (let i = 0; i <= segs; i++) {
    curve.getPointAt(i / segs, P);
    const s = lerp(1, tipScale, Math.pow(i / segs, 1.3));
    for (let j = 0; j <= radial; j++) {
      const idx = i * (radial + 1) + j;
      v.fromBufferAttribute(pos, idx).sub(P).multiplyScalar(s).add(P);
      pos.setXYZ(idx, v.x, v.y, v.z);
    }
  }
  return { geo, curve };
}

function mesh(geo, mat, part, opts = {}) {
  const m = new THREE.Mesh(geo, mat);
  m.userData.part = part;
  m.castShadow = opts.cast ?? true;
  m.receiveShadow = opts.receive ?? false;
  return m;
}
const noRaycast = () => {};

// ---------- 身体轮廓 ----------
const BODY_PROFILE = [
  [0.0, 0.02], [0.4, 0.02], [0.55, 0.08], [0.6, 0.2], [0.6, 0.36],
  [0.56, 0.54], [0.49, 0.7], [0.39, 0.83], [0.25, 0.93], [0.0, 0.98],
];
const BODY_Z = 0.9;
const bodyCurve = new THREE.SplineCurve(BODY_PROFILE.map(([r, y]) => new THREE.Vector2(r, y)));
const bodySamples = bodyCurve.getPoints(90);
function bodyRadiusAt(y) {
  for (let i = 0; i < bodySamples.length - 1; i++) {
    const a = bodySamples[i];
    const b = bodySamples[i + 1];
    if ((y >= a.y && y <= b.y) || (y <= a.y && y >= b.y)) return lerp(a.x, b.x, (y - a.y) / (b.y - a.y || 1));
  }
  return 0.5;
}

/**
 * 构建角色，返回 { root, blob, apply(params, time), anchors }。
 * apply 只负责把参数写入骨骼与面部，所有“表演”逻辑在 brain.js。
 */
export function buildCharacter(opts = {}) {
  const look = { glasses: 'browline', outfit: 'labcoat', ...opts };
  const furTex = furNoise();
  const M = {
    furBase: new THREE.MeshStandardMaterial({ color: PALETTE.furDeep, roughness: 1 }),
    face: new THREE.MeshPhysicalMaterial({
      color: PALETTE.face, roughness: 0.3, clearcoat: 0.8, clearcoatRoughness: 0.18,
    }),
    innerEar: new THREE.MeshPhysicalMaterial({
      color: PALETTE.innerEar, roughness: 0.75, sheen: 1, sheenColor: 0xffe3e6, sheenRoughness: 0.5,
    }),
    pad: new THREE.MeshPhysicalMaterial({ color: PALETTE.pad, roughness: 0.45, clearcoat: 0.4 }),
    nose: new THREE.MeshPhysicalMaterial({ color: PALETTE.nose, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.1 }),
    eye: new THREE.MeshPhysicalMaterial({ color: PALETTE.eye, roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.04 }),
    iris: new THREE.MeshPhysicalMaterial({ color: PALETTE.iris, roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.05 }),
    pupil: new THREE.MeshPhysicalMaterial({ color: 0x03060d, roughness: 0.2, clearcoat: 1 }),
    mouth: new THREE.MeshStandardMaterial({ color: PALETTE.mouth, roughness: 0.6 }),
    tongue: new THREE.MeshPhysicalMaterial({ color: PALETTE.tongue, roughness: 0.45, clearcoat: 0.5 }),
    line: new THREE.MeshStandardMaterial({ color: PALETTE.line, roughness: 0.6 }),
    brow: new THREE.MeshStandardMaterial({ color: 0xb3a597, roughness: 0.8 }),
    whisker: new THREE.MeshStandardMaterial({ color: PALETTE.whisker, roughness: 0.5 }),
    boot: new THREE.MeshPhysicalMaterial({
      color: PALETTE.boot, roughness: 0.75, sheen: 0.6, sheenColor: 0x9aa6ba, sheenRoughness: 0.6,
    }),
    sole: new THREE.MeshStandardMaterial({ color: 0xe6e9ee, roughness: 0.7 }),
    accent: new THREE.MeshPhysicalMaterial({ color: PALETTE.accent, roughness: 0.32, clearcoat: 0.9 }),
    metal: new THREE.MeshStandardMaterial({ color: 0xc7cfdb, metalness: 1, roughness: 0.22 }),
    navy: new THREE.MeshPhysicalMaterial({ color: PALETTE.navy, roughness: 0.62 }),
    page: new THREE.MeshStandardMaterial({ color: PALETTE.page, roughness: 0.9 }),
    white: new THREE.MeshStandardMaterial({ color: 0xf6f8fb, roughness: 0.4 }),
    blush: new THREE.MeshBasicMaterial({ map: radialTexture('240,161,156'), transparent: true, opacity: 0, depthWrite: false }),
    shadow: new THREE.MeshBasicMaterial({ map: radialTexture('20,32,51'), transparent: true, opacity: 0.28, depthWrite: false }),
  };

  // 毛绒：底层 + 若干壳层
  const shellMatCache = new Map();
  function shellMat(i, n, repeat, tint) {
    const k = `${i}/${n}/${repeat}/${tint}`;
    if (shellMatCache.has(k)) return shellMatCache.get(k);
    const h = i / n;
    const tex = furTex.clone();
    tex.repeat.set(repeat[0], repeat[1]);
    tex.needsUpdate = true;
    const c = new THREE.Color(PALETTE.furDeep).lerp(new THREE.Color(tint), Math.pow(h, 0.55));
    const m = new THREE.MeshStandardMaterial({
      color: c, roughness: 1, alphaMap: tex, alphaTest: lerp(0.08, 0.86, h),
    });
    shellMatCache.set(k, m);
    return m;
  }
  function furry(geo, part, { len = 0.04, shells = 7, repeat = [8, 4], cast = true, tint = PALETTE.fur } = {}) {
    smoothNormals(geo);
    const g = new THREE.Group();
    const base = mesh(geo, M.furBase, part, { cast, receive: true });
    g.add(base);
    for (let i = 1; i <= shells; i++) {
      const s = mesh(offsetGeometry(geo, (len * i) / shells), shellMat(i, shells, repeat, tint), part, { cast: false });
      s.raycast = noRaycast;
      g.add(s);
    }
    g.userData.base = base;
    return g;
  }

  const root = new THREE.Group();
  root.name = 'xiaoboshi';

  const blob = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 1.3), M.shadow);
  blob.rotation.x = -Math.PI / 2;
  blob.position.y = 0.002;
  blob.renderOrder = -1;

  const squash = new THREE.Group();
  root.add(squash);

  // ---------- 身体：白色毛绒（下摆处露出“短裤”）----------
  const bodyGeo = new THREE.LatheGeometry(bodySamples, 80);
  bodyGeo.scale(1, 1, BODY_Z);
  const body = furry(bodyGeo, 'body', { len: 0.032, shells: 6, repeat: [14, 4] });
  squash.add(body);

  // ---------- 服装（可替换款式，见 outfits.js）----------
  const kit = { mesh, canvasTex, bodyRadiusAt, BODY_Z, squash, onFace };
  const outfit = buildOutfit(look.outfit, kit);

  // 靴子
  for (const sx of [-1, 1]) {
    const boot = new THREE.Group();
    boot.position.set(0.22 * sx, 0.0, 0.33);
    boot.rotation.y = sx * 0.12;
    const upper = mesh(new THREE.SphereGeometry(0.16, 28, 20), M.boot, 'body', { receive: true });
    upper.scale.set(1, 0.66, 1.25);
    upper.position.y = 0.085;
    const sole = mesh(new THREE.CylinderGeometry(0.15, 0.16, 0.03, 32), M.sole, 'body');
    sole.scale.set(1, 1, 1.3);
    sole.position.y = 0.018;
    boot.add(upper, sole);
    squash.add(boot);
  }

  // ---------- 尾巴（关节链）----------
  const tailBase = new THREE.Group();
  tailBase.position.set(0.3, 0.28, -0.38);
  tailBase.rotation.order = 'YXZ';
  squash.add(tailBase);
  const tailJoints = [];
  {
    const N = 9;
    const SEG = 0.08;
    let parent = tailBase;
    for (let i = 0; i < N; i++) {
      const j = new THREE.Group();
      if (i > 0) j.position.y = SEG;
      parent.add(j);
      const r = lerp(0.072, 0.05, i / (N - 1));
      const geo = new THREE.CapsuleGeometry(r, SEG, 6, 14);
      geo.translate(0, SEG / 2, 0);
      const seg = furry(geo, 'body', { len: 0.03, shells: 5, repeat: [3, 1], cast: i < 6 });
      j.add(seg);
      tailJoints.push(j);
      parent = j;
    }
    // 尾尖一簇略带灰蓝
    const tip = furry(new THREE.SphereGeometry(0.062, 20, 14), 'body', { len: 0.035, shells: 5, repeat: [3, 2], tint: 0xdfe5ef });
    tip.position.y = SEG + 0.02;
    tailJoints[N - 1].add(tip);
  }

  // ---------- 手臂（肩 → 肘 → 爪）----------
  const arms = {};
  for (const [key, s] of [['L', -1], ['R', 1]]) {
    const shoulder = new THREE.Group();
    shoulder.position.set(0.5 * s, 0.66, 0);
    const upperGeo = new THREE.CapsuleGeometry(0.092, 0.12, 8, 18);
    upperGeo.translate(0, -0.11, 0);
    const sl = outfit.sleeve;
    if (sl) {
      const g = new THREE.CapsuleGeometry(0.112, 0.11, 8, 20);
      g.translate(0, -0.105, 0);
      shoulder.add(mesh(g, sl.mat, 'arm', { receive: true }));
      if (sl.short) {
        const cuff = mesh(new THREE.TorusGeometry(0.108, sl.cuffR, 8, 32), sl.cuffMat, 'arm', { cast: false });
        cuff.rotation.x = Math.PI / 2;
        cuff.position.y = -0.19;
        shoulder.add(cuff);
      }
    } else shoulder.add(furry(upperGeo, 'arm', { len: 0.03, shells: 5, repeat: [4, 2] }));
    const elbow = new THREE.Group();
    elbow.position.y = -0.225;
    shoulder.add(elbow);
    const foreGeo = new THREE.CapsuleGeometry(0.088, 0.09, 8, 18);
    foreGeo.translate(0, -0.09, 0);
    if (sl && !sl.short) {
      const g = new THREE.CapsuleGeometry(0.106, 0.08, 8, 20);
      g.translate(0, -0.085, 0);
      elbow.add(mesh(g, sl.mat, 'arm', { receive: true }));
      const cuff = mesh(new THREE.TorusGeometry(0.1, sl.cuffR, 8, 32), sl.cuffMat, 'arm', { cast: false });
      cuff.rotation.x = Math.PI / 2;
      cuff.position.y = -0.17;
      elbow.add(cuff);
    } else elbow.add(furry(foreGeo, 'arm', { len: 0.03, shells: 5, repeat: [4, 2] }));
    const hand = new THREE.Group();
    hand.position.y = -0.225;
    elbow.add(hand);
    const pawGeo = new THREE.SphereGeometry(0.1, 28, 20);
    pawGeo.scale(1, 1.05, 0.9);
    hand.add(furry(pawGeo, 'hand', { len: 0.026, shells: 5, repeat: [4, 2] }));
    // 粉色肉垫（掌心朝前）
    const main = mesh(new THREE.SphereGeometry(1, 20, 14), M.pad, 'hand', { cast: false });
    main.scale.set(0.042, 0.034, 0.014);
    main.position.set(0, -0.025, 0.1);
    main.rotation.x = 0.25;
    hand.add(main);
    for (const [tx, ty] of [[-0.04, 0.03], [0, 0.048], [0.04, 0.03]]) {
      const toe = mesh(new THREE.SphereGeometry(1, 14, 10), M.pad, 'hand', { cast: false });
      toe.scale.set(0.017, 0.019, 0.009);
      toe.position.set(tx, ty, 0.095 - Math.abs(tx) * 0.3);
      toe.rotation.x = -0.25;
      hand.add(toe);
    }
    squash.add(shoulder);
    arms[key] = { shoulder, elbow, hand, s };
  }

  // 书（独立演练回避姿态时出现）
  const book = new THREE.Group();
  {
    const half = (side) => {
      const g = new THREE.Group();
      const cover = mesh(new THREE.BoxGeometry(0.25, 0.34, 0.016), M.navy, 'arm');
      cover.position.set(0.125 * side, 0, -0.012);
      const pages = mesh(new THREE.BoxGeometry(0.235, 0.32, 0.03), M.page, 'arm');
      pages.position.set(0.12 * side, 0, 0.01);
      g.add(cover, pages);
      g.rotation.y = -0.38 * side;
      return g;
    };
    book.add(half(-1), half(1));
    book.visible = false;
    squash.add(book);
  }

  // ---------- 头：毛绒兜帽 ----------
  const neck = new THREE.Group();
  neck.position.set(0, 0.9, 0);
  neck.rotation.order = 'YXZ';
  squash.add(neck);
  const head = new THREE.Group();
  head.position.set(0, 0.6, 0.0);
  neck.add(head);

  {
    // 兜帽：椭球，前方挖出脸盘位置；下部略收，和身体连成一体
    const geo = new THREE.SphereGeometry(1, 96, 72);
    const pos = geo.attributes.position;
    const d = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) {
      d.fromBufferAttribute(pos, i);
      let x = d.x * HA;
      let y = d.y * HB;
      let z = d.z * HC;
      const tuck = smooth(-0.2, -0.9, d.y) * 0.1; // 下颌处收窄
      x *= 1 - tuck;
      z *= 1 - tuck * 0.6;
      const e = faceE(x, y);
      if (z > 0 && e < 1.04) {
        const fz = FZ + FC * Math.sqrt(Math.max(1 - Math.min(e, 1), 0)) - 0.04;
        z = Math.min(z, lerp(fz, z, smooth(0.9, 1.04, e)));
      }
      pos.setXYZ(i, x, y, z);
    }
    head.add(furry(geo, 'head', { len: 0.045, shells: 8, repeat: [9, 4.5] }));

    // 脸盘
    const face = mesh(new THREE.SphereGeometry(1, 72, 54), M.face, 'head', { receive: true });
    face.scale.set(FA, FB, FC);
    face.position.set(0, FY, FZ);
    head.add(face);

    // 兜帽边缘的一圈毛绒，让脸盘看起来嵌在里面
    const pts = [];
    for (let i = 0; i < 72; i++) {
      const a = (i / 72) * Math.PI * 2;
      const x = FA * 1.01 * Math.cos(a);
      const y = FY + FB * 1.01 * Math.sin(a);
      pts.push(new THREE.Vector3(x, y, Math.max(hoodZ(x, y), FZ) + 0.005));
    }
    const rimGeo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 144, 0.062, 14, true);
    head.add(furry(rimGeo, 'head', { len: 0.035, shells: 6, repeat: [40, 1] }));
  }

  // 兜帽顶端的软尖（带弹簧次级动作，复用原“呆毛”参数）
  const tuftPivot = new THREE.Group();
  {
    const dd = new THREE.Vector3(0.06, 1, -0.12).normalize();
    tuftPivot.position.set(dd.x * HA * 0.93, dd.y * HB * 0.93, dd.z * HC * 0.93);
    const { geo } = taperedTube(
      [[0, -0.1, 0], [0, 0.04, 0], [0.025, 0.14, -0.02], [0.08, 0.2, -0.06], [0.13, 0.21, -0.09]],
      0.13, 0.22, 28, 16,
    );
    tuftPivot.add(furry(geo, 'head', { len: 0.035, shells: 6, repeat: [6, 2] }));
    head.add(tuftPivot);
  }

  // 猫耳
  const ears = {};
  {
    const outerProfile = [[0.0, -0.04], [0.16, -0.02], [0.165, 0.05], [0.13, 0.15], [0.07, 0.25], [0.025, 0.3], [0, 0.31]]
      .map(([r, y]) => new THREE.Vector2(r, y));
    const innerProfile = [[0.0, 0.0], [0.11, 0.02], [0.1, 0.09], [0.06, 0.18], [0.02, 0.23], [0, 0.235]]
      .map(([r, y]) => new THREE.Vector2(r, y));
    for (const [key, s] of [['L', -1], ['R', 1]]) {
      const mount = new THREE.Group();
      const dd = new THREE.Vector3(s * 0.6, 0.76, 0.12).normalize();
      mount.position.set(dd.x * HA * 0.95, dd.y * HB * 0.95, dd.z * HC * 0.95);
      const up = dd.clone().lerp(Y, 0.45).normalize();
      mount.quaternion.setFromUnitVectors(Y, up);
      const pivot = new THREE.Group();
      mount.add(pivot);
      const og = new THREE.LatheGeometry(outerProfile, 32);
      og.scale(1, 1, 0.42);
      pivot.add(furry(og, 'head', { len: 0.03, shells: 6, repeat: [4, 2] }));
      const ig = new THREE.LatheGeometry(innerProfile, 28);
      ig.scale(1, 1, 0.22);
      const inner = mesh(ig, M.innerEar, 'head', { cast: false });
      inner.position.set(0, 0.03, 0.05);
      pivot.add(inner);
      // 内耳的几缕白毛
      for (let k = -1; k <= 1; k++) {
        const { geo } = taperedTube([[0, 0, 0], [k * 0.02, 0.06, 0.012], [k * 0.035, 0.11, 0.004]], 0.01, 0.15, 10, 6);
        const tuft = mesh(geo, shellMat(6, 6, [1, 1], PALETTE.fur).clone(), 'head', { cast: false });
        tuft.material.alphaMap = null;
        tuft.material.alphaTest = 0;
        tuft.position.set(0, 0.03, 0.065);
        pivot.add(tuft);
      }
      head.add(mount);
      ears[key] = { pivot, s };
    }
  }

  // 眼睛：每只眼一个“眼窝”坐标系，上下眼睑用裁剪平面实现（可倾斜表达情绪）
  const eyes = {};
  for (const [key, s] of [['L', -1], ['R', 1]]) {
    const socket = new THREE.Group();
    const upper = new THREE.Plane();
    const lower = new THREE.Plane();
    const planes = [upper, lower];
    const clipped = (m) => {
      const c = m.clone();
      c.clippingPlanes = planes;
      return c;
    };
    const eye = mesh(new THREE.SphereGeometry(1, 36, 26), clipped(M.eye), 'head', { cast: false });
    eye.scale.set(EW, EH, 0.045);
    eye.position.z = -0.012;
    // 下半部偏亮的蓝色虹膜：毛绒玩偶那种“玻璃珠”眼睛
    const iris = mesh(new THREE.SphereGeometry(1, 30, 22), clipped(M.iris), 'head', { cast: false });
    iris.scale.set(EW * 0.72, EH * 0.6, 0.016);
    iris.position.set(0, -EH * 0.26, 0.022);
    const pupil = mesh(new THREE.SphereGeometry(1, 24, 16), clipped(M.pupil), 'head', { cast: false });
    pupil.position.set(0, -EH * 0.16, 0.028);
    const hlMat = new THREE.MeshBasicMaterial({ color: 0xffffff, clippingPlanes: planes });
    const hl1 = mesh(new THREE.SphereGeometry(1, 16, 12), hlMat, 'head', { cast: false });
    hl1.scale.set(0.03, 0.034, 0.008);
    hl1.position.set(-0.03, 0.04, 0.036);
    const hl2 = mesh(new THREE.SphereGeometry(1, 12, 8), hlMat, 'head', { cast: false });
    hl2.scale.set(0.013, 0.013, 0.005);
    hl2.position.set(0.032, -0.05, 0.04);
    const lash = mesh(new THREE.CapsuleGeometry(0.008, 1, 4, 8), M.line, 'head', { cast: false });
    lash.rotation.z = Math.PI / 2;
    const lashPivot = new THREE.Group();
    lashPivot.add(lash);
    lashPivot.visible = false;
    const arc = mesh(new THREE.TorusGeometry(0.068, 0.013, 8, 28, Math.PI), M.line, 'head', { cast: false });
    arc.visible = false;
    socket.add(eye, iris, pupil, hl1, hl2, lashPivot, arc);
    head.add(socket);
    eyes[key] = { socket, eye, iris, pupil, hl: [hl1, hl2], lashPivot, lash, arc, upper, lower, s, baseX: 0.205 * s, baseY: 0.0 };
  }

  // 眉毛：短而圆的“麻吕眉”
  const brows = {};
  for (const [key, s] of [['L', -1], ['R', 1]]) {
    const g = new THREE.Group();
    const { p, n } = onFace(0.2 * s, 0.215, 0.004);
    g.position.copy(p);
    g.quaternion.setFromUnitVectors(Z, n);
    const inner = new THREE.Group();
    const b = mesh(new THREE.CapsuleGeometry(0.017, 0.038, 4, 12), M.brow, 'head', { cast: false });
    b.rotation.z = Math.PI / 2;
    b.scale.set(1, 1, 0.45);
    inner.add(b);
    g.add(inner);
    head.add(g);
    brows[key] = { inner, s };
  }

  // 眼镜（可替换款式，见 glasses.js）
  const glasses = buildGlasses(look.glasses, kit);
  head.add(glasses);

  // 猫鼻：圆角倒三角
  {
    const shape = new THREE.Shape();
    const w = 0.03;
    const h = 0.024;
    const r = 0.008;
    shape.moveTo(-w + r, h / 2);
    shape.lineTo(w - r, h / 2);
    shape.quadraticCurveTo(w, h / 2, w - r * 0.6, h / 2 - r);
    shape.lineTo(r * 0.7, -h / 2 + r * 0.6);
    shape.quadraticCurveTo(0, -h / 2 - r * 0.2, -r * 0.7, -h / 2 + r * 0.6);
    shape.lineTo(-w + r * 0.6, h / 2 - r);
    shape.quadraticCurveTo(-w, h / 2, -w + r, h / 2);
    const geo = new THREE.ExtrudeGeometry(shape, { depth: 0.008, bevelEnabled: true, bevelThickness: 0.008, bevelSize: 0.006, bevelSegments: 4, curveSegments: 8 });
    const nose = mesh(geo, M.nose, 'head', { cast: false });
    const { p, n } = onFace(0, -0.105, -0.002);
    nose.position.copy(p);
    nose.quaternion.setFromUnitVectors(Z, n);
    head.add(nose);
  }

  // 嘴：ω 形猫嘴 + 人中；说话时下方张开
  const mouth = new THREE.Group();
  {
    const { p, n } = onFace(0, -0.16, 0.001);
    mouth.position.copy(p);
    mouth.quaternion.setFromUnitVectors(Z, n);
    head.add(mouth);
  }
  const philtrum = mesh(new THREE.CapsuleGeometry(0.006, 0.018, 4, 8), M.line, 'head', { cast: false });
  philtrum.position.set(0, 0.016, 0.004);
  mouth.add(philtrum);
  const lips = [];
  for (const s of [-1, 1]) {
    const arcG = mesh(new THREE.TorusGeometry(0.027, 0.0068, 8, 24, Math.PI), M.line, 'head', { cast: false });
    arcG.rotation.z = Math.PI;
    arcG.position.set(0.027 * s, 0.004, 0.004);
    mouth.add(arcG);
    lips.push({ m: arcG, s });
  }
  const mouthOpen = mesh(new THREE.SphereGeometry(1, 32, 20), M.mouth, 'head', { cast: false });
  mouthOpen.visible = false;
  mouth.add(mouthOpen);
  const tongue = mesh(new THREE.SphereGeometry(1, 20, 14), M.tongue, 'head', { cast: false });
  tongue.visible = false;
  mouth.add(tongue);

  // 胡须：每侧三根，可整体抖动
  const whiskers = [];
  for (const s of [-1, 1]) {
    const pivot = new THREE.Group();
    const { p, n } = onFace(0.29 * s, -0.135, 0.002);
    pivot.position.copy(p);
    pivot.quaternion.setFromUnitVectors(Z, n);
    // 胡须贴着脸盘的弧面，末端停在毛绒边缘，不穿进兜帽
    for (const [ang, len] of [[0.2, 0.17], [0.02, 0.19], [-0.17, 0.165]]) {
      const ex = Math.cos(ang) * len;
      const ey = Math.sin(ang) * len;
      const { geo } = taperedTube(
        [[0, 0, 0.004], [s * ex * 0.5, ey * 0.5 + 0.004, -0.004], [s * ex, ey - 0.008, -0.04]],
        0.0045, 0.4, 16, 5,
      );
      pivot.add(mesh(geo, M.whisker, 'head', { cast: false }));
    }
    head.add(pivot);
    whiskers.push({ pivot, s });
  }

  // 腮红
  for (const s of [-1, 1]) {
    const { p, n } = onFace(0.3 * s, -0.085, 0.004);
    const c = new THREE.Mesh(new THREE.CircleGeometry(0.07, 32), M.blush);
    c.position.copy(p);
    c.quaternion.setFromUnitVectors(Z, n);
    c.scale.set(1.3, 0.8, 1);
    c.userData.part = 'head';
    head.add(c);
  }

  // 思考时绕头运行的三颗小银珠
  const dotMat = new THREE.MeshPhysicalMaterial({
    color: 0x9fb3d6, metalness: 0.6, roughness: 0.25, clearcoat: 1, transparent: true, opacity: 1,
  });
  const dots = [0, 1, 2].map(() => {
    const d = new THREE.Mesh(new THREE.SphereGeometry(0.06, 20, 14), dotMat);
    d.castShadow = false;
    head.add(d);
    return d;
  });

  // ---------- 参数写入 ----------
  const tmpP = new THREE.Vector3();
  const tmpN = new THREE.Vector3();
  const tmpV = new THREE.Vector3();
  const handA = new THREE.Vector3();
  const handB = new THREE.Vector3();

  function setLid(plane, nx, ny, c) {
    tmpN.set(nx, ny, 0);
    const len = tmpN.length();
    plane.normal.copy(tmpN).divideScalar(len);
    plane.constant = c / len;
  }

  function apply(P, time) {
    root.position.set(P.rootX, P.rootY, 0);
    root.rotation.set(P.lean, P.turn, P.sway);
    const sq = P.squash;
    squash.scale.set(1 - sq * 0.5, 1 + sq, 1 - sq * 0.5);

    blob.position.x = P.rootX;
    const lift = Math.max(P.rootY, 0);
    const bs = 1 / (1 + lift * 1.6);
    blob.scale.set(bs * (1 + sq * 0.4), bs * (1 + sq * 0.4), 1);
    M.shadow.opacity = 0.3 * bs;

    neck.rotation.set(P.headPitch, P.headYaw, P.headRoll);

    for (const key of ['L', 'R']) {
      const a = arms[key];
      const s = a.s;
      a.shoulder.position.y = 0.66 + P.shoulderUp;
      a.shoulder.rotation.set(P[`arm${key}Pitch`], s * P[`arm${key}Twist`], s * P[`arm${key}Abd`]);
      a.elbow.rotation.x = P[`arm${key}Elbow`];
    }

    // 耳朵：earBack 正值向后贴（不满/害怕），负值向前竖（专注）；earOut 向两侧耷拉（委屈/困）
    for (const key of ['L', 'R']) {
      const e = ears[key];
      const asym = (key === 'L' ? 1 : -1) * (P.earAsym ?? 0);
      e.pivot.rotation.x = -((P.earBack ?? 0) + asym) * 0.85;
      e.pivot.rotation.z = -e.s * (0.1 + (P.earOut ?? 0) * 0.95);
      e.pivot.rotation.y = e.s * (P.earBack ?? 0) * 0.35;
    }

    // 尾巴：抬起角度 + 沿关节传播的摆动波
    const tUp = P.tailUp ?? 0.5;
    tailBase.rotation.set(-(Math.PI / 2 - (0.2 + tUp * 1.15)), -1.05 + tUp * 0.15, 0);
    const ph = P.tailPhase ?? time;
    const wag = P.tailWag ?? 0.2;
    const curl = P.tailCurl ?? 0;
    for (let i = 0; i < tailJoints.length; i++) {
      const j = tailJoints[i];
      const k = i / (tailJoints.length - 1);
      j.rotation.x = 0.1 + 0.12 * k * tUp;
      // 默认向外侧微弯成 S 形；curl 时整条卷向身体
      j.rotation.z = Math.sin(ph - i * 0.7) * wag * (0.18 + 0.2 * k) - 0.06 * (1 - k) + curl * 0.3;
    }

    // 胡须
    for (const w of whiskers) {
      w.pivot.rotation.z = w.s * ((P.whisker ?? 0) * 0.22 + Math.sin(time * 1.3 + w.s) * 0.015);
    }

    // 眼睛位置（视线）与眼睑
    const lookX = P.eyeX * 0.04;
    const lookY = P.eyeY * 0.03;
    const happy = P.eyeMode === 'happy';
    for (const key of ['L', 'R']) {
      const e = eyes[key];
      const { p, n } = onFace(e.baseX + lookX, e.baseY + lookY, 0);
      e.socket.position.copy(p);
      e.socket.quaternion.setFromUnitVectors(Z, n);
    }
    root.updateMatrixWorld(true);

    const h = EH;
    for (const key of ['L', 'R']) {
      const e = eyes[key];
      const lowerLine = lerp(-h * 1.08, h * 0.25, P.lidBot);
      const upperLine = lerp(h * 1.08, lowerLine - 0.002, Math.min(P.lidTop, 1));
      const m = P.lidTilt * 0.45;
      setLid(e.upper, m * e.s, -1, upperLine);
      setLid(e.lower, 0, 1, -lowerLine);
      e.upper.applyMatrix4(e.socket.matrixWorld);
      e.lower.applyMatrix4(e.socket.matrixWorld);
      const closed = upperLine - lowerLine < 0.014;
      e.eye.visible = e.iris.visible = e.pupil.visible = !closed;
      e.hl[0].visible = e.hl[1].visible = !closed;
      e.arc.visible = closed;
      const ps = THREE.MathUtils.clamp(P.pupil ?? 1, 0.7, 1.3);
      e.pupil.scale.set(0.032 * ps, 0.042 * ps, 0.01);
      const lidDrop = 1 - upperLine / (h * 1.08);
      if (!closed && lidDrop > 0.14) {
        const yy = THREE.MathUtils.clamp(upperLine, -h * 0.98, h * 0.98);
        const halfW = EW * Math.sqrt(1 - (yy / h) ** 2);
        e.lashPivot.visible = true;
        e.lashPivot.position.set(0, upperLine, 0.03 * Math.sqrt(1 - (yy / h) ** 2) + 0.004);
        e.lashPivot.rotation.z = Math.atan(m * e.s);
        e.lash.scale.set(1, Math.max(halfW * 2 - 0.012, 0.01), 1);
      } else e.lashPivot.visible = false;
      if (closed) {
        if (happy) {
          e.arc.rotation.z = 0;
          e.arc.position.set(0, -0.035, 0.02);
          e.arc.scale.set(1, 0.85, 1);
        } else {
          e.arc.rotation.z = Math.PI;
          e.arc.position.set(0, lowerLine + 0.022, 0.02);
          e.arc.scale.set(1, 0.5, 1);
        }
      }
    }

    // 眉毛
    for (const key of ['L', 'R']) {
      const b = brows[key];
      const asym = key === 'R' ? P.browAsym : -P.browAsym * 0.4;
      b.inner.position.y = (P.browY + asym) * 0.03;
      b.inner.rotation.z = b.s * P.browTilt * 0.45;
    }

    // 眼镜
    glasses.position.y = P.glassesY;
    glasses.rotation.x = -P.glassesY * 2;

    // 嘴
    const open = Math.max(P.mouthOpen, 0);
    const width = 1 + P.mouthWide * 0.35;
    const sm = THREE.MathUtils.clamp(P.smile, -1, 1);
    for (const l of lips) {
      l.m.position.x = 0.027 * l.s * width;
      // 微笑：ω 更弯；不开心：翻成 ∩∩（撇嘴）
      const sy = sm >= -0.15 ? 0.55 + 0.6 * Math.max(sm, 0) : -0.55 + sm * 0.3;
      l.m.scale.set(width, sy, 1);
      l.m.position.y = 0.004 + (sy < 0 ? -0.012 : 0);
    }
    if (open > 0.06) {
      mouthOpen.visible = true;
      const mh = 0.012 + open * 0.06;
      mouthOpen.scale.set(0.034 * width + open * 0.012, mh, 0.02);
      mouthOpen.position.set(0, -0.008 - mh * 0.75, -0.002);
      tongue.visible = open > 0.22;
      tongue.scale.set(0.024 * width, 0.011 + open * 0.012, 0.014);
      tongue.position.set(0, -0.008 - mh * 1.25, 0.004);
    } else {
      mouthOpen.visible = tongue.visible = false;
    }

    M.blush.opacity = 0.25 + THREE.MathUtils.clamp(P.blush, 0, 1) * 0.6;

    // 兜帽软尖
    tuftPivot.rotation.set(P.tuftX * 0.8, 0, P.tuftZ * 0.8);

    // 思考小珠
    const dv = P.thinkDots;
    for (let i = 0; i < 3; i++) {
      const d = dots[i];
      if (dv < 0.02) {
        d.visible = false;
        continue;
      }
      d.visible = true;
      const a = time * 1.6 + (i * Math.PI * 2) / 3;
      const r = 1.0;
      tmpV.set(Math.cos(a) * r, 0.66 + Math.sin(a * 2) * 0.04, Math.sin(a) * r * 0.55);
      tmpV.applyAxisAngle(Z, 0.18);
      d.position.copy(tmpV);
      d.scale.setScalar(dv * (0.75 + 0.25 * Math.sin(time * 3 + i * 2.1)));
    }
    dotMat.opacity = Math.min(dv * 1.4, 1);

    // 书：放在两爪之间
    if (P.book > 0.02) {
      book.visible = true;
      arms.L.hand.getWorldPosition(handA);
      arms.R.hand.getWorldPosition(handB);
      tmpP.addVectors(handA, handB).multiplyScalar(0.5);
      squash.worldToLocal(tmpP);
      book.position.copy(tmpP);
      book.position.z += 0.12;
      book.rotation.set(-1.95, 0, 0);
      book.scale.setScalar(P.book * 1.2);
    } else {
      book.visible = false;
    }
  }

  /**
   * 特征点（世界坐标），用于开屏动画：线稿的每个部位都对齐到 3D 模型上的对应位置。
   * 在默认姿态下调用。
   */
  function landmarks() {
    root.updateMatrixWorld(true);
    const H = (x, y, z) => head.localToWorld(new THREE.Vector3(x, y, z));
    const ear = (key) => {
      const pv = ears[key].pivot;
      return {
        tip: pv.localToWorld(new THREE.Vector3(0, 0.335, 0)),
        base: [pv.localToWorld(new THREE.Vector3(-0.185, -0.03, 0)), pv.localToWorld(new THREE.Vector3(0.185, -0.03, 0))],
      };
    };
    const lenses = (glasses.userData.lenses || []).map((L) => ({
      side: L.side,
      pts: L.shape.map((v) => head.localToWorld(new THREE.Vector3(v.x, v.y, 0).applyQuaternion(L.q).add(L.center))),
      center: head.localToWorld(L.center.clone()),
    }));
    const eye = (key) => {
      const e = eyes[key];
      const { p } = onFace(e.baseX, e.baseY, 0.02);
      return { c: H(p.x, p.y, p.z), x: H(p.x + EW, p.y, p.z), y: H(p.x, p.y + EH, p.z) };
    };
    const face = (x, y) => {
      const { p } = onFace(x, y, 0.01);
      return H(p.x, p.y, p.z);
    };
    const silhouette = [];
    for (let i = 0; i <= 48; i++) {
      // 从 0.08 开始：身体轮廓在最底部收成一个点，从这里起才是“站在地上”的宽度
      const y = 0.08 + (i / 48) * 0.86;
      const r = Math.max(bodyRadiusAt(y) + 0.032, outfit.radiusAt(y));
      silhouette.push({ y, l: squash.localToWorld(new THREE.Vector3(-r, y, 0)), r: squash.localToWorld(new THREE.Vector3(r, y, 0)) });
    }
    return {
      head: H(0, 0, 0),
      hoodX: H(HA + 0.045, 0, 0),
      hoodY: H(0, HB + 0.045, 0),
      ears: [ear('L'), ear('R')],
      lenses,
      browTop: glasses.userData.browTop,
      eyes: [eye('L'), eye('R')],
      nose: face(0, -0.105),
      noseW: face(0.03, -0.105),
      mouth: face(0, -0.16),
      mouthW: face(0.054, -0.16),
      whiskers: [-1, 1].map((s) => ({
        root: face(0.29 * s, -0.135),
        ends: [[0.2, 0.17], [0.02, 0.19], [-0.17, 0.165]].map(([a, len]) => face((0.29 + Math.cos(a) * len) * s, -0.135 + Math.sin(a) * len)),
      })),
      ground: squash.localToWorld(new THREE.Vector3(0, 0, 0)),
      // 兜帽顶端软尖的轮廓（左根 → 左侧 → 尖 → 右侧 → 右根）
      tuft: [[-0.125, -0.06, 0], [-0.07, 0.12, 0], [0.13, 0.215, -0.09], [0.1, 0.1, -0.03], [0.125, -0.06, 0]].map(([x, y, z]) =>
        tuftPivot.localToWorld(new THREE.Vector3(x, y, z)),
      ),
      // 脸盘边缘（从最左点开始，经上方顺时针一圈）
      facePlate: Array.from({ length: 73 }, (_, i) => {
        const a = Math.PI - (i / 72) * Math.PI * 2;
        return H(FA * Math.cos(a), FY + FB * Math.sin(a), FZ + 0.01);
      }),
      silhouette,
    };
  }

  const anchors = { head, neck, body: body.userData.base, hands: [arms.L.hand, arms.R.hand], landmarks };
  return { root, blob, apply, anchors, look };
}
