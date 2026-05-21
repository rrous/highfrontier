<script lang="ts">
  import { onMount } from 'svelte';
  import { scene, route, routeResult, infoAsteroidId, infoTier, flightMode } from './stores';
  import { SPECTRAL_COLORS } from '../game/model/types';
  import { costColor } from '../game/physics/flight';
  import type { Asteroid } from '../game/model/types';

  let mapEl: HTMLDivElement;
  let svgEl: SVGSVGElement;
  let scrolled = false;
  let W = 0, H = 0;

  const hoverTimers: Map<number, ReturnType<typeof setTimeout>> = new Map();
  let hoverCloseTimer: ReturnType<typeof setTimeout> | null = null;

  function mapDims() {
    W = mapEl?.offsetWidth ?? 0;
    H = mapEl?.offsetHeight ?? 0;
  }

  function toXY(x: number, y: number) {
    return { x: x / 100 * W, y: y / 100 * H };
  }

  $: dvUnits = $routeResult?.segments.map(s => s.dvNorm) ?? [];

  function drawLines() {
    if (!svgEl) return;
    mapDims();
    svgEl.querySelectorAll('.rl').forEach(e => e.remove());
    const r = $route;
    if (!r.length || !$scene) return;

    const ids: (number | 'BASE')[] = ['BASE', ...r.map(e => e.id), 'BASE'];
    const getPoint = (id: number | 'BASE') => {
      if (id === 'BASE') return $scene!.base;
      return $scene!.asteroids.find(a => a.id === id)!;
    };
    const pts = ids.map(id => toXY(getPoint(id).x, getPoint(id).y));

    // Route lines
    for (let i = 0; i < pts.length - 1; i++) {
      const p1 = pts[i], p2 = pts[i + 1], isRet = i === pts.length - 2;
      const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      ln.setAttribute('x1', String(p1.x)); ln.setAttribute('y1', String(p1.y));
      ln.setAttribute('x2', String(p2.x)); ln.setAttribute('y2', String(p2.y));
      ln.setAttribute('stroke', isRet ? 'rgba(26,110,208,.15)' : 'rgba(26,110,208,.5)');
      ln.setAttribute('stroke-width', isRet ? '1' : '1.8');
      ln.setAttribute('class', 'rl');
      svgEl.appendChild(ln);

      if (!isRet) {
        const ax = p1.x + (p2.x - p1.x) * 0.6, ay = p1.y + (p2.y - p1.y) * 0.6;
        const arr = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        arr.setAttribute('points', '0,-5 10,0 0,5');
        arr.setAttribute('fill', r[i]?.mode === 'stop' ? 'rgba(70,200,70,.7)' : 'rgba(90,160,220,.7)');
        arr.setAttribute('transform', `translate(${ax},${ay}) rotate(${Math.atan2(p2.y - p1.y, p2.x - p1.x) * 180 / Math.PI})`);
        arr.setAttribute('class', 'rl');
        svgEl.appendChild(arr);
      }
    }

    // Waypoint decorators
    for (let i = 1; i < pts.length - 1; i++) {
      const e = r[i - 1], dv = dvUnits[i - 1] ?? 0;
      const cx = pts[i].x, cy = pts[i].y, R = 15;

      if (e.mode === 'stop') {
        const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        c.setAttribute('cx', String(cx)); c.setAttribute('cy', String(cy)); c.setAttribute('r', String(R));
        c.setAttribute('fill', 'rgba(70,200,70,.18)'); c.setAttribute('stroke', '#46c846');
        c.setAttribute('stroke-width', '1.2'); c.setAttribute('class', 'rl');
        svgEl.appendChild(c);
      } else {
        if (dv < 0.05) continue;
        const ia = Math.atan2(pts[i].y - pts[i - 1].y, pts[i].x - pts[i - 1].x);
        const oa = Math.atan2(pts[i + 1].y - pts[i].y, pts[i + 1].x - pts[i].x);
        const x1 = cx + R * Math.cos(ia), y1 = cy + R * Math.sin(ia);
        const x2 = cx + R * Math.cos(oa), y2 = cy + R * Math.sin(oa);
        const v1x = pts[i].x - pts[i - 1].x, v1y = pts[i].y - pts[i - 1].y;
        const v2x = pts[i + 1].x - pts[i].x, v2y = pts[i + 1].y - pts[i].y;
        const cross = v1x * v2y - v1y * v2x;
        const def = Math.acos(Math.max(-1, Math.min(1, (v1x * v2x + v1y * v2y) / (Math.hypot(v1x, v1y) * Math.hypot(v2x, v2y)))));
        const col = costColor(dv);
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', `M ${cx} ${cy} L ${x1} ${y1} A ${R} ${R} 0 ${def > Math.PI ? 1 : 0} ${cross >= 0 ? 1 : 0} ${x2} ${y2} Z`);
        path.setAttribute('fill', col); path.setAttribute('opacity', '0.58'); path.setAttribute('class', 'rl');
        svgEl.appendChild(path);
        const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        ring.setAttribute('cx', String(cx)); ring.setAttribute('cy', String(cy)); ring.setAttribute('r', String(R));
        ring.setAttribute('fill', 'none'); ring.setAttribute('stroke', col); ring.setAttribute('stroke-width', '1');
        ring.setAttribute('opacity', '0.25'); ring.setAttribute('class', 'rl');
        svgEl.appendChild(ring);
      }
    }
  }

  function initStars() {
    if (!svgEl) return;
    mapDims();
    for (let i = 0; i < 220; i++) {
      const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      c.setAttribute('cx', String(Math.random() * W));
      c.setAttribute('cy', String(Math.random() * H));
      c.setAttribute('r', String(Math.random() * 1.5 + 0.15));
      c.setAttribute('fill', `rgba(170,200,230,${(Math.random() * 0.45 + 0.06).toFixed(2)})`);
      svgEl.appendChild(c);
    }
  }

  function toggleRoute(asteroid: Asteroid) {
    if ($flightMode) return;
    route.update(r => {
      const idx = r.findIndex(e => e.id === asteroid.id);
      if (idx === -1) return [...r, { id: asteroid.id, mode: 'stop' }];
      const next = [...r];
      next.splice(idx, 1);
      return next;
    });
  }

  function onAsteroidHover(a: Asteroid) {
    if ($flightMode) return;
    if (hoverCloseTimer) { clearTimeout(hoverCloseTimer); hoverCloseTimer = null; }
    const t = setTimeout(() => {
      infoAsteroidId.set(a.id);
      infoTier.set('catalog');
    }, 2000);
    hoverTimers.set(a.id, t);
  }

  function onAsteroidLeave(a: Asteroid) {
    const t = hoverTimers.get(a.id);
    if (t) { clearTimeout(t); hoverTimers.delete(a.id); }
    hoverCloseTimer = setTimeout(() => {
      if (!$flightMode) infoAsteroidId.set(null);
    }, 700);
  }

  function onInfoCardEnter() {
    if (hoverCloseTimer) { clearTimeout(hoverCloseTimer); hoverCloseTimer = null; }
  }

  export { onInfoCardEnter };

  $: if ($route || $routeResult) drawLines();

  onMount(() => {
    initStars();
    window.addEventListener('resize', drawLines);
    return () => window.removeEventListener('resize', drawLines);
  });
