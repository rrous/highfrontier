import { writable, derived } from 'svelte/store';
import type { Scene, RouteEntry } from '../game/model/types';
import { makeShipConfig } from '../game/physics/flight';
import { calcRoute } from '../game/routeplanner/planner';

// Ship configuration
export const dryLevel   = writable(3);   // 1–5
export const waterLevel = writable(1);   // 1–9

export const ship = derived([dryLevel, waterLevel], ([$d, $w]) => makeShipConfig($d, $w));

// Loaded scene
export const scene = writable<Scene | null>(null);

// Route planning
export const route = writable<RouteEntry[]>([]);

// Computed route result
export const routeResult = derived([route, scene, ship], ([$route, $scene, $ship]) => {
  if (!$scene || $route.length === 0) return null;
  return calcRoute($route, $scene.base, $scene.asteroids, $ship);
});

// INFO card state
export const infoAsteroidId   = writable<number | null>(null);
export const infoTier         = writable<'catalog' | 'flyby' | 'stop'>('catalog');

// Flight mode (animation phase)
export const flightMode      = writable(false);
export const flightIdx       = writable(0);
export const flightConfirmed = writable(false);

// Legend overlay
export const legendVisible = writable(false);

// Toast
export const toastMsg  = writable('');
export const toastKind = writable<'go' | 'err'>('go');
let toastTimer = 0;
export function showToast(msg: string, kind: 'go' | 'err' = 'go') {
  toastMsg.set(msg);
  toastKind.set(kind);
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toastMsg.set(''), 1800);
}
