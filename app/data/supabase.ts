import type { Scene, Asteroid, AsteroidCatalog, AsteroidFlyby, AsteroidStop, SpectralType } from '../game/model/types';

const SB_URL = 'https://tfyuyylcygamglpdfudd.supabase.co';
const SB_KEY = 'sb_publishable_DH6ePHNli_LbFfwFuci0Cg_EE408poO';
const HDR: HeadersInit = { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` };

async function get(path: string): Promise<unknown[]> {
  const r = await fetch(`${SB_URL}${path}`, { headers: HDR });
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json() as Promise<unknown[]>;
}

async function rpc(fn: string, body: Record<string, unknown>): Promise<unknown> {
  const r = await fetch(`${SB_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: { ...HDR, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`RPC ${fn} → ${r.status}`);
  return r.json();
}

/** One element of `scene_snapshots.asteroid_data` — pipeline/migration_scene_snapshots.sql. */
interface SnapshotItem {
  id: number;
  name: string;
  spectral_type: string;
  x_km: number; y_km: number; z_km: number;       // heliocentric position, ecliptic J2000
  vx_kms: number; vy_kms: number; vz_kms: number; // heliocentric velocity
  dx_km: number; dy_km: number; dz_km: number;    // offset from base
  d_km: number;                                   // |r_target − r_base|
  dvx_kms: number; dvy_kms: number; dvz_kms: number;
}

/** Tier-1 catalog columns from `asteroids` — snapshot items carry kinematics only. */
interface Tier1Row {
  id: number;
  r_size: number | null;
  albedo: number | null;
  diameter_km: number | null;
  mass_str: string | null;
  period_h: number | null;
  has_satellite: boolean;
  structure: string;
  h2o_level: number;
  eco: string[] | null;
  is_interloper: boolean;
  fast_rotation: boolean;
}

/**
 * URL query params: ?base=&radius=&n=  (all optional)
 * Defaults: base 'Flora', radius 50 mil. km, n 25 nearest bodies.
 *
 * Scene source is the snapshot-backed `nearby_asteroids(base_id, date,
 * radius_km, max_n)` RPC over `scene_snapshots` (db_design.md §9.1) —
 * physical heliocentric distances from Kepler-propagated osculating elements,
 * replacing the legacy proper-element velocity-space `base_surroundings`.
 */
export async function loadScene(params: URLSearchParams): Promise<Scene> {
  const baseName = params.get('base') ?? 'Flora';
  const radiusParam = parseFloat(params.get('radius') ?? '');
  const wantN = parseInt(params.get('n') ?? '', 10) || 25;
  const radiusKm = Number.isFinite(radiusParam) ? radiusParam : 50_000_000;

  // Resolve the base → base_id for the snapshot RPC.
  const baseRows = await get(
    `/rest/v1/bases?select=id,asteroid_id&name=eq.${encodeURIComponent(baseName)}`,
  ) as Array<{ id: number; asteroid_id: number }>;
  const baseRow = baseRows[0];
  if (!baseRow) throw new Error(`Base ${baseName} not found in DB`);

  // Latest available snapshot — the daily job (snapshot-daily.yml) may not
  // have produced today's row yet, so don't hardcode CURRENT_DATE.
  const snaps = await get(
    `/rest/v1/scene_snapshots?select=snapshot_date&base_id=eq.${baseRow.id}&order=snapshot_date.desc&limit=1`,
  ) as Array<{ snapshot_date: string }>;
  const snapDate = snaps[0]?.snapshot_date;
  if (!snapDate) {
    throw new Error(`No scene snapshot for base ${baseName} — run pipeline/snapshot_daily.py`);
  }

  // Surroundings v2 — the base's own asteroid is included at d_km = 0,
  // hence max_n = wantN + 1. Result is sorted ascending by d_km.
  const items = await rpc('nearby_asteroids', {
    p_base_id: baseRow.id,
    p_date: snapDate,
    p_radius_km: radiusKm,
    p_max_n: Math.min(wantN + 1, 100),
  }) as SnapshotItem[];

  const baseItem = items.find(it => it.id === baseRow.asteroid_id);
  if (!baseItem) {
    throw new Error(`Base asteroid ${baseRow.asteroid_id} missing in snapshot ${snapDate}`);
  }
  const neighbours = items.filter(it => it.id !== baseRow.asteroid_id).slice(0, wantN);
  const rawAsteroids = [...neighbours, baseItem];

  // Projection radius: furthest neighbour + 15% margin
  let projR = 0;
  neighbours.forEach(a => {
    const d = Math.hypot(a.dx_km, a.dy_km);
    if (d > projR) projR = d;
  });
  projR = projR * 1.15 || 1000;

  const idList = `(${rawAsteroids.map(a => a.id).join(',')})`;
  const [tier1Raw, tier2Raw, tier3Raw] = await Promise.all([
    get(`/rest/v1/asteroids?select=id,r_size,albedo,diameter_km,mass_str,period_h,has_satellite,structure,h2o_level,eco,is_interloper,fast_rotation&id=in.${idList}`),
    get(`/rest/v1/asteroid_tier2?select=*&asteroid_id=in.${idList}`),
    get(`/rest/v1/asteroid_tier3?select=*&asteroid_id=in.${idList}`),
  ]) as [Tier1Row[], Array<Record<string, unknown>>, Array<Record<string, unknown>>];

  const t1 = Object.fromEntries(tier1Raw.map(t => [t.id, t]));
  const t2 = Object.fromEntries(tier2Raw.map(t => [(t['asteroid_id'] as number), t]));
  const t3 = Object.fromEntries(tier3Raw.map(t => [(t['asteroid_id'] as number), t]));

  const asteroids: Asteroid[] = rawAsteroids.map(a => {
    const isBase = a.id === baseRow.asteroid_id;
    return {
      id: a.id,
      name: a.name,
      type: (a.spectral_type as SpectralType) || 'U',
      x: isBase ? 55 : 50 + 50 * a.dx_km / projR,
      y: isBase ? 58 : 50 + 50 * a.dy_km / projR,
      r: t1[a.id]?.r_size ?? 10,
      vx: a.vx_kms * 1000,
      vy: a.vy_kms * 1000,
      vz: a.vz_kms * 1000,
      dKm: a.d_km,
    };
  });

  const catalog: Record<number, AsteroidCatalog> = {};
  const flyby: Record<number, AsteroidFlyby> = {};
  const stop: Record<number, AsteroidStop> = {};

  for (const a of rawAsteroids) {
    const c = t1[a.id];
    catalog[a.id] = {
      albedo: c?.albedo ?? null,
      diam: c?.diameter_km ?? null,
      massStr: c?.mass_str ?? null,
      period: c?.period_h ?? null,
      binary: c?.has_satellite ?? false,
      structure: c?.structure ?? '',
      h2o: c?.h2o_level ?? 0,
      eco: c?.eco ?? [],
      interloper: c?.is_interloper ?? false,
      fastRot: c?.fast_rotation ?? false,
    };

    const f = t2[a.id] as Record<string, unknown> | undefined;
    if (f) {
      const raw = (f['anomalies'] as Record<string, string> | null) ?? {};
      flyby[a.id] = {
        albedo: f['albedo'] as number,
        diam: f['diameter_km'] as number,
        massStr: f['mass_str'] as string,
        densStr: f['density_str'] as string,
        period: f['period_h'] as number,
        binary: f['has_satellite'] as boolean,
        structure: f['structure'] as string,
        h2o: f['h2o_level'] as number,
        eco: (f['eco'] as string[]) ?? [],
        mag: f['magnetic'] as boolean,
        anomaly: {
          albedo: raw['albedo'],
          diam: raw['diameter_km'],
          dens: raw['density_str'],
          period: raw['period_h'],
          binary: raw['has_satellite'],
          h2o: raw['h2o_level'],
          mag: raw['magnetic'],
          eco: raw['eco'],
        },
      };
    }

    const s = t3[a.id] as Record<string, unknown> | undefined;
    if (s) {
      stop[a.id] = {
        minerals: s['minerals'] as string,
        eco: (s['eco'] as string[]) ?? [],
        h2o: s['h2o_level'] as number,
        special: (s['special'] as string | null) ?? null,
      };
    }
  }

  return {
    base: {
      x: 50,
      y: 50,
      vx: baseItem.vx_kms * 1000,
      vy: baseItem.vy_kms * 1000,
      vz: baseItem.vz_kms * 1000,
    },
    asteroids,
    catalog,
    flyby,
    stop,
  };
}
