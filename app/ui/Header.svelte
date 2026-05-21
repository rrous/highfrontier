<script lang="ts">
  import {
    dryLevel, waterLevel, ship, routeResult,
    route, flightMode, legendVisible,
  } from './stores';

  $: pct = (() => {
    if (!$routeResult || $route.length === 0) return 100;
    return Math.round($routeResult.propellantLeft / $ship.propellant * 100);
  })();

  $: timeMins = $routeResult?.timeMins ?? 0;
  $: hasRoute = $route.length > 0;
  $: pctColor = pct < 0 ? 'var(--red)' : pct < 15 ? 'var(--yellow)' : 'var(--green)';
  $: timeColor = timeMins < 60 ? 'var(--green)' : timeMins < 120 ? 'var(--yellow)' : 'var(--red)';

  function cycleDry() {
    if ($flightMode) return;
    dryLevel.update(v => v >= 5 ? 1 : v + 1);
  }
  function cycleWater() {
    if ($flightMode) return;
    waterLevel.update(v => v >= 9 ? 1 : v + 1);
  }
  function goClick() {
    if ($flightMode || !hasRoute || pct < 0) return;
    dispatch('startFlight');
  }

  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher<{ startFlight: void }>();
</script>

<header class="header" class:flight-mode={$flightMode}>
  <button class="h-dry" title="Suchá hmotnost 1–5" on:click={cycleDry}>
    Dry&nbsp;{$dryLevel}
  </button>

  <button class="h-total" title="Celková hmotnost (klikni = více vody)" on:click={cycleWater}>
    Σ&nbsp;<span>{$dryLevel + $waterLevel}</span>
  </button>

  <button
    class="h-pct"
    class:has-route={hasRoute && pct >= 0}
    class:negative={pct < 0}
    on:click={goClick}
  >
    <span style="color:{pctColor}">{pct}%</span>
  </button>

  <div class="h-sep"></div>

  <span class="h-time" style="color:{timeColor}">{timeMins} min</span>
  <span class="h-speed">V&nbsp;{$ship.speed}</span>

  <button
    class="h-legend-btn"
    class:active={$legendVisible}
    on:click|stopPropagation={() => legendVisible.update(v => !v)}
  >?</button>
</header>

<style>
  .header {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    height: var(--header-h);
  }
  .header.flight-mode { background: rgba(12, 28, 60, .97); border-bottom-color: #1a3a6a; }

  .h-dry {
    flex-shrink: 0; width: 26px; height: 26px; border-radius: 4px;
    border: 1px solid var(--border); background: var(--bg);
    color: var(--bright); font-family: var(--font-hud); font-size: 14px; font-weight: 900;
    cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: border-color .2s; user-select: none;
  }
  .h-dry:hover { border-color: var(--mid); }

  .h-total {
    flex-shrink: 0; height: 26px; border-radius: 4px; padding: 0 8px;
    border: 1px solid var(--border); background: var(--bg);
    color: var(--mid); font-family: var(--font-hud); font-size: 11px; font-weight: 700;
    cursor: pointer; display: flex; align-items: center; gap: 2px;
    transition: border-color .2s; user-select: none; white-space: nowrap;
  }
  .h-total span { color: var(--bright); font-size: 12px; }
  .h-total:hover { border-color: var(--mid); }

  .h-pct {
    flex: 1; min-width: 0; height: 26px; border-radius: 4px; padding: 0 8px;
    border: 1px solid var(--border); background: var(--bg);
    font-family: var(--font-hud); font-size: 13px; font-weight: 900;
    cursor: default; display: flex; align-items: center; justify-content: center;
    transition: border-color .25s, box-shadow .25s;
  }
  .h-pct.has-route { border-color: var(--green); box-shadow: 0 0 8px rgba(70,200,70,.22); cursor: pointer; }
  .h-pct.has-route:hover { box-shadow: 0 0 16px rgba(70,200,70,.45); }
  .h-pct.negative  { border-color: var(--red);   box-shadow: 0 0 6px rgba(208,48,48,.20); cursor: not-allowed; }

  .h-sep   { width: 1px; height: 18px; background: var(--border); flex-shrink: 0; }
  .h-time  { font-family: var(--font-hud); font-size: 12px; font-weight: 700; white-space: nowrap; flex-shrink: 0; }
  .h-speed { font-size: 9px; color: var(--dim); letter-spacing: .04em; white-space: nowrap; flex-shrink: 0; }

  .h-legend-btn {
    flex-shrink: 0; width: 26px; height: 26px; border-radius: 50%;
    border: 1px solid var(--border); background: transparent; color: var(--dim);
    font-size: 13px; cursor: pointer; display: flex; align-items: center; justify-content: center;
    transition: border-color .2s, color .2s; font-family: var(--font-mono);
  }
  .h-legend-btn.active, .h-legend-btn:hover { border-color: var(--accent); color: var(--bright); }
</style>
