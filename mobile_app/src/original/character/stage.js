/**
 * 渲染舞台：透明背景 WebGL 画布，可嵌入任意容器。
 * - 柔光棚布光（主光 + 冷色轮廓光 + 补光 + 环境反射）+ 软阴影，形成 2.5D/3D 体积感
 * - 指针视差：镜头随指针/设备轻微环绕，强化立体感
 * - 性能：标签页隐藏时停止渲染；休息状态降到 24fps；像素比上限 2
 */
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { buildCharacter } from './model.js';
import { Brain } from './brain.js';

export class Stage {
  constructor(host, opts = {}) {
    this.host = host;
    this.opts = { fov: 22, parallax: true, ...opts };
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;
    renderer.localClippingEnabled = true;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.setClearColor(0x000000, 0);
    this.renderer = renderer;
    this.canvas = renderer.domElement;
    this.canvas.className = 'xb-canvas';
    this.canvas.setAttribute('aria-hidden', 'true');
    host.appendChild(this.canvas);

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environmentIntensity = 0.42;
    this.scene = scene;

    const key = new THREE.DirectionalLight(0xfff4ea, 2.5);
    key.position.set(-0.9, 5.8, 2.6);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.left = -1.6;
    key.shadow.camera.right = 1.6;
    key.shadow.camera.top = 2.8;
    key.shadow.camera.bottom = -0.6;
    key.shadow.camera.near = 1;
    key.shadow.camera.far = 12;
    key.shadow.bias = -0.0004;
    key.shadow.normalBias = 0.025;
    key.shadow.radius = 4;
    const rim = new THREE.DirectionalLight(0xbcd2ff, 1.7);
    rim.position.set(3, 2.6, -3.2);
    const fill = new THREE.DirectionalLight(0xe2e9fa, 0.4);
    fill.position.set(3.2, 1, 3);
    const hemi = new THREE.HemisphereLight(0xf2f5ff, 0xa9b3c2, 0.5);
    scene.add(key, key.target, rim, fill, hemi);

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(6, 6),
      new THREE.ShadowMaterial({ color: 0x14203a, opacity: 0.1 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    this.model = buildCharacter(this.opts.look);
    scene.add(this.model.root, this.model.blob);
    this.brain = new Brain(this.model);

    this.camera = new THREE.PerspectiveCamera(this.opts.fov, 1, 0.1, 60);
    this.target = new THREE.Vector3(0, 1.17, 0);
    this.parallax = { x: 0, y: 0, tx: 0, ty: 0 };
    this.raycaster = new THREE.Raycaster();
    this.ndc = new THREE.Vector2();

    this.timer = new THREE.Timer();
    this.timeScale = 1;
    this.acc = 0;
    this.running = true;
    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(host);
    this._vis = () => {
      if (!document.hidden) this.timer.reset?.();
    };
    document.addEventListener('visibilitychange', this._vis);
    this._loop = this._loop.bind(this);
    requestAnimationFrame(this._loop);
  }

  _resize() {
    const r = this.host.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width));
    const h = Math.max(1, Math.round(r.height));
    if (w === this.w && h === this.h) return;
    this.w = w;
    this.h = h;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this._frame();
    this.render();
  }

  _frame() {
    // 让整个角色（含举手、跳起的空间）完整落在画面内
    const fov = THREE.MathUtils.degToRad(this.camera.fov);
    const H = this.opts.frameHeight ?? 2.75;
    const W = this.opts.frameWidth ?? 2.25;
    const t = Math.tan(fov / 2);
    this.dist = Math.max(H / 2 / t, W / 2 / (t * this.camera.aspect));
    this.camera.updateProjectionMatrix();
  }

  /** 更换眼镜 / 服装：重建模型，行为状态（弹簧、动作、状态机）保持不变 */
  setLook(look) {
    const cur = this.model.look;
    if (cur && cur.glasses === look.glasses && cur.outfit === look.outfit) return;
    const old = this.model;
    this.scene.remove(old.root, old.blob);
    old.root.traverse((o) => {
      o.geometry?.dispose();
    });
    this.model = buildCharacter(look);
    this.scene.add(this.model.root, this.model.blob);
    this.brain.model = this.model;
    this.brain.update(0.001);
    this.render();
  }

  setParallax(x, y) {
    this.parallax.tx = Math.max(-1, Math.min(1, x));
    this.parallax.ty = Math.max(-1, Math.min(1, y));
  }

  hitTest(clientX, clientY) {
    const r = this.canvas.getBoundingClientRect();
    this.ndc.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.ndc, this.camera);
    const hits = this.raycaster.intersectObject(this.model.root, true);
    const hit = hits.find((h) => h.object.visible && h.object.userData.part);
    return hit ? hit.object.userData.part : null;
  }

  /** 角色头部在页面中的屏幕坐标（用于气泡定位、视线计算） */
  headScreenPos() {
    const v = new THREE.Vector3();
    this.model.anchors.head.getWorldPosition(v);
    v.project(this.camera);
    const r = this.canvas.getBoundingClientRect();
    return { x: r.left + ((v.x + 1) / 2) * r.width, y: r.top + ((1 - v.y) / 2) * r.height };
  }

  _loop(ts) {
    if (!this.running) return;
    requestAnimationFrame(this._loop);
    if (document.hidden) return;
    this.timer.update(ts);
    const dt = this.timer.getDelta();
    // 休息时降帧
    const minDt = this.brain.state === 'rest' ? 1 / 24 : 0;
    this.acc += dt;
    if (this.acc < minDt) return;
    const step = this.acc;
    this.acc = 0;
    // timeScale：开屏动画的慢放 / 暂停（0 时不推进角色动画，只重绘）
    if (this.timeScale > 0) this.brain.update(step * this.timeScale);
    this.render(step);
  }

  render(dt = 0.016) {
    const p = this.parallax;
    const k = 1 - Math.exp(-dt * 4);
    const amp = this.opts.parallax && !this.brain.reducedMotion ? 1 : 0;
    p.x += (p.tx * amp - p.x) * k;
    p.y += (p.ty * amp - p.y) * k;
    const az = p.x * 0.16;
    const el = 0.07 + p.y * 0.06;
    const d = this.dist || 8;
    this.camera.position.set(
      this.target.x + Math.sin(az) * Math.cos(el) * d,
      this.target.y + Math.sin(el) * d,
      this.target.z + Math.cos(az) * Math.cos(el) * d,
    );
    this.camera.lookAt(this.target);
    this.renderer.render(this.scene, this.camera);
    if (!this.shown) {
      // 第一帧画好后再淡入，避免出现空白画布或闪烁
      this.shown = true;
      requestAnimationFrame(() => this.canvas.classList.add('is-ready'));
    }
  }

  /** 释放所有 GPU 资源与 WebGL 上下文（单页应用里反复挂载/卸载时必须调用） */
  destroy() {
    this.running = false;
    this._ro.disconnect();
    document.removeEventListener('visibilitychange', this._vis);
    const textures = new Set();
    this.scene.traverse((o) => {
      o.geometry?.dispose();
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      for (const m of mats) {
        for (const v of Object.values(m)) if (v && v.isTexture) textures.add(v);
        m.dispose();
      }
    });
    textures.forEach((t) => t.dispose());
    this.scene.environment?.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.canvas.remove();
  }
}
