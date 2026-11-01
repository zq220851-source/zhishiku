/**
 * 小博士的服装款式。
 * 每款由：躯干布料（旋转体 + 程序化贴图）、领口（V 领 / 衬衫领）、里层（衬衫 / 领带 / 领结）、
 * 边饰、纽扣、口袋配件、袖子（可选，长袖或短袖）组成。
 * 返回 { sleeve }，供手臂决定用毛绒还是布料袖子。
 */
import * as THREE from 'three';

export const OUTFITS = {
  argyle: '菱格针织背心',
  labcoat: '白大褂',
  cardigan: '海军蓝开衫',
  shirt: '条纹衬衫 + 领结',
};

const Z = new THREE.Vector3(0, 0, 1);
const lerp = (a, b, t) => a + (b - a) * t;

// ---------- 布料贴图 ----------
function argyle(canvasTex) {
  return canvasTex(256, (g, s) => {
    g.fillStyle = '#9ea5b0';
    g.fillRect(0, 0, s, s);
    g.fillStyle = '#3f5784';
    g.beginPath();
    g.moveTo(s / 2, s * 0.1);
    g.lineTo(s * 0.8, s / 2);
    g.lineTo(s / 2, s * 0.9);
    g.lineTo(s * 0.2, s / 2);
    g.closePath();
    g.fill();
    g.strokeStyle = 'rgba(236,239,244,0.7)';
    g.lineWidth = s * 0.014;
    g.setLineDash([s * 0.05, s * 0.04]);
    g.beginPath();
    g.moveTo(0, 0);
    g.lineTo(s, s);
    g.moveTo(s, 0);
    g.lineTo(0, s);
    g.stroke();
  });
}
function knitBump(canvasTex) {
  return canvasTex(64, (g, s) => {
    g.fillStyle = '#808080';
    g.fillRect(0, 0, s, s);
    for (let col = 0; col < 4; col++) {
      const x0 = (col * s) / 4;
      for (let row = 0; row < 4; row++) {
        const y0 = (row * s) / 4;
        const grd = g.createLinearGradient(x0, 0, x0 + s / 4, 0);
        grd.addColorStop(0, '#5a5a5a');
        grd.addColorStop(0.5, '#d8d8d8');
        grd.addColorStop(1, '#5a5a5a');
        g.strokeStyle = grd;
        g.lineWidth = s / 9;
        g.beginPath();
        g.moveTo(x0 + s * 0.02, y0);
        g.lineTo(x0 + s / 8, y0 + s / 6);
        g.lineTo(x0 + s / 4 - s * 0.02, y0);
        g.stroke();
      }
    }
  }, { srgb: false });
}
function ribBump(canvasTex) {
  return canvasTex(32, (g, s) => {
    const grd = g.createLinearGradient(0, 0, s, 0);
    grd.addColorStop(0, '#404040');
    grd.addColorStop(0.5, '#e0e0e0');
    grd.addColorStop(1, '#404040');
    g.fillStyle = grd;
    g.fillRect(0, 0, s, s);
  }, { srgb: false });
}
/** 斜纹棉布（白大褂） */
function twill(canvasTex) {
  return canvasTex(64, (g, s) => {
    g.fillStyle = '#808080';
    g.fillRect(0, 0, s, s);
    g.strokeStyle = '#b0b0b0';
    g.lineWidth = 3;
    for (let i = -s; i < s * 2; i += 8) {
      g.beginPath();
      g.moveTo(i, 0);
      g.lineTo(i + s, s);
      g.stroke();
    }
  }, { srgb: false });
}
/** 麻花针（开衫）：颜色贴图与凹凸共用同一张图 */
function cable(canvasTex, color = true) {
  return canvasTex(128, (g, s) => {
    g.fillStyle = color ? '#2b4068' : '#707070';
    g.fillRect(0, 0, s, s);
    // 两列麻花 + 中间的竖向罗纹
    for (const cx of [s * 0.25, s * 0.75]) {
      for (let k = 0; k < 2; k++) {
        const y0 = (k * s) / 2;
        for (const dir of [-1, 1]) {
          const grd = g.createLinearGradient(cx - 20, 0, cx + 20, 0);
          const hi = color ? '#4a6596' : '#e0e0e0';
          const lo = color ? '#223556' : '#404040';
          grd.addColorStop(0, lo);
          grd.addColorStop(0.5, hi);
          grd.addColorStop(1, lo);
          g.strokeStyle = grd;
          g.lineWidth = s * 0.11;
          g.beginPath();
          g.moveTo(cx - dir * 14, y0);
          g.bezierCurveTo(cx - dir * 14, y0 + s * 0.2, cx + dir * 14, y0 + s * 0.3, cx + dir * 14, y0 + s * 0.5);
          g.stroke();
        }
      }
    }
    g.strokeStyle = color ? '#33497a' : '#a0a0a0';
    g.lineWidth = 3;
    for (const x of [s * 0.5, 0]) {
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, s);
      g.stroke();
    }
  }, { srgb: color });
}
/** 牛津纺条纹（衬衫） */
function stripes(canvasTex) {
  return canvasTex(64, (g, s) => {
    g.fillStyle = '#cbdbf1';
    g.fillRect(0, 0, s, s);
    g.fillStyle = '#5f86c9';
    g.fillRect(0, 0, 6, s);
    g.fillRect(s / 2, 0, 3, s);
    g.fillStyle = 'rgba(255,255,255,0.7)';
    g.fillRect(8, 0, 2, s);
  });
}

