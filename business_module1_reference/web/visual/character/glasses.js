/**
 * 小博士的眼镜款式。每款由镜框轮廓（2D 闭合曲线）+ 粗细 + 材质 + 桥/镜腿/配件组成，
 * 镜框贴着脸盘的弧面摆放。所有款式共用 apply() 里的 glassesY 推眼镜动作。
 */
import * as THREE from 'three';

export const GLASSES = {
  round: '黑色细框圆镜',
  wire: '金丝细圆镜',
  tortoise: '玳瑁粗框',
  browline: '眉线框',
  halfmoon: '半月老花镜 + 眼镜链',
};

const Z = new THREE.Vector3(0, 0, 1);

function superellipse(w, h, n, N = 72, mod) {
  const pts = [];
  for (let i = 0; i < N; i++) {
    const a = (i / N) * Math.PI * 2;
    const c = Math.cos(a);
    const s = Math.sin(a);
    let x = Math.sign(c) * Math.abs(c) ** (2 / n) * w;
    let y = Math.sign(s) * Math.abs(s) ** (2 / n) * h;
    if (mod) [x, y] = mod(x, y, a);
    pts.push(new THREE.Vector2(x, y));
  }
  return pts;
}

function halfMoon(w, h) {
  const pts = [];
  // 下半圆弧（从右上角顺时针到左上角）
  for (let i = 0; i <= 40; i++) {
    const a = -i / 40 * Math.PI;
    pts.push(new THREE.Vector2(Math.cos(a) * w, Math.sin(a) * h));
  }
  // 平直的上沿（从左到右）
  for (let i = 1; i < 12; i++) pts.push(new THREE.Vector2(-w + (2 * w * i) / 12, 0.004));
  return pts;
}

function tortoiseTexture(canvasTex) {
  return canvasTex(256, (g, s) => {
    g.fillStyle = '#7a4a22';
    g.fillRect(0, 0, s, s);
    const cols = ['rgba(176,110,48,0.8)', 'rgba(46,22,8,0.75)', 'rgba(214,150,70,0.7)', 'rgba(120,66,26,0.7)'];
    for (let i = 0; i < 90; i++) {
      const x = Math.random() * s;
      const y = Math.random() * s;
      const r = 6 + Math.random() * 26;
      const grd = g.createRadialGradient(x, y, 0, x, y, r);
      grd.addColorStop(0, cols[i % cols.length]);
      grd.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = grd;
      g.fillRect(x - r, y - r, r * 2, r * 2);
    }
  });
}