</script>

<div class="map-container" on:scroll={() => (scrolled = true)} bind:this={mapEl}>
  <div class="map-inner">
    <svg class="route-svg" bind:this={svgEl}></svg>

    {#if $scene}
      <!-- BASE marker -->
      <div class="base-el" style="left:{$scene.base.x}%;top:{$scene.base.y}%">
        <svg width="34" height="34" viewBox="0 0 34 34">
          <polygon points="17,3 31,30 3,30" fill="none" stroke="#1a6ed0" stroke-width="1.5"/>
          <polygon points="17,11 26,28 8,28" fill="#1a6ed0" opacity="0.18"/>
          <text x="17" y="23" text-anchor="middle" font-size="6" fill="#5aadff"
            font-family="Orbitron,monospace" font-weight="700" letter-spacing="0.25">BASE</text>
        </svg>
      </div>

      <!-- Asteroids -->
      {#each $scene.asteroids as a (a.id)}
        {@const ri = $route.findIndex(e => e.id === a.id)}
        {@const seg = ri !== -1 ? $routeResult?.segments[ri] : null}
        <button
          class="asteroid-btn"
          class:is-stop={ri !== -1 && $route[ri].mode === 'stop'}
          class:is-flyby={ri !== -1 && $route[ri].mode === 'flyby'}
          style="left:{a.x}%;top:{a.y}%"
          on:click|stopPropagation={() => toggleRoute(a)}
          on:mouseenter={() => onAsteroidHover(a)}
          on:mouseleave={() => onAsteroidLeave(a)}
        >
          <div class="a-ring" style="width:{a.r * 2}px;height:{a.r * 2}px;background:{SPECTRAL_COLORS[a.type] ?? '#888'}">
            <span class="a-type">{a.type}</span>
            {#if ri !== -1}
              <div
                class="a-badge"
                title={seg ? `${$route[ri].mode === 'stop' ? 'zastávka' : 'průlet'}  Δv=${seg.dvMs} m/s  H₂O=−${seg.fuelKg} kg` : ''}
              >{ri + 1}</div>
            {/if}
          </div>
          <div class="a-label">{a.name}</div>
        </button>
      {/each}
    {/if}

    {#if !scrolled}
      <div class="scroll-hint">›</div>
    {/if}
  </div>
</div>

<style>
  .map-container {
    flex: 1;
    overflow-x: auto;
    overflow-y: hidden;
    position: relative;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }
  .map-container::-webkit-scrollbar { height: 3px; }
  .map-container::-webkit-scrollbar-thumb { background: var(--border); }

  .map-inner {
    position: relative;
    height: 100%;
    width: 1400px;
    background: radial-gradient(ellipse at 30% 38%, #0a1828 0%, var(--bg) 68%);
    flex-shrink: 0;
  }

  .route-svg { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }

  .base-el { position: absolute; transform: translate(-50%,-50%); pointer-events: none; }

  .asteroid-btn {
    position: absolute;
    transform: translate(-50%,-50%);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    user-select: none;
    background: none;
    border: none;
    padding: 0;
  }
  .a-ring {
    border-radius: 50%;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform .15s, box-shadow .2s;
    border: 2px solid transparent;
  }
  .asteroid-btn:hover .a-ring { transform: scale(.92); }
  .asteroid-btn:active .a-ring { transform: scale(.82); }
  .a-type { font-size: 11px; font-weight: 700; color: rgba(0,0,0,.5); font-family: var(--font-hud); line-height: 1; pointer-events: none; }
  .a-label { font-size: 11px; color: var(--dim); white-space: nowrap; transition: color .2s; }

  .asteroid-btn.is-stop  .a-ring  { border-color: var(--green);  box-shadow: 0 0 12px rgba(70,200,70,.55); }
  .asteroid-btn.is-stop  .a-label { color: var(--green); }
  .asteroid-btn.is-flyby .a-ring  { border-color: var(--yellow); box-shadow: 0 0 10px rgba(216,152,32,.45); border-style: dashed; }
  .asteroid-btn.is-flyby .a-label { color: var(--yellow); }

  .a-badge {
    position: absolute;
    top: -6px; right: -6px;
    width: 16px; height: 16px;
    border-radius: 50%;
    font-family: var(--font-hud);
    font-size: 9px; font-weight: 900;
    display: flex; align-items: center; justify-content: center;
    color: #000; z-index: 2;
  }
  .is-stop  .a-badge { background: var(--green); }
  .is-flyby .a-badge { background: var(--yellow); }

  .scroll-hint {
    position: absolute;
    right: 8px; top: 50%;
    transform: translateY(-50%);
    color: var(--dim);
    font-size: 20px;
    pointer-events: none;
    opacity: .5;
    animation: pulse-r 2s ease-in-out infinite;
  }
  @keyframes pulse-r {
    0%,100% { opacity:.25; transform:translateY(-50%) translateX(0); }
    50%      { opacity:.6;  transform:translateY(-50%) translateX(4px); }
  }
</style>