export function buildOutfit(style, k) {
  const { mesh, canvasTex, bodyRadiusAt, BODY_Z, squash } = k;
  const tex = (t, rx, ry) => {
    t.repeat.set(rx, ry);
    return t;
  };

  const ribMat = (color) => new THREE.MeshStandardMaterial({ color, bumpMap: tex(ribBump(canvasTex), 90, 1), bumpScale: 1.6, roughness: 0.95 });
  const mats = {
    accent: new THREE.MeshPhysicalMaterial({ color: 0x2f5bd3, roughness: 0.32, clearcoat: 0.9 }),
    metal: new THREE.MeshStandardMaterial({ color: 0xc7cfdb, metalness: 1, roughness: 0.22 }),
    navy: new THREE.MeshPhysicalMaterial({ color: 0x1e3457, roughness: 0.55, sheen: 0.6, sheenColor: 0x5a78ab }),
    shirtWhite: new THREE.MeshPhysicalMaterial({ color: 0xf7f8fb, roughness: 0.7, sheen: 0.6, sheenColor: 0xe6ecf6 }),
    shirtBlue: new THREE.MeshPhysicalMaterial({ color: 0xa9c4ea, roughness: 0.75, sheen: 0.5, sheenColor: 0xe6ecf6 }),
  };

  // 款式定义
  const SPECS = {
    argyle: {
      y0: 0.27, y1: 0.9, out: 0.042, flareY: 0,
      mat: new THREE.MeshStandardMaterial({
        map: tex(argyle(canvasTex), 13, 2.6), bumpMap: tex(knitBump(canvasTex), 70, 20), bumpScale: 1.4, roughness: 0.95,
      }),
      v: { half: 0.075, y: 0.62 }, trim: { r: 0.022, mat: ribMat(0x7c8593) }, hem: 'rib', hemMat: ribMat(0x7c8593),
      buttons: { ys: [0.53, 0.43, 0.33], mat: new THREE.MeshPhysicalMaterial({ color: 0x2c3442, roughness: 0.3, clearcoat: 0.9 }) },
      pen: { u: 0.425, y: 0.78 },
    },
    labcoat: {
      y0: 0.16, y1: 0.9, out: 0.05, flareY: 0.32,
      mat: new THREE.MeshPhysicalMaterial({
        color: 0xdfe6f1, roughness: 0.6, clearcoat: 0.15, sheen: 0.8, sheenColor: 0xcfdcef, sheenRoughness: 0.4,
        bumpMap: tex(twill(canvasTex), 50, 14), bumpScale: 0.6,
      }),
      v: { half: 0.1, y: 0.46 }, trim: { r: 0.03, mat: null, flat: true }, hem: 'line', piping: 0x3f5f99,
      inner: { mat: mats.shirtBlue, tie: true },
      buttons: { ys: [0.42, 0.28], mat: new THREE.MeshPhysicalMaterial({ color: 0xe9edf3, roughness: 0.3, clearcoat: 0.8 }) },
      placket: true,
      pocket: { u: 0.42, y: 0.66 }, pen: { u: 0.42, y: 0.72 }, badge: { u: 0.585, y: 0.66 },
      sleeve: { color: 0xdfe6f1, short: false, cuff: 'line' },
    },
    cardigan: {
      y0: 0.25, y1: 0.9, out: 0.046, flareY: 0,
      mat: new THREE.MeshStandardMaterial({
        map: tex(cable(canvasTex), 16, 3), bumpMap: tex(cable(canvasTex, false), 16, 3), bumpScale: 2.2, roughness: 0.95,
      }),
      v: { half: 0.08, y: 0.5 }, trim: { r: 0.024, mat: ribMat(0x23365a) }, hem: 'rib', hemMat: ribMat(0x23365a),
      inner: { mat: mats.shirtWhite, collar: true },
      buttons: { ys: [0.45, 0.36, 0.27], mat: new THREE.MeshPhysicalMaterial({ color: 0xc9a67a, roughness: 0.35, clearcoat: 0.9 }) },
      pen: { u: 0.425, y: 0.74 },
      sleeve: { color: 0x2b4068, knit: true, short: false, cuff: 'rib' },
    },
    shirt: {
      y0: 0.25, y1: 0.9, out: 0.04, flareY: 0,
      mat: new THREE.MeshPhysicalMaterial({
        map: tex(stripes(canvasTex), 26, 1), roughness: 0.75, sheen: 0.5, sheenColor: 0xeef3fa,
      }),
      v: null, hem: 'line', placket: true, collar: true, bowtie: true,
      buttons: { ys: [0.68, 0.56, 0.44, 0.32], mat: new THREE.MeshPhysicalMaterial({ color: 0xf7f9fc, roughness: 0.3, clearcoat: 0.8 }) },
      pocket: { u: 0.42, y: 0.62 }, pen: { u: 0.42, y: 0.68 },
      sleeve: { color: 0xdbe6f5, stripes: true, short: true, cuff: 'line' },
    },
  };
  const S = SPECS[style] || SPECS.labcoat;
  const trimMat = S.trim?.mat || S.mat;

  // 躯干轮廓：低于 flareY 时保持外扩（白大褂的下摆）
  const rFlare = S.flareY ? bodyRadiusAt(S.flareY) : 0;
  const rT = (y, out = S.out) => {
    let r = bodyRadiusAt(y);
    if (S.flareY && y < S.flareY) r = Math.max(r, rFlare + (S.flareY - y) * 0.12);
    return r + out;
  };
  const point = (u, y, out = 0) => {
    const phi = -Math.PI + u * Math.PI * 2;
    const r = rT(y, S.out + out);
    return new THREE.Vector3(Math.sin(phi) * r, y, Math.cos(phi) * r * BODY_Z);
  };
  const normal = (u, y) => {
    const phi = -Math.PI + u * Math.PI * 2;
    const dr = (rT(y + 0.01) - rT(y - 0.01)) / 0.02;
    return new THREE.Vector3(Math.sin(phi), -dr, Math.cos(phi) / BODY_Z).normalize();
  };
  const onTorso = (obj, u, y, out = 0.004) => {
    obj.position.copy(point(u, y, out));
    obj.quaternion.setFromUnitVectors(Z, normal(u, y));
    return obj;
  };
  const latheBand = (y0, y1, out, mat, segs = 48) => {
    const pts = [];
    for (let i = 0; i <= segs; i++) {
      const y = lerp(y0, y1, i / segs);
      pts.push(new THREE.Vector2(rT(y, out), y));
    }
    const geo = new THREE.LatheGeometry(pts, 96, -Math.PI, Math.PI * 2);
    geo.scale(1, 1, BODY_Z);
    return mesh(geo, mat, 'body', { receive: true });
  };

  // 躯干（V 领用 alphaMap 裁出；v 与 y 线性对应）
  if (S.v) {
    const vv = (S.v.y - S.y0) / (S.y1 - S.y0);
    S.mat.alphaMap = canvasTex(256, (g, s) => {
      g.fillStyle = '#fff';
      g.fillRect(0, 0, s, s);
      g.fillStyle = '#000';
      g.beginPath();
      g.moveTo(s * (0.5 - S.v.half), 0);
      g.lineTo(s * (0.5 + S.v.half), 0);
      g.lineTo(s * 0.5, s * (1 - vv));
      g.closePath();
      g.fill();
    }, { srgb: false, repeat: false });
    S.mat.alphaTest = 0.5;
    S.mat.side = THREE.DoubleSide;
  }
  squash.add(latheBand(S.y0, S.y1, S.out, S.mat, 64));

  // 里层：衬衫（从 V 领里露出）
  if (S.inner) {
    squash.add(latheBand(S.v.y - 0.06, S.y1, S.out - 0.016, S.inner.mat, 24));
  }

  // V 领边饰
  if (S.v) {
    for (const s of [-1, 1]) {
      const pts = [];
      for (let i = 0; i <= 16; i++) {
        const t = i / 16;
        pts.push(point(0.5 + s * lerp(S.v.half, 0, t) - s * 0.004, lerp(S.y1, S.v.y, t), 0.004));
      }
      const tm = mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 32, S.trim.r, 10), trimMat, 'body');
      squash.add(tm);
      if (S.trim.flat) {
        // 白大褂翻领：在边缘外侧再叠一条较宽的翻领 + 明线
        const lap = [];
        const seam = [];
        for (let i = 0; i <= 16; i++) {
          const t = i / 16;
          const u = 0.5 + s * lerp(S.v.half + 0.035, 0.012, t);
          lap.push(point(u, lerp(S.y1, S.v.y + 0.02, t), 0.006));
          seam.push(point(u + s * 0.02, lerp(S.y1, S.v.y + 0.03, t), 0.012));
        }
        squash.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(lap), 32, 0.026, 10), S.mat, 'body'));
        squash.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(seam), 32, S.piping ? 0.0055 : 0.0035, 6), new THREE.MeshStandardMaterial({ color: S.piping || 0xc5cdd9, roughness: 0.6 }), 'body', { cast: false }));
      }
    }
  }

  // 前襟门襟线
  if (S.placket) {
    const top = S.v ? S.v.y : S.y1 - 0.08;
    const pts = [];
    for (let i = 0; i <= 12; i++) pts.push(point(0.5 + 0.012, lerp(top, S.y0 + 0.02, i / 12), 0.003));
    squash.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 24, 0.004, 5), new THREE.MeshStandardMaterial({ color: 0xa8b4c6 }), 'body', { cast: false }));
  }

  // 下摆
  if (S.hem === 'rib') {
    squash.add(latheBand(S.y0 - 0.035, S.y0 + 0.05, S.out + 0.012, S.hemMat, 8));
  } else {
    const pts = [];
    for (let i = 0; i <= 64; i++) pts.push(point(i / 64, S.y0 + 0.03, 0.003));
    squash.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 96, S.piping ? 0.007 : 0.004, 6, true), new THREE.MeshStandardMaterial({ color: S.piping || 0xa8b4c6, roughness: 0.6 }), 'body', { cast: false }));
  }

  // 纽扣
  if (S.buttons) {
    for (const y of S.buttons.ys) {
      const b = mesh(new THREE.SphereGeometry(0.024, 18, 12), S.buttons.mat, 'body');
      b.scale.set(1, 1, 0.5);
      squash.add(onTorso(b, 0.5, y, 0.006));
    }
  }

  // 领带（白大褂里层）
  if (S.inner?.tie) {
    const knot = mesh(new THREE.SphereGeometry(0.032, 16, 12), mats.navy, 'body');
    knot.scale.set(1, 0.85, 0.5);
    squash.add(onTorso(knot, 0.5, 0.8, -0.006));
    const shape = new THREE.Shape();
    shape.moveTo(-0.022, 0.0);
    shape.lineTo(0.022, 0.0);
    shape.lineTo(0.036, -0.2);
    shape.lineTo(0, -0.24);
    shape.lineTo(-0.036, -0.2);
    shape.closePath();
    const blade = mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.006, bevelEnabled: true, bevelSize: 0.004, bevelThickness: 0.004, bevelSegments: 2 }), mats.navy, 'body');
    squash.add(onTorso(blade, 0.5, 0.78, -0.008));
    blade.rotateX(-0.12);
  }

  // 衬衫领尖（开衫、衬衫）
  if (S.inner?.collar || S.collar) {
    const mat = S.collar ? S.mat : S.inner.mat;
    for (const s of [-1, 1]) {
      const shape = new THREE.Shape();
      shape.moveTo(0, 0);
      shape.lineTo(s * 0.11, -0.012);
      shape.lineTo(s * 0.035, -0.1);
      shape.closePath();
      const flap = mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.006, bevelEnabled: true, bevelSize: 0.006, bevelThickness: 0.005, bevelSegments: 2 }), mat, 'body');
      squash.add(onTorso(flap, 0.5 + s * 0.012, 0.83, S.collar ? 0.01 : -0.004));
      flap.rotateX(-0.25);
    }
  }

  // 领结
  if (S.bowtie) {
    const bow = new THREE.Group();
    for (const s of [-1, 1]) {
      const wing = mesh(new THREE.ConeGeometry(0.05, 0.085, 20), mats.navy, 'body');
      wing.rotation.z = (s * Math.PI) / 2;
      wing.position.x = s * 0.04;
      wing.scale.set(1, 1, 0.45);
      bow.add(wing);
    }
    const knot = mesh(new THREE.SphereGeometry(0.026, 16, 12), mats.navy, 'body');
    knot.scale.set(1, 1.05, 0.6);
    bow.add(knot);
    // 领结上的小圆点
    for (const [x, y] of [[-0.05, 0.012], [-0.035, -0.015], [0.05, -0.012], [0.035, 0.015]]) {
      const dot = mesh(new THREE.SphereGeometry(0.006, 8, 6), mats.shirtWhite, 'body', { cast: false });
      dot.position.set(x, y, 0.018);
      bow.add(dot);
    }
    bow.scale.setScalar(1.45);
    squash.add(onTorso(bow, 0.5, 0.8, 0.035));
  }

  // 口袋
  if (S.pocket) {
    const { u, y } = S.pocket;
    const pts = [[u - 0.04, y], [u - 0.04, y - 0.12], [u, y - 0.135], [u + 0.04, y - 0.12], [u + 0.04, y]]
      .map(([uu, yy]) => point(uu, yy, 0.004));
    squash.add(mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'catmullrom', 0.2), 32, 0.0035, 5), new THREE.MeshStandardMaterial({ color: 0xa8b4c6 }), 'body', { cast: false }));
    const top = new THREE.CatmullRomCurve3([point(u - 0.042, y, 0.005), point(u, y + 0.003, 0.005), point(u + 0.042, y, 0.005)]);
    squash.add(mesh(new THREE.TubeGeometry(top, 10, 0.006, 6), new THREE.MeshStandardMaterial({ color: 0xb9c4d4 }), 'body', { cast: false }));
  } else if (S.pen) {
    const { u, y } = S.pen;
    const slit = new THREE.CatmullRomCurve3([point(u - 0.03, y - 0.02, 0.003), point(u, y - 0.015, 0.003), point(u + 0.03, y - 0.02, 0.003)]);
    squash.add(mesh(new THREE.TubeGeometry(slit, 10, 0.006, 6), S.trim?.mat || S.mat, 'body', { cast: false }));
  }
  // 钢笔
  if (S.pen) {
    const { u, y } = S.pen;
    const pen = new THREE.Group();
    onTorso(pen, u, y, -0.004);
    pen.rotateZ(0.1);
    const barrel = mesh(new THREE.CapsuleGeometry(0.019, 0.1, 6, 14), mats.accent, 'body');
    const clip = mesh(new THREE.BoxGeometry(0.009, 0.07, 0.008), mats.metal, 'body');
    clip.position.set(0, 0.0, 0.021);
    pen.add(barrel, clip);
    squash.add(pen);
  }
  // 胸卡（白大褂）
  if (S.badge) {
    const { u, y } = S.badge;
    const card = new THREE.Group();
    onTorso(card, u, y, 0.012);
    const body = mesh(new THREE.BoxGeometry(0.1, 0.13, 0.006), mats.shirtWhite, 'body');
    const band = mesh(new THREE.BoxGeometry(0.1, 0.03, 0.007), mats.accent, 'body');
    band.position.y = 0.05;
    const photo = mesh(new THREE.BoxGeometry(0.032, 0.04, 0.007), new THREE.MeshStandardMaterial({ color: 0xc8d2e0 }), 'body', { cast: false });
    photo.position.set(-0.022, -0.005, 0.001);
    const line1 = mesh(new THREE.BoxGeometry(0.036, 0.006, 0.007), new THREE.MeshStandardMaterial({ color: 0x9aa6b8 }), 'body', { cast: false });
    line1.position.set(0.022, 0.005, 0.001);
    const line2 = line1.clone();
    line2.position.y = -0.012;
    const clipM = mesh(new THREE.BoxGeometry(0.02, 0.03, 0.01), mats.metal, 'body');
    clipM.position.y = 0.075;
    card.add(body, band, photo, line1, line2, clipM);
    squash.add(card);
  }

  // 袖子材质
  let sleeve = null;
  if (S.sleeve) {
    const sl = S.sleeve;
    let mat;
    if (sl.knit) {
      mat = new THREE.MeshStandardMaterial({ map: tex(cable(canvasTex), 3, 1), bumpMap: tex(cable(canvasTex, false), 3, 1), bumpScale: 2, roughness: 0.95 });
    } else if (sl.stripes) {
      mat = new THREE.MeshPhysicalMaterial({ map: tex(stripes(canvasTex), 4, 1), roughness: 0.75, sheen: 0.5, sheenColor: 0xeef3fa });
    } else {
      mat = S.mat;
    }
    sleeve = {
      mat,
      short: sl.short,
      cuffMat: sl.cuff === 'rib' ? ribMat(0x23365a) : new THREE.MeshStandardMaterial({ color: S.piping || 0xa8b4c6, roughness: 0.7 }),
      cuffR: sl.cuff === 'rib' ? 0.03 : S.piping ? 0.012 : 0.006,
    };
  }
  // 躯干外轮廓半径（不在衣服范围内时返回 0），供开屏动画计算剪影
  const radiusAt = (y) => (y >= S.y0 - 0.035 && y <= S.y1 ? rT(y) + (S.hem === 'rib' && y < S.y0 + 0.05 ? 0.012 : 0) : 0);
  return { sleeve, radiusAt };
}
