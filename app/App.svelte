<script lang="ts">
  import { onMount } from 'svelte';
  import Header from './ui/Header.svelte';
  import Map from './ui/Map.svelte';
  import InfoCard from './ui/InfoCard.svelte';
  import Legend from './ui/Legend.svelte';
  import Toast from './ui/Toast.svelte';
  import './ui/tokens.css';

  import { scene, route, infoAsteroidId, infoTier, flightMode, flightIdx, flightConfirmed, showToast } from './ui/stores';
  import { loadScene } from './data/supabase';

  let loading = true;
  let loadError = '';
  let mapRef: Map;

  onMount(async () => {
    try {
      const s = await loadScene(new URLSearchParams(window.location.search));
      scene.set(s);
    } catch (e) {
      loadError = '⚠ Chyba připojení k DB: ' + (e instanceof Error ? e.message : String(e));
    } finally {
      loading = false;
    }
  });

  // Close info card on click outside
  function onDocClick() {
    if (!$flightMode) infoAsteroidId.set(null);
  }

  // Keyboard Escape
  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !$flightMode) infoAsteroidId.set(null);
  }

  // Flight mode
  function startFlight() {
    flightMode.set(true);
    flightIdx.set(0);
    flightConfirmed.set(false);
    showToast('GO! ▶', 'go');
    setTimeout(showFlightWaypoint, 600);
  }

  function showFlightWaypoint() {
    const r = $route;
    const i = $flightIdx;
    if (i >= r.length) { endFlight(); return; }
    infoAsteroidId.set(r[i].id);
    infoTier.set('flyby');
    flightConfirmed.set(false);
  }

  function flightNext() {
    flightConfirmed.set(false);
    flightIdx.update(v => v + 1);
    infoAsteroidId.set(null);
    setTimeout(showFlightWaypoint, 300);
  }

  function endFlight() {
    flightMode.set(false);
    infoAsteroidId.set(null);
    showToast('Mise dokončena', 'go');
  }
</script>

<svelte:window on:click={onDocClick} on:keydown={onKeyDown} />

{#if loading}
  <div class="loading">
    <div class="loading-title">HIGHFRONTIER</div>
    NAČÍTÁM DATA Z DB…
  </div>
{:else if loadError}
  <div class="loading">{loadError}</div>
{:else}
  <div class="app" on:click|stopPropagation>
    <Header on:startFlight={startFlight} />
    <Map bind:this={mapRef} />
    <InfoCard
      onCardEnter={() => mapRef?.onInfoCardEnter()}
      on:flightNext={flightNext}
    />
  </div>
{/if}

<Legend />
<Toast />

<style>
  .app {
    height: 100dvh;
    max-width: var(--app-max-w);
    margin: 0 auto;
    display: flex;
    flex-direction: column;
  }
  .loading {
    position: fixed;
    inset: 0;
    background: var(--bg);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    font-family: var(--font-hud);
    font-size: 12px;
    color: var(--dim);
    letter-spacing: .15em;
  }
  .loading-title { color: var(--accent); font-size: 18px; font-weight: 700; }
</style>
