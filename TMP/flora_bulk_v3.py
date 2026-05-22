"""
Flora Bulk v3 — funkční verze
  Krok 1: SBDB bulk dotaz (Flora zóna)
  Krok 2: kontrola přes astroquery
  Krok 3: stavový vektor (R, V) -> klasické orbitální elementy
"""
import urllib.request, urllib.parse, json, math

AU_TO_KM = 1.49597870700e+08
GM_SUN   = 1.32712440018e+11   # km^3 / s^2
TARGET_JD = 2461182.5
FLORA_R = [2.490763083815513e+07, -3.494963800023187e+08,  1.042812151715852e+07]
FLORA_V = [1.830475195341738e+01,  3.940070836350522e+00, -1.909535899674513e+00]

SBDB = "https://ssd-api.jpl.nasa.gov/sbdb_query.api"


def sbdb_query(fields, cdata=None, sb_class=None, limit=None):
    params = {"fields": ",".join(fields)}
    if cdata:
        params["sb-cdata"] = json.dumps(cdata)
    if sb_class:
        params["sb-class"] = sb_class
    if limit:
        params["limit"] = str(limit)
    url = SBDB + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


# ── vektorová pomocná aritmetika ──────────────────────────────────────────────
def vdot(a, b):  return sum(x * y for x, y in zip(a, b))
def vnorm(a):    return math.sqrt(vdot(a, a))
def vcross(a, b):
    return [a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0]]
def vsub(a, b):  return [x - y for x, y in zip(a, b)]
def vscale(a, s):return [x * s for x in a]


def state_to_elements(r_vec, v_vec, mu):
    """Stavový vektor (km, km/s) -> klasické orbitální elementy."""
    r = vnorm(r_vec)
    v = vnorm(v_vec)
    rv = vdot(r_vec, v_vec)

    # specifická energie -> velká poloosa
    energy = v * v / 2.0 - mu / r
    a = -mu / (2.0 * energy)

    # moment hybnosti
    h_vec = vcross(r_vec, v_vec)
    h = vnorm(h_vec)

    # uzlová přímka (K x h)
    n_vec = [-h_vec[1], h_vec[0], 0.0]
    n = vnorm(n_vec)

    # vektor excentricity
    e_vec = vscale(
        vsub(vscale(r_vec, v * v - mu / r), vscale(v_vec, rv)),
        1.0 / mu,
    )
    e = vnorm(e_vec)

    # inklinace
    inc = math.degrees(math.acos(max(-1.0, min(1.0, h_vec[2] / h))))

    # rektascenze výstupního uzlu
    if n > 1e-12:
        raan = math.degrees(math.acos(max(-1.0, min(1.0, n_vec[0] / n))))
        if n_vec[1] < 0:
            raan = 360.0 - raan
    else:
        raan = 0.0

    # argument perihelu
    if n > 1e-12 and e > 1e-12:
        argp = math.degrees(math.acos(
            max(-1.0, min(1.0, vdot(n_vec, e_vec) / (n * e)))))
        if e_vec[2] < 0:
            argp = 360.0 - argp
    else:
        argp = 0.0

    # pravá anomálie
    if e > 1e-12:
        nu = math.degrees(math.acos(
            max(-1.0, min(1.0, vdot(e_vec, r_vec) / (e * r)))))
        if rv < 0:
            nu = 360.0 - nu
    else:
        nu = 0.0

    period_days = 2.0 * math.pi * math.sqrt(a ** 3 / mu) / 86400.0

    return {
        "a_AU": a / AU_TO_KM,
        "e": e,
        "i_deg": inc,
        "raan_deg": raan,
        "argp_deg": argp,
        "nu_deg": nu,
        "period_yr": period_days / 365.25,
        "r_AU": r / AU_TO_KM,
        "v_kms": v,
    }


# ── Krok 1: SBDB bulk dotaz s opravenými filtry ───────────────────────────────
print("=== SBDB bulk dotaz (Flora zóna) ===")
constraint = {"AND": ["a|RG|2.17|2.33", "e|LT|0.25", "i|LT|9"]}
try:
    res = sbdb_query(["spkid", "full_name", "a", "e", "i"], cdata=constraint)
    total = res.get("count")
    rows = res.get("data", [])
    print(f"  Constraint: {constraint['AND']}")
    print(f"  Celkem nalezeno: {total} těles")
    print(f"  Staženo v této odpovědi: {len(rows)} řádků")
    print(f"  Prvních 5:")
    for row in rows[:5]:
        spkid, name, a, e, i = row
        print(f"    {name.strip():<28} a={a:>7}  e={e:>7}  i={i:>6}")
except urllib.error.HTTPError as ex:
    print(f"  HTTP {ex.code}: {ex.read().decode()[:300]}")
except Exception as ex:
    print(f"  CHYBA: {ex}")


# ── Krok 2: kontrola přes astroquery (nezávislý zdroj) ────────────────────────
print("\n=== Kontrola přes astroquery (MPC) ===")
try:
    from astroquery.mpc import MPC
    result = MPC.query_objects(
        "asteroid",
        semimajor_axis_min=2.17,
        semimajor_axis_max=2.33,
        eccentricity_max=0.25,
        inclination_max=9.0,
        limit=100,
    )
    print(f"  Vráceno {len(result)} těles (limit 100)")
    if result:
        for obj in result[:5]:
            name = obj.get("name") or obj.get("designation") or "?"
            print(f"    {str(name):<28} a={obj.get('semimajor_axis')}  "
                  f"e={obj.get('eccentricity')}  i={obj.get('inclination')}")
except ImportError:
    print("  astroquery není nainstalovaná")
except Exception as ex:
    print(f"  astroquery chyba: {type(ex).__name__}: {ex}")


# ── Krok 3: stavový vektor -> orbitální elementy ──────────────────────────────
print("\n=== Stavový vektor FLORA -> orbitální elementy ===")
print(f"  Epocha JD = {TARGET_JD}")
el = state_to_elements(FLORA_R, FLORA_V, GM_SUN)
print(f"  |R| = {el['r_AU']:.6f} AU      |V| = {el['v_kms']:.6f} km/s")
print(f"  a   = {el['a_AU']:.6f} AU")
print(f"  e   = {el['e']:.6f}")
print(f"  i   = {el['i_deg']:.6f} deg")
print(f"  RAAN= {el['raan_deg']:.6f} deg")
print(f"  argp= {el['argp_deg']:.6f} deg")
print(f"  nu  = {el['nu_deg']:.6f} deg")
print(f"  oběžná doba = {el['period_yr']:.4f} let")

ref = {"a": 2.201, "e": 0.1563, "i": 5.89}
print(f"\n  Porovnání s SBDB pro 8 Flora "
      f"(a={ref['a']}, e={ref['e']}, i={ref['i']}):")
print(f"    da = {el['a_AU'] - ref['a']:+.4f} AU   "
      f"de = {el['e'] - ref['e']:+.4f}   "
      f"di = {el['i_deg'] - ref['i']:+.3f} deg")
