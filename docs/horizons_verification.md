# Ověření poloh a Δv proti JPL Horizons

- **Epocha:** 2026-06-04 00:00 UT
- **Vygenerováno:** 2026-06-04 14:21 UTC
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

## Stavové vektory cílových těles

| těleso | X [AU] | Y [AU] | Z [AU] | VX [km/s] | VY [km/s] | VZ [km/s] |
|---|---:|---:|---:|---:|---:|---:|
| Ulyanov | 0.303139 | -2.367485 | 0.077971 | 18.077890 | 4.675922 | 0.832486 |
| Begzhigitova | 0.291554 | -2.289704 | 0.140598 | 18.503559 | 5.003801 | -0.954266 |
| Gerardfaure | 0.270886 | -2.329267 | 0.136666 | 18.882737 | 1.483579 | -0.398363 |
| Elenacuoghi | 0.180733 | -2.376048 | 0.062447 | 18.107219 | 3.002406 | -2.289871 |
