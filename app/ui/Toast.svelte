<script lang="ts">
  import { toastMsg, toastKind } from './stores';
</script>

{#if $toastMsg}
  <div class="toast" class:go={$toastKind === 'go'}>{$toastMsg}</div>
{/if}

<style>
  .toast {
    position: fixed;
    top: 52px;
    left: 50%;
    transform: translateX(-50%);
    color: #fff;
    font-family: var(--font-hud);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: .12em;
    padding: 8px 16px;
    border-radius: 4px;
    pointer-events: none;
    white-space: nowrap;
    z-index: 400;
    background: rgba(208, 48, 48, .94);
    animation: fadein .15s ease;
  }
  .toast.go { background: rgba(70, 200, 70, .94); color: #000; }
  @keyframes fadein { from { opacity: 0 } to { opacity: 1 } }
</style>
