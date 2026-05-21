// Hybrid flight model — app/DESIGN.md §5.
// All values in SI units. Constants marked §OQ-2 are physically motivated defaults
// to be calibrated during game balancing.

/** Bipropellant exhaust velocity (hydrazine/NTO typical). §OQ-2 */
export const VE_DEFAULT = 3000;       // m/s

/** Fixed Δv budget per full rendezvous (braking + departure). §OQ-2 */
export const DV_STOP_DEFAULT = 150;   // m/s

/** Δv budget for the return leg to BASE. §OQ-2 */
export const DV_RETURN_DEFAULT = 100; // m/s

/** Effective transit rate for flight-time estimation. §OQ-2 */
export const SPEED_DEFAULT = 3;       // (m/s) / min → time in minutes

export interface ShipConfig {
  dryMass: number;    // kg
  propellant: number; // kg (current load)
  ve: number;         // m/s exhaust velocity
  dvStop: number;     // m/s per rendezvous
  dvReturn: number;   // m/s return budget
  speed: number;      // (m/s velocity-space) per minute of flight time
}

export function makeShipConfig(dryLevel: number, waterLevel: number): ShipConfig {
  return {
    dryMass: dryLevel * 100,
    propellant: waterLevel * 100,
    ve: VE_DEFAULT,
    dvStop: DV_STOP_DEFAULT,
    dvReturn: DV_RETURN_DEFAULT,
    speed: SPEED_DEFAULT,
  };
}

/** Tsiolkovsky rocket equation — propellant consumed for a maneuver. */
export function fuelUsed(dv: number, currentPropellant: number, ship: ShipConfig): number {
  return (ship.dryMass + currentPropellant) * (1 - Math.exp(-dv / ship.ve));
}

/**
 * Scale-invariant flyby Δv (dimensionless 0–2, where 2 = full U-turn).
 * Property: identical result whether using map-% or m/s velocity-space coords,
 * because only direction vectors are used. — §design_gamer_UX §2.6
 */
export function dvFlyby(
  px: number, py: number,
  cx: number, cy: number,
  nx: number, ny: number,
): number {
  const l1 = Math.hypot(cx - px, cy - py);
  const l2 = Math.hypot(nx - cx, ny - cy);
  if (l1 < 1e-12 || l2 < 1e-12) return 0;
  const v1x = (cx - px) / l1, v1y = (cy - py) / l1;
  const v2x = (nx - cx) / l2, v2y = (ny - cy) / l2;
  return Math.hypot(v2x - v1x, v2y - v1y);
}

/** 3D velocity-space distance = actual Δv between two bodies (m/s). */
export function deltaV(
  ax: number, ay: number, az: number,
  bx: number, by: number, bz: number,
): number {
  return Math.hypot(bx - ax, by - ay, bz - az);
}

/** Visual cost color for pie-slice SVG; uses dimensionless dvNorm (0–2). */
export function costColor(dvNorm: number): string {
  if (dvNorm < 0.5) return '#46c846';
  if (dvNorm < 1.5) return '#d89820';
  return '#d03030';
}
