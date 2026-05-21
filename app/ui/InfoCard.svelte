<script lang="ts">
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import { scene, route, infoAsteroidId, infoTier, flightMode, flightConfirmed } from './stores';
  const dispatch = createEventDispatcher<{ flightNext: void }>();
  import { drawSurface } from './surface';
  import { SPECTRAL_COLORS } from '../game/model/types';
  import type { SpectralType } from '../game/model/types';
  import { deltaV } from '../game/physics/flight';

  export let onCardEnter: () => void = () => {};

  let canvasEl: HTMLCanvasElement;

  $: asteroid = $scene?.asteroids.find(a => a.id === $infoAsteroidId) ?? null;
  $: cat = asteroid && $scene ? $scene.catalog[asteroid.id] : null;
  $: fly = asteroid && $scene ? $scene.flyby[asteroid.id] : null;
  $: stp = asteroid && $scene ? $scene.stop[asteroid.id] : null;
  $: visible = asteroid !== null;
  $: isFly = $infoTier === 'flyby';
  $: isStop = $infoTier === 'stop';
  $: data = (isFly || isStop) ? fly : cat;

  $: dV = asteroid && $scene
    ? Math.round(deltaV(asteroid.vx, asteroid.vy, asteroid.vz, $scene.base.vx, $scene.base.vy, $scene.base.vz))
    : 0;

  $: ri = $route.findIndex(e => e.id === $infoAsteroidId);
  $: mode = ri >= 0 ? $route[ri].mode : null;

  $: if (visible && canvasEl && asteroid) {
    requestAnimationFrame(() => drawSurface(canvasEl, asteroid!.type as SpectralType, asteroid!.id * 1301));
  }

  function close() {
    infoAsteroidId.set(null);
  }

  function setMode(m: 'stop' | 'flyby') {
    if ($infoAsteroidId === null) return;
    if ($flightMode) {
      flightConfirmed.set(true);
      route.update(r => {
        const idx = r.findIndex(e => e.id === $infoAsteroidId);
        if (idx >= 0) { const next = [...r]; next[idx] = { ...next[idx], mode: m }; return next; }
        return r;
      });
      infoTier.set(m === 'stop' ? 'stop' : 'flyby');
      return;
    }
    route.update(r => {
      const idx = r.findIndex(e => e.id === $infoAsteroidId);
      if (idx === -1) return [...r, { id: $infoAsteroidId!, mode: m }];
      const next = [...r]; next[idx] = { ...next[idx], mode: m }; return next;
    });
  }

  function h2oDots(n: number) {
    return Array.from({ length: 4 }, (_, i) =>
      i < n ? '<span class="h2o-on">●</span>' : '<span class="h2o-off">○</span>'
    ).join('');
  }

  function ecoHtml(eco: string[]) {
    if (!eco.length) return '<span class="unk">—</span>';
    const cls: Record<string, string> = { Pt: 'eco-pt', Fe: 'eco-fe', 'H₂O': 'eco-h2o', PGM: 'eco-pgm' };
    return '<div class="eco-row">' + eco.map(e => `<span class="eco ${cls[e] ?? 'eco-pt'}">${e}</span>`).join('') + '</div>';
  }

  function valHtml(flyVal: string | number | null, catVal: string | number | null, anomaly?: string) {
    const flag = anomaly ? `<span class="flag anomaly">${anomaly}</span>` : '';
    const orig = catVal == null ? `<span class="orig">nové</span>` : `<span class="orig">(${catVal})</span>`;
    return `<span class="ir-val">${flyVal}</span>${orig}${flag}`;
  }

  $: rows = (() => {
    if (!asteroid || !cat) return '';
    const d = data;
    let html = '';

    // albedo
    if (isFly || isStop) {
      html += `<div class="ir"><span class="ir-lbl">alb</span>${valHtml(fly!.albedo.toFixed(3), cat.albedo?.toFixed(3) ?? null, fly!.anomaly?.albedo)}</div>`;
    } else {
      const albX = cat.albedo != null && (cat.albedo > 0.40 || cat.albedo < 0.09);
      html += `<div class="ir"><span class="ir-lbl">alb</span>
        <span class="ir-val${cat.albedo == null ? ' unk' : ''}">${cat.albedo != null ? cat.albedo.toFixed(3) : '?'}</span>
        ${cat.interloper ? '<span class="flag intlp">⚡ INTERLOPER</span>' : albX ? '<span class="flag anomaly">⚡</span>' : ''}</div>`;
    }

    // diameter
    if (isFly || isStop) {
      html += `<div class="ir"><span class="ir-lbl">Ø</span>${valHtml(fly!.diam + ' km', cat.diam ? cat.diam + ' km' : null, fly!.anomaly?.diam)}</div>`;
    } else {
      html += `<div class="ir"><span class="ir-lbl">Ø</span><span class="ir-val${!cat.diam ? ' unk' : ''}">${cat.diam ? cat.diam + ' km' : '?'}</span></div>`;
    }

    // mass + density
    if (isFly || isStop) {
      html += `<div class="ir"><span class="ir-lbl">m</span>${valHtml('~' + fly!.massStr + ' kg', cat.massStr ? '~' + cat.massStr + ' kg' : null, undefined)}</div>`;
      html += `<div class="ir"><span class="ir-lbl">ρ</span>${valHtml(fly!.densStr, null, fly!.anomaly?.dens)}</div>`;
    } else {
      html += `<div class="ir"><span class="ir-lbl">m</span><span class="ir-val${!cat.massStr ? ' unk' : ''}">${cat.massStr ? '~' + cat.massStr + ' kg' : '?'}</span></div>`;
    }

    // delta-v from BASE (real m/s — §5.4)
    html += `<div class="ir"><span class="ir-lbl">Δv</span><span class="ir-val">${dV} m/s</span></div>`;
    html += '<div class="info-div"></div>';

    // rotation
    if (isFly || isStop) {
      html += `<div class="ir"><span class="ir-lbl">↻</span>${valHtml(fly!.period + ' h', cat.period ? cat.period + ' h' : null, fly!.anomaly?.period)}</div>`;
    } else {
      html += `<div class="ir"><span class="ir-lbl">↻</span>
        <span class="ir-val${!cat.period ? ' unk' : ''}">${cat.period ? cat.period + ' h' : '?'}</span>
        ${cat.fastRot ? '<span class="flag anomaly">⚡ YORP?</span>' : ''}</div>`;
    }

    // binary
    const bVal = d?.binary ?? false;
    html += `<div class="ir"><span class="ir-lbl">⊕⊕</span>
      <span class="ir-val${!bVal ? ' unk' : ''}">${bVal ? 'ANO' : '—'}</span>
      ${bVal ? `<span class="flag pos">${(isFly || isStop) && fly!.anomaly?.binary ? fly!.anomaly.binary : '⚡'}</span>` : ''}</div>`;

    // structure
    html += `<div class="ir"><span class="ir-lbl">◈</span><span class="ir-val${d?.structure === '?' ? ' unk' : ''}">${d?.structure ?? '?'}</span></div>`;

    // magnetic (flyby only)
    if ((isFly || isStop) && fly!.mag) {
      html += `<div class="ir"><span class="ir-lbl">⊗</span><span class="ir-val">ANO</span><span class="flag anomaly">${fly!.anomaly?.mag ?? '⚡'}</span></div>`;
    }

    html += '<div class="info-div"></div>';

    // H2O
    const h2oVal = (isFly || isStop) ? fly!.h2o : cat.h2o;
    const h2oFlag = (isFly || isStop) && fly!.anomaly?.h2o ? `<span class="flag anomaly">${fly!.anomaly.h2o}</span>` : '';
    html += `<div class="ir"><span class="ir-lbl">H₂O</span><span class="h2o-dots">${h2oDots(h2oVal)}</span>${h2oFlag}</div>`;

    // eco resources
    const ecoVal = (isFly || isStop) ? fly!.eco : cat.eco;
    const ecoFlag = (isFly || isStop) && fly!.anomaly?.eco ? `<span class="flag anomaly">${fly!.anomaly.eco}</span>` : '';
    html += `<div class="ir"><span class="ir-lbl">⬡</span>${ecoHtml(ecoVal)}${ecoFlag}</div>`;

    // Tier 3 minerals
    if (isStop && stp) {
      html += '<div class="info-div"></div>';
      html += `<div class="ir" style="flex-wrap:wrap"><span class="ir-lbl">min</span><span class="minerals">${stp.minerals}</span></div>`;
      if (stp.special) {
        html += `<div class="ir" style="margin-top:4px"><span class="ir-lbl"></span><span class="special">${stp.special}</span></div>`;
      }
    }

    return html;
  })();

  $: tierLabel = isFly
    ? ' <span class="tier-label">TIER 2 · PRŮLET</span>'
    : isStop
    ? ' <span class="tier-label yellow">TIER 3 · ZASTÁVKA</span>'
    : '';

  $: stopLocked = $flightMode && $flightConfirmed && mode === 'flyby';
  $: flybyLocked = $flightMode && $flightConfirmed && mode === 'stop';
