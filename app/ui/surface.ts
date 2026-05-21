import { SPECTRAL_SURFACE_RGB } from '../game/model/types';
import type { SpectralType } from '../game/model/types';

/** Renders the asteroid surface canvas in the INFO card. */
export function drawSurface(canvas: HTMLCanvasElement, type: SpectralType, seed: number): void {
  const W = (canvas.width = canvas.offsetWidth || 390);
  const H = (canvas.height = canvas.offsetHeight || 185);
  const ctx = canvas.getContext('2d')!;
  const [r, g, b] = SPECTRAL_SURFACE_RGB[type] ?? [80, 80, 80];

  // Space background
  ctx.fillStyle = '#020406';
  ctx.fillRect(0, 0, W, H);

  // Background stars (deterministic from seed)
  let s = (seed || 99991) >>> 0;
  const sr = () => { s ^= s << 13; s ^= s >> 17; s ^= s << 5; return (s >>> 0) / 4_294_967_296; };
  for (let i = 0; i < 55; i++) {
    ctx.fillStyle = `rgba(180,210,240,${(sr() * 0.38 + 0.05).toFixed(2)})`;
    ctx.beginPath();
    ctx.arc(sr() * W, sr() * H, sr() * 0.8 + 0.1, 0, Math.PI * 2);
    ctx.fill();
  }

  // Asteroid body (oval, slight diagonal tilt)
  const cx = W * 0.47, cy = H * 0.5, rx = H * 0.4, ry = H * 0.34;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-0.22);

  const gBody = ctx.createRadialGradient(-rx * 0.28, -ry * 0.28, rx * 0.04, rx * 0.08, ry * 0.06, rx * 1.18);
  gBody.addColorStop(0, `rgb(${Math.min(r + 85, 255)},${Math.min(g + 78, 255)},${Math.min(b + 62, 255)})`);
  gBody.addColorStop(0.42, `rgb(${r},${g},${b})`);
  gBody.addColorStop(1, `rgb(${Math.max(r - 55, 0)},${Math.max(g - 50, 0)},${Math.max(b - 45, 0)})`);
  ctx.beginPath();
  ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = gBody;
  ctx.fill();

  const gTerm = ctx.createRadialGradient(rx * 0.52, ry * 0.38, rx * 0.1, rx * 0.52, ry * 0.38, rx * 1.08);
  gTerm.addColorStop(0, 'rgba(0,0,0,0)');
  gTerm.addColorStop(0.55, 'rgba(0,0,0,0)');
  gTerm.addColorStop(1, 'rgba(0,0,0,.70)');
  ctx.beginPath();
  ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = gTerm;
  ctx.fill();

  const gLimb = ctx.createRadialGradient(0, 0, rx * 0.52, 0, 0, rx * 1.01);
  gLimb.addColorStop(0, 'rgba(0,0,0,0)');
  gLimb.addColorStop(0.72, 'rgba(0,0,0,0)');
  gLimb.addColorStop(1, 'rgba(0,0,0,.65)');
  ctx.beginPath();
  ctx.ellipse(0, 0, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = gLimb;
  ctx.fill();
  ctx.restore();

  // Scanlines
  ctx.fillStyle = 'rgba(0,0,0,.07)';
  for (let y = 0; y < H; y += 2) ctx.fillRect(0, y, W, 1);

  // Placeholder label
  ctx.fillStyle = 'rgba(80,120,150,.38)';
  ctx.font = '9px "Share Tech Mono",monospace';
  ctx.textAlign = 'center';
  ctx.fillText('· TIER 3 FLYBY REQUIRED ·', W / 2, H - 8);
}
