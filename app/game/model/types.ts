export type SpectralType = 'S' | 'C' | 'E' | 'V' | 'M' | 'D' | 'P' | 'K' | 'U';

export const SPECTRAL_COLORS: Record<SpectralType, string> = {
  S: '#c89836', C: '#60586a', E: '#d8d6d2', V: '#9c2e24',
  M: '#9c9a98', D: '#785040', P: '#6b5440', K: '#a07a4a', U: '#6e6e6e',
};

export const SPECTRAL_SURFACE_RGB: Record<SpectralType, [number, number, number]> = {
  S: [168, 138, 72], C: [50, 46, 56], E: [224, 218, 210], V: [112, 42, 36],
  M: [140, 138, 136], D: [118, 80, 62], P: [107, 84, 64], K: [160, 122, 74], U: [110, 110, 110],
};

export interface Asteroid {
  id: number;
  name: string;
  type: SpectralType;
  x: number;   // map % (0–100)
  y: number;   // map % (0–100)
  r: number;   // display radius (px)
  vx: number;  // proper-element velocity x (m/s) — §db_design §9.1
  vy: number;  // proper-element velocity y (m/s)
  vz: number;  // proper-element velocity z (m/s)
}

export interface Base {
  x: number;   // map % — always 50
  y: number;   // map % — always 50
  vx: number;  // m/s
  vy: number;  // m/s
  vz: number;  // m/s
}

export type RouteMode = 'stop' | 'flyby';

export interface RouteEntry {
  id: number;
  mode: RouteMode;
}

export interface AsteroidCatalog {
  albedo: number | null;
  diam: number | null;
  massStr: string | null;
  period: number | null;
  binary: boolean;
  structure: string;
  h2o: number;
  eco: string[];
  interloper: boolean;
  fastRot: boolean;
}

export interface FlybyAnomalies {
  albedo?: string;
  diam?: string;
  dens?: string;
  period?: string;
  binary?: string;
  h2o?: string;
  mag?: string;
  eco?: string;
}

export interface AsteroidFlyby {
  albedo: number;
  diam: number;
  massStr: string;
  densStr: string;
  period: number;
  binary: boolean;
  structure: string;
  h2o: number;
  eco: string[];
  mag: boolean;
  anomaly: FlybyAnomalies;
}

export interface AsteroidStop {
  minerals: string;
  eco: string[];
  h2o: number;
  special: string | null;
}

export interface Scene {
  base: Base;
  asteroids: Asteroid[];
  catalog: Record<number, AsteroidCatalog>;
  flyby: Record<number, AsteroidFlyby>;
  stop: Record<number, AsteroidStop>;
}
