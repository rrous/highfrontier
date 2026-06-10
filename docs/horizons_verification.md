# Ověření poloh a Δv proti JPL Horizons

- **Epocha:** 2026-06-04 00:00 UT
- **Vygenerováno:** 2026-06-10 11:59 UTC
- **Zdroj:** JPL Horizons API (`EPHEM_TYPE=VECTORS`)
- **Rámec:** heliocentrický (Slunce, `500@10`), ekliptika J2000, jednotky km / km·s⁻¹
- **Referenční těleso:** 8 Flora (A847 UA) (rec #8)

> **Δv** = velikost rozdílu heliocentrických rychlostních vektorů oproti Floře (velocity-space distance), shodně s definicí `deltaV()` v `app/game/physics/flight.ts`. Nejde o rozpočet na přeletový manévr.

## Referenční stav — Flora

| veličina | X | Y | Z |
|---|---:|---:|---:|
| poloha [AU] | 0.303524 | -2.302095 | 0.055243 |
| poloha [km] | 4.541e+07 | -3.444e+08 | 8.264e+06 |
| rychlost [km/s] | 18.181377 | 5.156957 | -1.942309 |

## Souhrn — cílová tělesa vs. Flora

| těleso | rec # | Horizons rozlišil | vzdálenost [AU] | vzdálenost [km] | Δv [km/s] | Δv [m/s] |
|---|---|---|---:|---:|---:|---:|
| Ulyanov | 2112 | 2112 Ulyanov (1972 NP) | 0.069229 | 1.036e+07 | 2.818083 | 2818.1 |
| Begzhigitova | 17102 | 17102 Begzhigitova (1999 JB41) | 0.087077 | 1.303e+07 | 1.050470 | 1050.5 |
| Gerardfaure | 8297 | 8297 Gerardfaure (1993 QJ4) | 0.091833 | 1.374e+07 | 4.045909 | 4045.9 |
| Elenacuoghi | 58580 | 58580 Elenacuoghi (1997 SW2) | 0.143522 | 2.147e+07 | 2.183664 | 2183.7 |

## Rozklad Δv po složkách (těleso − Flora)

> Konvence `těleso − Flora` shodná s polem `dv*_kms` ve `snapshot_daily.py` (`v_target − v_base`). Velikost `|Δv|` je na znaménku nezávislá.

| těleso | ΔVX [m/s] | ΔVY [m/s] | ΔVZ [m/s] | \|Δv\| [km/s] | \|Δv\| [m/s] |
|---|---:|---:|---:|---:|---:|
| Ulyanov | -103.5 | -481.0 | +2774.8 | 2.818083 | 2818.1 |
| Begzhigitova | +322.2 | -153.2 | +988.0 | 1.050470 | 1050.5 |
| Gerardfaure | +701.4 | -3673.4 | +1543.9 | 4.045909 | 4045.9 |
| Elenacuoghi | -74.2 | -2154.6 | -347.6 | 2.183664 | 2183.7 |

## Analýza přeletu — proč Δv vychází v km/s

Oskulační dráha Flory: a = 2.2016 AU, e = 0.1562, i = 5.89°. Rozhodující nákladová položka je **vzájemný sklon rovin drah** (kombinace rozdílu sklonu i výstupného uzlu): otočení roviny při orbitální rychlosti ~17–19 km/s stojí `2·v·sin(Δi/2)`. Tento rozdíl nelze odstranit fázováním (čekáním na výhodnou polohu) — je to vlastnost drah, ne okamžiku.

| těleso | a [AU] | e | i [°] | vzáj. sklon [°] | Δv roviny [km/s] | Δv v rovině [m/s] | odhad přeletu¹ [km/s] | okamžitý \|Δv\| [km/s] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Ulyanov | 2.2539 | 0.1372 | 3.37 | 8.55 | 2.556 | 235 | 2.88 | 2.818 |
| Begzhigitova | 2.2238 | 0.1451 | 4.23 | 3.94 | 1.178 | 101 | 1.37 | 1.050 |
| Gerardfaure | 2.2378 | 0.0613 | 3.59 | 4.77 | 1.427 | 163 | 1.68 | 4.046 |
| Elenacuoghi | 2.2057 | 0.1213 | 7.16 | 1.37 | 0.410 | 19 | 0.52 | 2.184 |

¹ změna roviny u aféru + Hohmann mezi velkými poloosami + únik z Flory (87 m/s); impulzní odhad nezávislý na fázi drah. Zanedbává sladění excentricity (u Gerardfaure významné) a zachycení u cílového tělesa (~m/s) — jde o dolní odhad. Tam, kde okamžitý |Δv| vychází výrazně výš než odhad přeletu (Gerardfaure, Elenacuoghi), rozdíl způsobuje aktuální fáze drah a dá se zlevnit načasováním; složka roviny (Ulyanov) se načasovat nedá.

**Závěr pro herní model:** skutečná cena rendezvous mezi tělesy rodiny Flora je řádově **0,5–4 km/s**, nikoli fixních 150 m/s — trasa se musí platit **postupným vyrovnáváním rychlostí po segmentech** (`|v_cíl − v_aktuální|`), viz `app/DESIGN.md` §5.2 a `db_design.md` §11.3.

## Stavové vektory cílových těles

| těleso | X [AU] | Y [AU] | Z [AU] | VX [km/s] | VY [km/s] | VZ [km/s] |
|---|---:|---:|---:|---:|---:|---:|
| Ulyanov | 0.303139 | -2.367485 | 0.077971 | 18.077890 | 4.675922 | 0.832486 |
| Begzhigitova | 0.291554 | -2.289704 | 0.140598 | 18.503559 | 5.003801 | -0.954266 |
| Gerardfaure | 0.270886 | -2.329267 | 0.136666 | 18.882737 | 1.483579 | -0.398363 |
| Elenacuoghi | 0.180733 | -2.376048 | 0.062447 | 18.107219 | 3.002406 | -2.289871 |
