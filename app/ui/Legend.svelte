<script lang="ts">
  import { legendVisible } from './stores';
</script>

{#if $legendVisible}
  <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
  <div class="overlay" on:click|self={() => legendVisible.set(false)}>
    <div class="leg-title">LEGENDA</div>
    <div class="leg-grid">
      <div class="swatch" style="background:var(--S)"></div><div class="leg-text">S — silikit (olivin, pyroxen, PGM)</div>
      <div class="swatch" style="background:var(--C)"></div><div class="leg-text">C — uhlikatý, voda, He-3</div>
      <div class="swatch" style="background:var(--M)"></div><div class="leg-text">M — kov (Fe-Ni, PGM jackpot)</div>
      <div class="swatch" style="background:var(--V)"></div><div class="leg-text">V — bazalt, fragment Vesty</div>
      <div class="swatch" style="background:var(--E)"></div><div class="leg-text">E — enstatit, vysoké albedo</div>
      <div class="swatch" style="background:var(--D)"></div><div class="leg-text">D — tmavý, organický</div>
      <div class="swatch" style="background:var(--P)"></div><div class="leg-text">P — primitivní, tmavý</div>
      <div class="swatch" style="background:var(--K)"></div><div class="leg-text">K — přechodový (S/C), CV/CO chondrit</div>
      <div class="swatch" style="background:var(--U)"></div><div class="leg-text">U — neklasifikovaný</div>
      <div class="leg-div"></div>
      <div class="swatch stop-s"></div><div class="leg-text">zastávka — plný stop</div>
      <div class="swatch flyby-s"></div><div class="leg-text">průlet — závisí na úhlu zahnutí</div>
      <div class="leg-div"></div>
    </div>
    <div class="pie-row">
      <div class="pie-item">
        <svg width="22" height="22" viewBox="-11 -11 22 22">
          <path d="M0,0 L10,0 A10,10,0,0,1,5,-8.66 Z" fill="#46c846" opacity=".75"/>
          <circle r="10" fill="none" stroke="#46c846" stroke-width="1" opacity=".3"/>
        </svg>levný průlet
      </div>
      <div class="pie-item">
        <svg width="22" height="22" viewBox="-11 -11 22 22">
          <path d="M0,0 L10,0 A10,10,0,0,1,-10,0 Z" fill="#d89820" opacity=".75"/>
          <circle r="10" fill="none" stroke="#d89820" stroke-width="1" opacity=".3"/>
        </svg>střední obrat
      </div>
      <div class="pie-item">
        <svg width="22" height="22" viewBox="-11 -11 22 22">
          <path d="M0,0 L10,0 A10,1,0,1,1,0,-10 Z" fill="#d03030" opacity=".75"/>
          <circle r="10" fill="none" stroke="#d03030" stroke-width="1" opacity=".3"/>
        </svg>drahý obrat
      </div>
    </div>
    <div class="leg-note">
      mapa: klik = zastávka → průlet → odebrat<br>
      INFO panel: přepnutí zastávka ↔ průlet<br><br>
      suché 1–5 · voda 1–9 · Tsiolkovsky: lehčí loď = levnější manévry
    </div>
    <button class="close-btn" on:click={() => legendVisible.set(false)}>ZAVŘÍT</button>
  </div>
{/if}

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(6, 9, 16, .92);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    gap: 14px;
    z-index: 300;
    padding: 24px;
    backdrop-filter: blur(4px);
  }
  .leg-title {
    font-family: var(--font-hud);
    font-size: 13px;
    font-weight: 700;
    color: var(--bright);
    letter-spacing: .2em;
  }
  .leg-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 14px;
    align-items: center;
    width: 100%;
    max-width: 320px;
  }
  .swatch { width: 16px; height: 16px; border-radius: 50%; }
  .stop-s  { border: 2px solid var(--green); }
  .flyby-s { border: 2px dashed var(--yellow); }
  .leg-text { font-size: 12px; color: var(--mid); }
  .leg-div { grid-column: 1 / -1; height: 1px; background: var(--border); margin: 2px 0; }
  .pie-row  { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; justify-content: center; }
  .pie-item { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--mid); }
  .leg-note { font-size: 11px; color: var(--dim); text-align: center; line-height: 1.8; max-width: 300px; }
  .close-btn {
    font-family: var(--font-hud);
    font-size: 11px;
    letter-spacing: .15em;
    color: var(--dim);
    border: 1px solid var(--border);
    background: none;
    padding: 9px 22px;
    border-radius: 4px;
    cursor: pointer;
  }
  .close-btn:hover { color: var(--bright); border-color: var(--mid); }
</style>
