import type { Scene, Asteroid, AsteroidCatalog, AsteroidFlyby, AsteroidStop, SpectralType } from '../game/model/types';

const SB_URL = 'https://tfyuyylcygamglpdfudd.supabase.co';
const SB_KEY = 'sb_publishable_DH6ePHNli_LbFfwFuci0Cg_EE408poO';
const HDR: HeadersInit = { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` };

async function get(path: string): Promise<unknown[]> {
  const r = await fetch(`${SB_URL}${path}`, { headers: HDR });
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`);
  return r.json() as Promise<unknown[]>;
}

async function rpc(fn: string, body: Record<string, unknown>): Promise<unknown[]> {
  const r = await fetch(`${SB_URL}/rest/v1/rpc/${fn}`, {
    method: 'POST',
    headers: { ...HDR, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`RPC ${fn} → ${r.status}`);
  return r.json() as Promise<unknown[]>;
}

/** URL query params: ?base=&radius=&n=  (all optional; default = base 'Flora') */
export async function loadScene(params: URLSearchParams): Promise<Scene> {
  const baseName = params.get('base') ?? 'Flora';
  const radius = parseFloat(params.get('radius') ?? '');
  const wantN = parseInt(params.get('n') ?? '', 10) || 20;
  const searchRadius = Number.isFinite(radius) ? radius : 100_000;

  // surroundings of a named base — `db_design.md` §11.1, RPC `base_surroundings`.
  // The base's own asteroid is included in the result at delta_v = 0.
  const all = await rpc('base_surroundings', { base_name: baseName, radius: searchRadius, max_n: 100 }) as Array<{
    id: number; name: string; spectral_type: string;
    x_pos: number; y_pos: number; z_pos: number | null;
    r_size: number; albedo: number | null; diameter_km: number | null;
    mass_str: string | null; period_h: number | null; has_satellite: boolean;
    structure: string; h2o_level: number; eco: string[] | null;
    is_interloper: boolean; fast_rotation: boolean;
    dx: number; dy: number; dz: number; delta_v: number;
  }>;

  const baseRow = all.find(a => a.name === baseName);
  if (!baseRow) throw new Error(`Base ${baseName} not found in DB`);
  const qx = baseRow.x_pos;
  const qy = baseRow.y_pos;
  const qz = baseRow.z_pos ?? 0;

  const neighbours = all.filter(a => a.name !== baseName).slice(0, wantN);
  const rawAsteroids = [...neighbours, baseRow];

  // Projection radius: furthest neighbour + 15% margin
  let projR = 0;
  neighbours.forEach(a => {
    const d = Math.hypot(a.dx, a.dy);
    if (d > projR) projR = d;
  });
  projR = projR * 1.15 || 1000;

  if (rawAsteroids.length === 0) {
    return { base: { x: 50, y: 50, vx: qx, vy: qy, vz: qz }, asteroids: [], catalog: {}, flyby: {}, stop: {} };
  }

  const idList = `(${rawAsteroids.map(a => a.id).join(',')})`;
  const [tier2Raw, tier3Raw] = await Promise.all([
    get(`/rest/v1/asteroid_tier2?select=*&asteroid_id=in.${idList}`),
    get(`/rest/v1/asteroid_tier3?select=*&asteroid_id=in.${idList}`),
  ]) as [Array<Record<string, unknown>>, Array<Record<string, unknown>>];

  const t2 = Object.fromEntries(tier2Raw.map(t => [(t['asteroid_id'] as number), t]));
  const t3 = Object.fromEntries(tier3Raw.map(t => [(t['asteroid_id'] as number), t]));

  const asteroids: Asteroid[] = rawAsteroids.map(a => {
    const isBase = a.name === baseName;
    return {
      id: a.id,
      name: a.name,
      type: (a.spectral_type as SpectralType) || 'U',
      x: isBase ? 55 : 50 + 50 * a.dx / projR,
      y: isBase ? 58 : 50 + 50 * a.dy / projR,
      r: a.r_size,
      vx: a.x_pos,
      vy: a.y_pos,
      vz: a.z_pos ?? 0,
    };
  });

  const catalog: Record<number, AsteroidCatalog> = {};
  const flyby: Record<number, AsteroidFlyby> = {};
  const stop: Record<number, AsteroidStop> = {};

  for (const a of rawAsteroids) {
    catalog[a.id] = {
      albedo: a.albedo,
      diam: a.diameter_km,
      massStr: a.mass_str,
      period: a.period_h,
      binary: a.has_satellite,
      structure: a.structure,
      h2o: a.h2o_level,
      eco: a.eco ?? [],
      interloper: a.is_interloper,
      fastRot: a.fast_rotation,
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
    base: { x: 50, y: 50, vx: qx, vy: qy, vz: qz },
    asteroids,
    catalog,
    flyby,
    stop,
  };
}
