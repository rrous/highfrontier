"""
Flora Bulk v3 — analýza nad lokální cache
  Krok 1: načtení datasetu z TMP/flora_zone.csv.gz
  Krok 2: stavový vektor (R, V) -> klasické orbitální elementy (validace)
  Krok 3: elementy -> kartézská pozice k epoše TARGET_JD
  Krok 4: 50 těles nejbližších k poloze Flory
"""
import gzip, csv, os, math

AU_TO_KM = 1.49597870700e+08
GM_SUN   = 1.32712440018e+11   # km^3 / s^2
TARGET_JD = 2461182.5
FLORA_R = [2.490763083815513e+07, -3.494963800023187e+08,  1.042812151715852e+07]
FLORA_V = [1.830475195341738e+01,  3.940070836350522e+00, -1.909535899674513e+00]

CACHE = os.path.join(os.path.dirname(__file__), "flora_zone.csv.gz")


# ── vektorová aritmetika ──────────────────────────────────────────────────────
def vdot(a, b):   return sum(x * y for x, y in zip(a, b))
def vnorm(a):     return math.sqrt(vdot(a, a))
def vcross(a, b):
    return [a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0]]
def vsub(a, b):   return [x - y for x, y in zip(a, b)]
def vscale(a, s): return [x * s for x in a]
def norm3(a, b):  return vnorm(vsub(a, b))   # vzdálenost dvou bodů (km)


# ── stavový vektor -> orbitální elementy ──────────────────────────────────────
def state_to_elements(r_vec, v_vec, mu):
    r = vnorm(r_vec)
    v = vnorm(v_vec)
    rv = vdot(r_vec, v_vec)
    energy = v * v / 2.0 - mu / r
    a = -mu / (2.0 * energy)
    h_vec = vcross(r_vec, v_vec)
    h = vnorm(h_vec)
    n_vec = [-h_vec[1], h_vec[0], 0.0]
    n = vnorm(n_vec)
    e_vec = vscale(
        vsub(vscale(r_vec, v * v - mu / r), vscale(v_vec, rv)), 1.0 / mu)
    e = vnorm(e_vec)
    inc = math.degrees(math.acos(max(-1.0, min(1.0, h_vec[2] / h))))
    if n > 1e-12:
        raan = math.degrees(math.acos(max(-1.0, min(1.0, n_vec[0] / n))))
        if n_vec[1] < 0:
            raan = 360.0 - raan
    else:
        raan = 0.0
    if n > 1e-12 and e > 1e-12:
        argp = math.degrees(math.acos(
            max(-1.0, min(1.0, vdot(n_vec, e_vec) / (n * e)))))
        if e_vec[2] < 0:
            argp = 360.0 - argp
    else:
        argp = 0.0
    period_days = 2.0 * math.pi * math.sqrt(a ** 3 / mu) / 86400.0
    return {"a_AU": a / AU_TO_KM, "e": e, "i_deg": inc,
            "raan_deg": raan, "argp_deg": argp,
            "period_yr": period_days / 365.25}