export function buildGlasses(style, k) {
  const { mesh, onFace, canvasTex } = k;
  const mats = {
    black: new THREE.MeshPhysicalMaterial({ color: 0x15171c, roughness: 0.25, clearcoat: 1, clearcoatRoughness: 0.1 }),
    gold: new THREE.MeshStandardMaterial({ color: 0xd4ae68, metalness: 1, roughness: 0.26 }),
    silver: new THREE.MeshStandardMaterial({ color: 0xc9d0da, metalness: 1, roughness: 0.22 }),
    brow: new THREE.MeshPhysicalMaterial({ color: 0x23262e, roughness: 0.3, clearcoat: 1, clearcoatRoughness: 0.12 }),
    lens: new THREE.MeshPhysicalMaterial({
      color: 0xe4ecf7, roughness: 0.04, transparent: true, opacity: 0.14, clearcoat: 1, depthWrite: false, side: THREE.DoubleSide,
    }),
    pad: new THREE.MeshPhysicalMaterial({ color: 0xeef3f8, roughness: 0.1, transparent: true, opacity: 0.7, clearcoat: 1 }),
    bead: new THREE.MeshPhysicalMaterial({ color: 0x2f5bd3, roughness: 0.2, clearcoat: 1 }),
  };
  if (style === 'tortoise') {
    const t = tortoiseTexture(canvasTex);
    t.repeat.set(6, 1);
    mats.tortoise = new THREE.MeshPhysicalMaterial({ map: t, roughness: 0.28, clearcoat: 1, clearcoatRoughness: 0.06 });
  }

  // 款式参数：轮廓、镜框粗细、材质、中心高度、铰链与鼻梁连接点、镜腿粗细
  const SPEC = {
    round: { shape: superellipse(0.152, 0.152, 2), tube: 0.009, mat: mats.black, cy: 0, hinge: [0.152, 0.015], inner: [0.148, 0.03], bridgeLift: 0.04, temple: 0.008 },
    wire: { shape: superellipse(0.145, 0.145, 2), tube: 0.0055, mat: mats.gold, cy: 0, hinge: [0.145, 0.02], inner: [0.142, 0.045], bridgeLift: 0.05, temple: 0.0055, pads: true },
    tortoise: {
      shape: superellipse(0.158, 0.138, 3.2), tube: 0.018, mat: mats.tortoise, cy: 0.005,
      hinge: [0.16, 0.06], inner: [0.155, 0.03], bridgeLift: 0.012, temple: 0.014, bridgeTube: 0.016,
    },
    browline: {
      shape: superellipse(0.156, 0.132, 2.5, 72, (x, y) => [x, y > 0 ? y * 0.9 : y]),
      tube: 0.0055, mat: mats.silver, cy: 0.005, hinge: [0.157, 0.07], inner: [0.15, 0.06], bridgeLift: 0.008,
      temple: 0.012, templeMat: mats.brow, browTop: true, bridgeTube: 0.016, bridgeMat: mats.brow, pads: true,
    },
    halfmoon: {
      shape: halfMoon(0.13, 0.1), tube: 0.0055, mat: mats.gold, cy: -0.05, off: 0.085, flat: 0.92, hinge: [0.13, 0.004], inner: [0.13, 0.004],
      bridgeLift: 0.03, temple: 0.0055, chain: true,
    },
  };
  const S = SPEC[style] || SPEC.browline;
  const g = new THREE.Group();
  const hinges = [];
  const inners = [];
  // 镜框轮廓的几何信息（头部局部坐标），供开屏动画把线稿精确对齐到 3D 眼镜
  g.userData.lenses = [];
  g.userData.browTop = !!S.browTop;
  const lensShape = new THREE.Shape(S.shape);

  for (const s of [-1, 1]) {
    const { p, n } = onFace(0.205 * s, S.cy, S.off ?? 0.065);
    // 镜片平面只部分跟随脸盘弧度；位置偏低的款式更竖直，避免下沿陷进脸里
    const q = new THREE.Quaternion().setFromUnitVectors(Z, n.clone().lerp(Z, S.flat ?? 0.5).normalize());
    const rimG = new THREE.Group();
    rimG.position.copy(p);
    rimG.quaternion.copy(q);
    const curve = new THREE.CatmullRomCurve3(S.shape.map((v) => new THREE.Vector3(v.x, v.y, 0)), true, 'centripetal');
    rimG.add(mesh(new THREE.TubeGeometry(curve, 128, S.tube, 10, true), S.mat, 'head'));
    if (S.browTop) {
      // 眉线框：上半圈加粗的深色“眉毛”
      const top = S.shape.filter((v) => v.y > -0.025).sort((a, b) => a.x - b.x);
      const tc = new THREE.CatmullRomCurve3(top.map((v) => new THREE.Vector3(v.x, v.y + 0.006, 0.004)), false, 'centripetal');
      const tm = mesh(new THREE.TubeGeometry(tc, 64, 0.019, 10, false), mats.brow, 'head');
      tm.scale.set(1, 1, 0.75);
      rimG.add(tm);
    }
    const lens = mesh(new THREE.ShapeGeometry(lensShape, 24), mats.lens, 'head', { cast: false });
    lens.renderOrder = 2;
    rimG.add(lens);
    if (S.pads) {
      for (const dz of [0]) {
        const pad = mesh(new THREE.SphereGeometry(1, 12, 8), mats.pad, 'head', { cast: false });
        pad.scale.set(0.012, 0.02, 0.008);
        pad.position.set(-s * 0.11, -0.075, -0.03 + dz);
        rimG.add(pad);
      }
    }
    g.add(rimG);
    g.userData.lenses.push({ center: p.clone(), q: q.clone(), shape: S.shape.map((v) => v.clone()), side: s });
    hinges.push(new THREE.Vector3(s * S.hinge[0], S.hinge[1], 0).applyQuaternion(q).add(p));
    inners.push(new THREE.Vector3(-s * S.inner[0], S.inner[1], 0).applyQuaternion(q).add(p));
  }

  // 镜腿
  hinges.forEach((h, i) => {
    const s = i === 0 ? -1 : 1;
    const temple = new THREE.CatmullRomCurve3([
      h.clone().add(new THREE.Vector3(s * 0.004, 0, -0.02)),
      new THREE.Vector3(s * 0.56, 0.03 + S.cy * 0.3, 0.42),
      new THREE.Vector3(s * 0.7, 0.05, 0.12),
    ]);
    const tm = mesh(new THREE.TubeGeometry(temple, 20, S.temple, 8), S.templeMat || S.mat, 'head');
    g.add(tm);
  });

  // 鼻梁
  {
    const [a, b] = inners;
    const mid = a.clone().add(b).multiplyScalar(0.5).add(new THREE.Vector3(0, S.bridgeLift, 0.04));
    const bridge = new THREE.QuadraticBezierCurve3(a, mid, b);
    g.add(mesh(new THREE.TubeGeometry(bridge, 20, S.bridgeTube || S.tube * 1.05, 8), S.bridgeMat || S.mat, 'head'));
    if (style === 'browline') {
      // 下方的细金属鼻托梁
      const a2 = a.clone().add(new THREE.Vector3(0, -0.05, 0));
      const b2 = b.clone().add(new THREE.Vector3(0, -0.05, 0));
      const m2 = a2.clone().add(b2).multiplyScalar(0.5).add(new THREE.Vector3(0, 0.02, 0.03));
      g.add(mesh(new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(a2, m2, b2), 16, 0.005, 6), mats.silver, 'head'));
    }
  }

  // 眼镜链（半月老花镜）：金色细链 + 蓝色小珠
  if (S.chain) {
    const [hl, hr] = hinges;
    const curve = new THREE.CatmullRomCurve3([
      hl.clone().add(new THREE.Vector3(-0.01, -0.01, -0.03)),
      new THREE.Vector3(-0.47, -0.25, 0.4),
      new THREE.Vector3(-0.36, -0.56, 0.5),
      new THREE.Vector3(0, -0.68, 0.54),
      new THREE.Vector3(0.36, -0.56, 0.5),
      new THREE.Vector3(0.47, -0.25, 0.4),
      hr.clone().add(new THREE.Vector3(0.01, -0.01, -0.03)),
    ]);
    g.add(mesh(new THREE.TubeGeometry(curve, 120, 0.0032, 5), mats.gold, 'head', { cast: false }));
    for (let i = 1; i < 24; i++) {
      const b = mesh(new THREE.SphereGeometry(i % 3 === 0 ? 0.009 : 0.006, 10, 8), i % 3 === 0 ? mats.bead : mats.gold, 'head', { cast: false });
      b.position.copy(curve.getPointAt(i / 24));
      g.add(b);
    }
  }
  return g;
}