</script>

<div
  class="info-card"
  class:visible
  on:mouseenter={onCardEnter}
  on:mouseleave={() => { if (!$flightMode) infoAsteroidId.set(null); }}
>
  {#if asteroid && cat}
    <div class="info-hdr">
      <div class="info-badge" style="background:{SPECTRAL_COLORS[asteroid.type as SpectralType] ?? '#888'};
        color:{['E','M'].includes(asteroid.type) ? 'rgba(0,0,0,.7)' : 'rgba(0,0,0,.55)'}">
        {asteroid.type}
      </div>
      <div class="info-name">{@html asteroid.name + tierLabel}</div>
      {#if !$flightMode}
        <button class="info-close" on:click|stopPropagation={close}>×</button>
      {/if}
    </div>

    <div class="info-surface">
      <canvas bind:this={canvasEl}></canvas>
    </div>

    <div class="info-data">{@html rows}</div>

    <div class="info-actions">
      <button
        class="info-btn btn-stop"
        class:active={mode === 'stop'}
        class:locked={stopLocked}
        on:click|stopPropagation={() => setMode('stop')}
        disabled={stopLocked}
      >ZASTÁVKA</button>

      <button
        class="info-btn btn-flyby"
        class:active={mode === 'flyby'}
        class:locked={flybyLocked}
        on:click|stopPropagation={() => setMode('flyby')}
        disabled={flybyLocked}
      >⤳ PRŮLET</button>

      {#if $flightMode}
        <button class="info-btn btn-next" on:click|stopPropagation={() => dispatch('flightNext')}>DÁLE ›</button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .info-card {
    position: fixed;
    top: var(--header-h);
    bottom: 0;
    left: 50%;
    transform: translateX(-50%) translateY(110%);
    width: 100%;
    max-width: var(--app-max-w);
    z-index: 200;
    background: rgba(7, 11, 20, .99);
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
    transition: transform .22s cubic-bezier(.4,0,.2,1);
  }
  .info-card.visible { transform: translateX(-50%) translateY(0); }

  .info-hdr {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px 10px;
    border-bottom: 1px solid var(--border);
  }
  .info-badge {
    width: 32px; height: 32px;
    border-radius: 50%;
    flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--font-hud); font-size: 12px; font-weight: 900;
  }
  .info-name {
    flex: 1;
    font-family: var(--font-hud); font-size: 14px; font-weight: 700;
    color: var(--bright); letter-spacing: .06em;
    min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .info-close {
    flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
    border: 1px solid var(--border); background: transparent;
    color: var(--dim); font-size: 16px; line-height: 1; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: border-color .2s, color .2s;
  }
  .info-close:hover { border-color: var(--red); color: var(--red); }

  .info-surface {
    flex-shrink: 0; height: 185px; overflow: hidden;
    border-bottom: 1px solid var(--border);
  }
  .info-surface canvas { display: block; width: 100%; height: 100%; }

  .info-data {
    flex: 1; overflow-y: auto; padding: 10px 14px;
    display: flex; flex-direction: column; gap: 7px;
    scrollbar-width: thin; scrollbar-color: var(--border) transparent;
  }
  .info-data::-webkit-scrollbar { width: 3px; }
  .info-data::-webkit-scrollbar-thumb { background: var(--border); }

  .info-actions {
    flex-shrink: 0;
    display: flex; flex-wrap: wrap; gap: 8px;
    padding: 8px 14px 12px;
    border-top: 1px solid var(--border);
  }
  .info-btn {
    flex: 1; padding: 8px 4px; border-radius: 4px;
    font-family: var(--font-hud); font-size: 10px; font-weight: 700;
    letter-spacing: .1em; cursor: pointer; border: 1px solid; text-align: center;
    transition: background .15s, box-shadow .15s, opacity .15s;
  }
  .btn-stop  { color: var(--green);  border-color: rgba(70,200,70,.25);  background: transparent; }
  .btn-stop.active  { background: rgba(70,200,70,.20);  border-color: var(--green);  box-shadow: 0 0 8px rgba(70,200,70,.3); }
  .btn-stop:hover   { background: rgba(70,200,70,.10); border-color: rgba(70,200,70,.5); }
  .btn-flyby { color: var(--yellow); border-color: rgba(216,152,32,.25); background: transparent; }
  .btn-flyby.active { background: rgba(216,152,32,.20); border-color: var(--yellow); box-shadow: 0 0 8px rgba(216,152,32,.3); }
  .btn-flyby:hover  { background: rgba(216,152,32,.10); border-color: rgba(216,152,32,.5); }
  .btn-next  { color: var(--accent); border-color: rgba(26,110,208,.4); background: rgba(26,110,208,.08); }
  .btn-next:hover { background: rgba(26,110,208,.2); border-color: var(--accent); }
  .info-btn.locked { opacity: .3; cursor: not-allowed; pointer-events: none; }
  .info-btn:disabled { opacity: .25; cursor: default; }

  /* Data rows (rendered via @html) */
  :global(.ir) { display: flex; align-items: center; gap: 12px; min-height: 22px; }
  :global(.ir-lbl) { width: 32px; flex-shrink: 0; font-size: 11px; color: var(--dim); text-align: right; letter-spacing: .04em; }
  :global(.ir-val) { font-family: var(--font-hud); font-size: 15px; font-weight: 700; color: var(--bright); }
  :global(.ir-val.unk) { color: var(--dim); font-family: var(--font-mono); font-weight: 400; font-size: 14px; }
  :global(.flag) { font-size: 11px; margin-left: 5px; letter-spacing: .04em; }
  :global(.flag.anomaly) { color: #ffd040; }
  :global(.flag.intlp)   { color: #ff6840; }
  :global(.flag.pos)     { color: var(--green); }
  :global(.orig) { font-size: 10px; color: var(--dim); margin-left: 4px; font-family: var(--font-mono); }
  :global(.info-div) { height: 1px; background: var(--border); margin: 2px 0; flex-shrink: 0; }
  :global(.h2o-dots) { font-size: 15px; letter-spacing: 2px; line-height: 1; }
  :global(.h2o-on)  { color: #4abaff; }
  :global(.h2o-off) { color: var(--dim); opacity: .4; }
  :global(.eco-row) { display: flex; gap: 5px; flex-wrap: wrap; }
  :global(.eco) { font-family: var(--font-hud); font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 2px; letter-spacing: .04em; }
  :global(.eco-pt)  { color: #c8b878; background: rgba(200,184,120,.12); border: 1px solid rgba(200,184,120,.22); }
  :global(.eco-fe)  { color: #9c9a98; background: rgba(156,154,152,.12); border: 1px solid rgba(156,154,152,.22); }
  :global(.eco-h2o) { color: #4abaff; background: rgba(74,186,255,.10);  border: 1px solid rgba(74,186,255,.22); }
  :global(.eco-pgm) { color: #d4b860; background: rgba(212,184,96,.15);  border: 1px solid rgba(212,184,96,.30); }
  :global(.minerals) { font-size: 11px; color: var(--mid); line-height: 1.5; }
  :global(.special)  { font-size: 12px; font-family: var(--font-hud); font-weight: 700; color: #ffd040; letter-spacing: .04em; }
  :global(.tier-label) { font-size: 9px; color: var(--accent); letter-spacing: .1em; }
  :global(.tier-label.yellow) { color: var(--yellow); }
</style>