# ── Keplerova rovnice ─────────────────────────────────────────────────────────
def solve_kepler(M, e):
    """M, výsledek E v radiánech."""
    E = M if e < 0.8 else math.pi
    for _ in range(60):
        dE = (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-13:
            break
    return E


# ── orbitální elementy -> kartézská pozice (a rychlost) k cílové epoše ────────
def elements_to_cartesian(a, e, i, om, w, ma, epoch_jd,
                          target_jd=TARGET_JD, mu=GM_SUN):
    """
    a [AU], e [-], i/om/w/ma [deg], epoch_jd [JD] = epocha platnosti 'ma'.
    Střední anomálie se propaguje z epoch_jd na target_jd.
    Vrací (pos_km, vel_kms) v ekliptikálních souřadnicích.
    """
    a_km = a * AU_TO_KM
    i  = math.radians(i)
    om = math.radians(om)
    w  = math.radians(w)
    M0 = math.radians(ma)

    # propagace střední anomálie na cílovou epochu
    n = math.sqrt(mu / a_km ** 3)                 # rad/s
    dt = (target_jd - epoch_jd) * 86400.0         # s
    M = (M0 + n * dt) % (2.0 * math.pi)

    E = solve_kepler(M, e)
    nu = 2.0 * math.atan2(math.sqrt(1.0 + e) * math.sin(E / 2.0),
                          math.sqrt(1.0 - e) * math.cos(E / 2.0))
    r = a_km * (1.0 - e * math.cos(E))

    # perifokální soustava
    xp, yp = r * math.cos(nu), r * math.sin(nu)
    p = a_km * (1.0 - e * e)
    h = math.sqrt(mu * p)
    vxp = -mu / h * math.sin(nu)
    vyp =  mu / h * (e + math.cos(nu))

    # rotace perifokální -> ekliptikální (3-1-3: R3(-om) R1(-i) R3(-w))
    cO, sO = math.cos(om), math.sin(om)
    ci, si = math.cos(i),  math.sin(i)
    cw, sw = math.cos(w),  math.sin(w)
    R = [[cO*cw - sO*sw*ci, -cO*sw - sO*cw*ci,  sO*si],
         [sO*cw + cO*sw*ci, -sO*sw + cO*cw*ci, -cO*si],
         [sw*si,             cw*si,             ci]]
    pos = [R[0][0]*xp + R[0][1]*yp,
           R[1][0]*xp + R[1][1]*yp,
           R[2][0]*xp + R[2][1]*yp]
    vel = [R[0][0]*vxp + R[0][1]*vyp,
           R[1][0]*vxp + R[1][1]*vyp,
           R[2][0]*vxp + R[2][1]*vyp]
    return pos, vel


# ── Krok 1: načtení datasetu z lokální cache ──────────────────────────────────
print("=== Načtení datasetu z lokální cache ===")
with gzip.open(CACHE, "rt") as f:
    records = list(csv.DictReader(f))
print(f"  Soubor: {CACHE}")
print(f"  Načteno {len(records)} záznamů, pole: {list(records[0].keys())}")


# ── Krok 2: stavový vektor FLORA -> orbitální elementy (validace) ─────────────
print("\n=== Stavový vektor FLORA -> orbitální elementy ===")
el = state_to_elements(FLORA_R, FLORA_V, GM_SUN)
print(f"  a={el['a_AU']:.6f} AU  e={el['e']:.6f}  i={el['i_deg']:.6f} deg  "
      f"perioda={el['period_yr']:.4f} let")


# ── Krok 3 + 4: pozice všech těles a 50 nejbližších k Floře ───────────────────
print("\n=== Hledání 50 nejbližších těles k poloze Flory ===")
print(f"  Cílová epocha JD = {TARGET_JD}")

results = []
skipped = 0
for rec in records:
    try:
        a  = float(rec["a"])
        e  = float(rec["e"])
        i  = float(rec["i"])
        om = float(rec["om"])
        w  = float(rec["w"])
        ma = float(rec["ma"])
        epoch_jd = float(rec["epoch"])
    except (ValueError, KeyError):
        skipped += 1
        continue
    pos, vel = elements_to_cartesian(a, e, i, om, w, ma, epoch_jd)
    d_km = norm3(FLORA_R, pos)
    name = rec["full_name"].strip()
    results.append((name, d_km, d_km / AU_TO_KM))

results.sort(key=lambda x: x[1])
print(f"  Spočítáno {len(results)} těles ({skipped} přeskočeno kvůli chybějícím elementům)\n")

print(f"  {'#':>3}  {'Těleso':<34} {'vzdálenost':>12}   {'':>14}")
for rank, (name, d_km, d_AU) in enumerate(results[:50], start=1):
    print(f"  {rank:>3}  {name:<34} {d_AU:>9.4f} AU  =  {d_km/1e6:>9.1f} mil. km")
