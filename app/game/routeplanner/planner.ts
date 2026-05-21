import type { Asteroid, Base, RouteEntry, RouteMode } from '../model/types';
import { dvFlyby, fuelUsed, deltaV } from '../physics/flight';
import type { ShipConfig } from '../physics/flight';

export interface Segment {
  dvNorm: number;   // dimensionless (0–2) for SVG pie visualization
  dvMs: number;     // m/s for Tsiolkovsky (rounded)
  fuelKg: number;   // kg consumed (rounded)
  mode: RouteMode;
}

export interface RouteResult {
  segments: Segment[];
  propellantLeft: number; // kg (may be negative = route infeasible)
  totalDvMs: number;      // sum of 3D inter-body velocity distances (m/s)
  timeMins: number;
}

type Point = { x: number; y: number; vx: number; vy: number; vz: number };

function getPoint(id: number | 'BASE', base: Base, asteroids: Asteroid[]): Point {
  if (id === 'BASE') return base;
  return asteroids.find(a => a.id === id)!;
}

export function calcRoute(
  route: RouteEntry[],
  base: Base,
  asteroids: Asteroid[],
  ship: ShipConfig,
): RouteResult {
  if (route.length === 0) {
    return { segments: [], propellantLeft: ship.propellant, totalDvMs: 0, timeMins: 0 };
  }

  const ids: (number | 'BASE')[] = ['BASE', ...route.map(r => r.id), 'BASE'];
  const pts = ids.map(id => getPoint(id, base, asteroids));

  let propellant = ship.propellant;
  const segments: Segment[] = [];
  let totalDvMs = 0;

  for (let i = 1; i < ids.length - 1; i++) {
    const prev = pts[i - 1], cur = pts[i], next = pts[i + 1];
    const entry = route[i - 1];

    const approachMs = deltaV(prev.vx, prev.vy, prev.vz, cur.vx, cur.vy, cur.vz);
    totalDvMs += approachMs;

    let dvMs: number;
    let dvNorm: number;

    if (entry.mode === 'stop') {
      dvMs = ship.dvStop;
      dvNorm = dvMs / ship.ve; // normalized for costColor (always small → green, intentional)
    } else {
      // dvFlyby is scale-invariant — map-% coords give same result as m/s coords
      dvNorm = dvFlyby(prev.x, prev.y, cur.x, cur.y, next.x, next.y);
      dvMs = dvNorm * approachMs;
    }

    const fuel = fuelUsed(dvMs, propellant, ship);
    segments.push({
      dvNorm,
      dvMs: Math.round(dvMs),
      fuelKg: Math.round(fuel * 10) / 10,
      mode: entry.mode,
    });
    propellant -= fuel;
  }

  // Return leg: last waypoint back to BASE
  const lastPt = pts[pts.length - 2];
  totalDvMs += deltaV(lastPt.vx, lastPt.vy, lastPt.vz, base.vx, base.vy, base.vz);
  propellant -= fuelUsed(ship.dvReturn, Math.max(0, propellant), ship);

  return {
    segments,
    propellantLeft: propellant,
    totalDvMs,
    timeMins: Math.round(totalDvMs / ship.speed),
  };
}
