/**
 * 指针交互：视线跟随、悬停、点击（按部位命中）、拖动、键盘。
 * 点击只在真正点到角色几何体时生效（射线检测），透明区域不拦截意图。
 */
/** 轻触觉反馈（仅支持的安卓设备；减少动画时不振动） */
function haptic(ms) {
  if (document.documentElement.classList.contains('rm')) return;
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* 部分浏览器在无用户手势时抛错 */
  }
}

export function attachPointerInteractions(stage, host, opts = {}) {
  const { brain } = stage;
  const o = { draggable: true, onTap: null, onDragStart: null, onDragMove: null, onDragEnd: null, ...opts };
  let down = null;
  let dragging = false;
  let vx = 0;
  let vy = 0;
  let lastMove = null;

  host.tabIndex = host.tabIndex >= 0 ? host.tabIndex : 0;
  host.setAttribute('role', host.getAttribute('role') || 'button');

  const onWindowMove = (e) => {
    if (e.pointerType === 'touch' && !down) return; // 触屏没有悬停，不追随
    const hp = stage.headScreenPos();
    const dx = e.clientX - hp.x;
    const dy = e.clientY - hp.y;
    const dist = Math.hypot(dx, dy) || 1;
    const reach = Math.min(dist / 380, 1);
    brain.setPointer((dx / dist) * reach, (-dy / dist) * reach);
    stage.setParallax((dx / window.innerWidth) * 1.4, (dy / window.innerHeight) * 1.2);
  };
  window.addEventListener('pointermove', onWindowMove, { passive: true });

  const onHostMove = (e) => {
    if (down) {
      const mx = e.clientX - down.x;
      const my = e.clientY - down.y;
      if (!dragging && o.draggable && Math.hypot(mx, my) > 7) {
        dragging = true;
        host.setPointerCapture?.(e.pointerId);
        host.style.cursor = 'grabbing';
        haptic(10);
        brain.dragStart();
        o.onDragStart?.();
        host.classList.add('is-dragging');
      }
      if (dragging) {
        const now = performance.now();
        if (lastMove) {
          const dt = Math.max((now - lastMove.t) / 1000, 1 / 240);
          const ivx = (e.clientX - lastMove.x) / dt;
          const ivy = (e.clientY - lastMove.y) / dt;
          vx += (ivx - vx) * 0.3;
          vy += (ivy - vy) * 0.3;
        }
        lastMove = { x: e.clientX, y: e.clientY, t: now };
        brain.dragMove(vx, vy);
        o.onDragMove?.(e.clientX, e.clientY, down);
      }
      return;
    }
    if (e.pointerType !== 'touch') {
      const part = stage.hitTest(e.clientX, e.clientY);
      brain.setHover(!!part);
      host.style.cursor = part ? (o.draggable ? 'grab' : 'pointer') : '';
    }
  };

  const onDown = (e) => {
    const part = stage.hitTest(e.clientX, e.clientY);
    if (!part) return;
    e.preventDefault();
    down = { x: e.clientX, y: e.clientY, part, rect: host.getBoundingClientRect() };
    lastMove = null;
    vx = vy = 0;
  };

  const onUp = (e) => {
    if (!down) return;
    if (dragging) {
      dragging = false;
      host.classList.remove('is-dragging');
      brain.dragEnd();
      o.onDragEnd?.(e.clientX, e.clientY, vx, vy);
    } else {
      brain.poke(down.part);
      if (e.pointerType === 'touch') haptic(6);
      o.onTap?.(down.part);
    }
    host.style.cursor = '';
    down = null;
  };

  const onLeave = () => {
    if (!down) brain.setHover(false);
  };

  const onKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      brain.poke('body');
      o.onTap?.('keyboard');
    }
  };

  host.addEventListener('pointermove', onHostMove);
  host.addEventListener('pointerdown', onDown);
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);
  host.addEventListener('pointerleave', onLeave);
  host.addEventListener('keydown', onKey);

  return () => {
    window.removeEventListener('pointermove', onWindowMove);
    host.removeEventListener('pointermove', onHostMove);
    host.removeEventListener('pointerdown', onDown);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', onUp);
    host.removeEventListener('pointerleave', onLeave);
    host.removeEventListener('keydown', onKey);
  };
}
