# HighFrontier — Database Design Document
## Backend pro Flora asteroid pole

> Stav: v0.2 · Cíl: Supabase / PostgreSQL · Doplněk k `highfrontier_poc_design_v04.md` (sekce 6–7)  
> Tento dokument definuje **obsah** DB. Sekce 0 popisuje skutečně nasazený stav.

---

## 0. Stav implementace (2026-05-20)

Pipeline (`pipeline/fetch_flora.py`) vygenerovala katalog `raw_data/flora_full.json`
a data jsou nahraná v Supabase. Skutečný stav se v několika bodech liší od
původního návrhu v0.1 níže:

| Položka | Návrh v0.1 | Skutečnost |
|---|---|---|
| Počet těles | 10 000 (cíl) | **13 786** |
| Schéma | nerozhodnuto (sekce 9) | 3 ploché tabulky: `asteroids`, `asteroid_tier2`, `asteroid_tier3` |
| Composition | JSONB blob (návrh) | `asteroid_tier3.minerals` jako textový řetězec |
| Tier model | T1/T2/T3 jako sloupce/null | jedna tabulka per tier, FK `asteroid_id` → `asteroids.id` |

**Datový tok:** `flora_full.json` → `pipeline/transform_to_db.py` (ETL adaptér,
mapuje vědecký katalog na schéma route planneru) → Supabase. Migrace schématu je
v `pipeline/migration_route_planner.sql`, proximity dotaz pro klienta v
`pipeline/rpc_nearby_asteroids.sql` (funkce `nearby_asteroids` — vrátí tělesa
v zadaném dosahu, seřazená podle fyzické 3D vzdálenosti (km), strop 100).

**Pozor:** kalibrační cíle (sekce 3, 7, 8) byly laděné na 10 000 těles. Při
13 786 tělesech jsou absolutní počty rare finds a užitečných těles odpovídajícím
způsobem vyšší; procenta zhruba platí. Přeladění je otevřený bod (sekce 9).

---

## 1. Účel a kontext

Backend DB drží 13 786 asteroidů Flora regionu. Klient (HTML/Godot) si přes API stahuje scény (max 100 těles dle souřadnic — funkce `nearby_asteroids`) a postupně odhaluje data podle Tier mechanismu:

```
Tier 1 (katalog)   = co JPL/WISE skutečně ví → některá pole null
Tier 2 (flyby)     = pravda o pozorovatelných parametrech (mass, density, rotation, spectral)
Tier 3 (zastávka)  = mineralogie + rare finds
```

**Klíčový princip:** všech 10k těles je "reálných" v tom smyslu, že má JPL orbitální elementy. Procedurální vrstva nedoplňuje neexistující asteroidy — doplňuje **pravdu skrytou za měřicí gap** (tj. když JPL nemá albedo, hra ji má, hráč ji odhalí Tier 2 skenem).

---

## 2. Datová provenance

| Co | Zdroj | Stav |
|---|---|---|
| Orbitální elementy 10k Flora | JPL SBDB + AstDyS (Nesvorný 2015 family membership) | **REAL** |
| H magnituda | JPL | **REAL** |
| Změřená albeda (~35% těles) | WISE/NEOWISE (Masiero et al.) | **REAL** |
| Spektrální třídy (~12%) | SMASS II, Bus-DeMeo, SDSS MOC4 | **REAL** |
| Rotační periody (~5%) | LCDB (Warner et al.) | **REAL** |
| DAMIT shape modely (~1%) | astro.troja.mff.cuni.cz/projects/damit | **REAL** |
| Binární systémy (~0.5%) | Johnston's archive | **REAL** |
| Bulk mineralogie % per třída | Meteoritická literatura: LL/L (S), CM/CI (C), iron mets (M), HED (V), enstatit chondrites (E), Tagish Lake (D), CV/CO (K) | **REAL ranges** |
| Rare find existence | Murchison, Allende, Almahata Sitta, Khatyrka, Tagish Lake, Ryugu, Bennu | **REAL** |
| **Per-class rare find probabilities** | kalibrováno k designovým cílům (~25 legendary, ~300 exotic v 10k) | **MOJE KALIBRACE** |
| **Per-asteroid noise σ kolem mean** | designové rozhodnutí | **MOJE KALIBRACE** |
| **Game value $/kg (relativní)** | herní scoring, ne reálná ekonomika | **HERNÍ HODNOTY** |

> ⚠ Konkrétní probability čísla (např. "0.3% S-typů má microdiamonds") **nejsou z literatury** — jsou to designové cíle. Pokud chceš víc/méně rare finds, mění se zde.

---

## 3. Kalibrační cíle

| Metrika | Cíl | Mechanismus |
|---|---|---|
| Celkem těles | 10 000 | bulk generování + ~50–100 backbone se shape models |
| "Užitečných" (těžitelný resource v rozumné koncentraci) | ~13% (1 300) | per-class probability tabulky |
| LEGENDARY rare finds | ~25 v poli (0.25%) | per-find probability × spektrální distribuce |
| EXOTIC rare finds | ~300 v poli (3%) | per-find probability × distribuce |
| Hráč se "naučí" třída → typ payoff | po 5–10 misích | probabilities jsou deterministická funkce třídy/velikosti, ne náhodné |

---

## 4. Spektrální distribuce ve Flora poli

Zdroj: pozorovaná distribuce v inner main belt (DeMeo & Carry 2013) + Flora dynamika (Nesvorný 2015). Sloupec „Skutečnost" = vygenerovaný katalog `flora_full.json`.

| Třída | Cílový podíl | Skutečnost (13 786) | Poznámka |
|---|---|---|---|
| S | 70% | 9 724 (70.5%) | Flora family core, LL/L chondrity |
| C / Ch | 13% | 1 612 (11.7%) | nejčastější interloper v inner belt |
| V | 5% | 664 (4.8%) | Vesta fragmenty (Flora je sousední rodina) |
| D | 4% | 500 (3.6%) | tmavé, organické — vzácné v inner belt, ale možné |
| M (X-komplex) | 2% | 402 (2.9%) | kovová tělesa, vzácná |
| E (X-komplex) | 2% | 299 (2.2%) | enstatit, Hungaria-like interloper |
| P (X-komplex) | 2% | 242 (1.8%) | mezi C a D, primitivní |
| K | 1% | 180 (1.3%) | Eos-like interloper |
| U (Unknown) | 1% | 163 (1.2%) | nezařaditelné, hráč objeví Tier 2 |
| **Σ** | **100%** | **13 786** | |

> `spectral_type` v tabulce `asteroids` má check constraint na těchto 9 hodnot
> (`S, C, M, V, E, D, P, K, U`). Klient (route planner) má pro všech 9 typů
> barvu a legendu.

---

## 5. Resource catalog (52 položek)

Sloupce: `id` (snake_case), `name` (CZ), `category`, `rarity_tier` (COMMON / UNCOMMON / RARE / EXOTIC / LEGENDARY), `speculation` (CONFIRMED / PLAUSIBLE / SPECULATIVE), `game_value` (relativní $/kg, log scale 1–100000), `note`.

### 5.1 Bulk minerály (13)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `olivin` | olivin (Fa28-32) | mineral | COMMON | CONFIRMED | 1 | dominant v LL chondrites |
| `pyroxen_lowca` | nízko-Ca pyroxen (En76-78) | mineral | COMMON | CONFIRMED | 1 | enstatit-ferrosilit série |
| `pyroxen_highca` | vysoko-Ca pyroxen (augit) | mineral | COMMON | CONFIRMED | 1 | bazaltické textury |
| `plagioklas` | plagioklas (An40-90) | mineral | COMMON | CONFIRMED | 2 | feldspar |
| `enstatit` | enstatit (MgSiO₃) | mineral | COMMON | CONFIRMED | 2 | dominant v E-type |
| `fe_ni_metal` | Fe-Ni kov (kamacit + taenit) | construction | UNCOMMON | CONFIRMED | 5 | LL <3%, M 80%+ |
| `troilit` | troilit (FeS) | mineral | COMMON | CONFIRMED | 2 | sulfid, S+M+E |
| `fylosilikat` | fylosilikáty (serpentin, saponit) | mineral | COMMON | CONFIRMED | 3 | C-type, vážená H₂O |
| `magnetit` | magnetit (Fe₃O₄) | mineral | COMMON | CONFIRMED | 3 | C, D, P |
| `karbonaty` | karbonáty (Ca, Mg, Fe) | mineral | UNCOMMON | CONFIRMED | 4 | C-type, dusík |
| `ilmenit` | ilmenit (FeTiO₃) | construction | UNCOMMON | CONFIRMED | 12 | **zdroj Ti**, V-type |
| `chromit` | chromit (FeCr₂O₄) | construction | UNCOMMON | CONFIRMED | 10 | zdroj Cr, V+M |
| `schreibersite` | schreibersite (Fe,Ni)₃P | mineral | UNCOMMON | CONFIRMED | 15 | **zdroj P**, M+železné |

### 5.2 Konstrukční prvky (8)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `fe` | železo | construction | COMMON | CONFIRMED | 1 | extrahováno z Fe-Ni |
| `ni` | nikl | construction | UNCOMMON | CONFIRMED | 3 | z Fe-Ni metal |
| `co` | kobalt | electronics | UNCOMMON | CONFIRMED | 15 | baterie, M-type |
| `ti` | titanium | construction | RARE | CONFIRMED | 25 | z ilmenitu, V-type |
| `al` | hliník | construction | RARE | PLAUSIBLE | 18 | z plagioklasu, V |
| `cr` | chrom | construction | RARE | CONFIRMED | 30 | z chromitu |
| `w` | wolfram | construction | EXOTIC | PLAUSIBLE | 80 | trace v M-type |
| `si` | křemík | electronics | COMMON | CONFIRMED | 2 | všudypřítomný |

### 5.3 Vzácné kovy (PGM + Au) (7)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `pt` | platina | electronics | RARE | CONFIRMED | 500 | M-type jádro |
| `pd` | palladium | electronics | RARE | CONFIRMED | 400 | s Pt |
| `ir` | iridium | electronics | EXOTIC | CONFIRMED | 800 | nejhustší prvek |
| `rh` | rhodium | electronics | EXOTIC | CONFIRMED | 1200 | nejvzácnější PGM |
| `os` | osmium | electronics | EXOTIC | CONFIRMED | 700 | s Ir |
| `au` | zlato | electronics | RARE | CONFIRMED | 300 | trace v M, S |
| `cu` | měď | electronics | UNCOMMON | CONFIRMED | 8 | vedení, M+S |

### 5.4 Elektronika (5)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `ge` | germanium | electronics | RARE | CONFIRMED | 40 | polovodiče, M+S |
| `ga` | galium | electronics | RARE | CONFIRMED | 35 | M+S trace |
| `ree_light` | LREE (Nd, La, Ce) | electronics | EXOTIC | PLAUSIBLE | 60 | magnety, V-type |
| `ree_heavy` | HREE (Dy, Gd, Tb) | electronics | EXOTIC | PLAUSIBLE | 150 | vzácnější, K+V |
| `li` | lithium | electronics | RARE | PLAUSIBLE | 50 | baterie, C+D trace |

### 5.5 Propellant + energie (5)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `h2o_bound` | voda vázaná | propellant | UNCOMMON | CONFIRMED | 4 | ve fylosilikátech, C |
| `h2o_ice` | vodní led | propellant | RARE | CONFIRMED | 6 | povrch chladnějších těles |
| `ch4` | methan | propellant | EXOTIC | SPECULATIVE | 20 | Sabatier z CO₂+H₂ |
| `he3` | helium-3 | propellant | EXOTIC | PLAUSIBLE | 200 | povrch starých těles |
| `co2` | CO₂ (volatile) | propellant | RARE | PLAUSIBLE | 8 | C/D, vzácné v inner belt |

### 5.6 Life support (4)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `n` | dusík (sloučeniny) | life_support | EXOTIC | PLAUSIBLE | 150 | **velmi vzácný** — D, NH₃·H₂O |
| `p` | fosfor | life_support | RARE | CONFIRMED | 35 | ze schreibersite, M+C |
| `c_organic` | organický uhlík | life_support | RARE | CONFIRMED | 15 | C, D |
| `s` | síra | life_support | UNCOMMON | CONFIRMED | 6 | z troilitu/sulfidů |

### 5.7 Exotic + scientific (10)

| id | název | category | rarity | speculation | value | poznámka |
|---|---|---|---|---|---|---|
| `microdiamonds` | mikrodiamanty | scientific | LEGENDARY | CONFIRMED | 5000 | Canyon Diablo, ureility |
| `lonsdaleite` | lonsdaleite (hex. diamant) | scientific | LEGENDARY | CONFIRMED | 8000 | Almahata Sitta |
| `presolar_sic` | presolarní SiC | scientific | LEGENDARY | CONFIRMED | 15000 | Murchison, Allende |
| `quasicrystal` | kvazikrystaly | scientific | LEGENDARY | CONFIRMED | 50000 | Khatyrka (Nobel-grade) |
| `fullerene` | fullereny C₆₀ | scientific | EXOTIC | CONFIRMED | 800 | Allende, C-type |
| `amino_acids` | aminokyseliny (70+ druhů) | scientific | EXOTIC | CONFIRMED | 400 | Murchison, Ryugu 2022 |
| `ribose` | ribóza | scientific | LEGENDARY | CONFIRMED | 6000 | Oba et al. 2019 |
| `nucleobases` | nukleobáze (adenin, guanin, uracil) | scientific | EXOTIC | CONFIRMED | 700 | Murchison, NWA 7325 |
| `tholins` | tholiny (komplexní polymery) | exotic | EXOTIC | SPECULATIVE | 300 | analogicky Triton, Pluto |
| `magnetic_record` | paleomagnetický záznam | scientific | LEGENDARY | PLAUSIBLE | 12000 | M-type, raný sluneční systém |

---

## 6. Per-class composition templates

Pro každou spektrální třídu: bulk minerály s **mean ± σ %** a `reveal_tier`. Při generování:

```
composition[i] = mean[i] + N(0, σ[i])     # truncated to [0, 100]
                                          # renormalized so Σ = 100
```

σ je obvykle 20% relativní (např. mean 50 → σ 10), kromě hlavních minerálů kde je úzčí.

### 6.1 S-typ (LL/L chondrity, n=7000)

Zdroj: Itokawa sample analysis (Nakamura 2011), Brearley & Jones 1998.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| olivin | 52 | 6 | T3 | Fa28-32 |
| pyroxen_lowca | 24 | 4 | T3 | En76-78 |
| pyroxen_highca | 5 | 2 | T3 | |
| plagioklas | 9 | 2 | T3 | |
| fe_ni_metal | 4 | 3 | T3 | širší σ — LL vs L variability |
| troilit | 5 | 2 | T3 | |
| chromit | 0.5 | 0.3 | T3 | |
| **Σ ≈** | **~100** | | | |

### 6.2 C / Ch-typ (CM/CI, Ryugu, n=1300)

Zdroj: Yokoyama et al. 2023 (Ryugu), Murchison studies.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| fylosilikat | 65 | 8 | T3 | serpentin + saponit |
| magnetit | 6 | 2 | T3 | |
| troilit | 4 | 2 | T3 | + pyrrhotit |
| karbonaty | 4 | 2 | T3 | Ca/Mg/Fe |
| h2o_bound | 9 | 3 | T2 | **vidět z hustoty** |
| c_organic | 3 | 1.5 | T3 | 1.5% v Murchisonu, víc v Ryugu |
| olivin | 4 | 2 | T3 | relikt grains |
| pyroxen_lowca | 3 | 1.5 | T3 | |

### 6.3 M-typ (železné meteority, n=200)

Zdroj: Wasson 1985, Goldstein 2009.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| fe_ni_metal | 88 | 5 | T2 | **vidět z hustoty + magnetismus** |
| troilit | 6 | 2 | T3 | |
| schreibersite | 2 | 1 | T3 | |
| chromit | 0.5 | 0.3 | T3 | |
| pt | 0.005 | 0.003 | T3 | 10–100× zemská kůra |
| pd | 0.003 | 0.002 | T3 | |
| ir | 0.0005 | 0.0003 | T3 | |
| au | 0.0008 | 0.0005 | T3 | |
| ge | 0.05 | 0.03 | T3 | |
| ga | 0.04 | 0.03 | T3 | |
| (silikáty regolith) | 3 | 3 | T3 | mesosiderite-like rim |

### 6.4 E-typ (enstatit chondrity, n=200)

Zdroj: Keil 1968, Brearley & Jones 1998.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| enstatit | 70 | 8 | T3 | |
| fe_ni_metal | 14 | 5 | T3 | EH má víc, EL méně |
| troilit | 6 | 2 | T3 | + niningerit, oldhamit |
| plagioklas | 5 | 2 | T3 | |
| pyroxen_lowca | 3 | 2 | T3 | |
| (sulfidy speciální) | 2 | 1 | T3 | reduktivní podmínky |

### 6.5 P-typ (mezi C a D, n=200)

Zdroj: tentativní, žádný přímý meteorit analog. Modelováno jako "tmavší C" + víc organiky.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| fylosilikat | 50 | 8 | T3 | |
| magnetit | 12 | 3 | T3 | tmavší než C |
| c_organic | 6 | 3 | T3 | |
| troilit | 5 | 2 | T3 | |
| karbonaty | 8 | 3 | T3 | |
| h2o_bound | 12 | 3 | T2 | |
| olivin | 4 | 2 | T3 | |
| pyroxen_lowca | 3 | 1.5 | T3 | |

### 6.6 V-typ (HED — eucrit/diogenit/howardit, n=500)

Zdroj: McSween 1999, Mittlefehldt 1998.

Generujeme jako mix: 60% eucrit (basaltic) + 20% diogenit (orthopyroxenit) + 20% howardit (regolith breccia). Per asteroid se vybere podtyp s těmito vahami.

**Eucrit varianta:**

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| pyroxen_highca | 55 | 8 | T3 | pigeonit |
| plagioklas | 38 | 6 | T3 | Ca-bohatý |
| ilmenit | 2 | 1 | T3 | **Ti zdroj** |
| chromit | 0.8 | 0.4 | T3 | |
| (silica) | 3 | 2 | T3 | |
| olivin | 1 | 1 | T3 | |

**Diogenit varianta:**

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| pyroxen_lowca | 88 | 5 | T3 | orthopyroxene |
| olivin | 8 | 4 | T3 | někdy víc |
| plagioklas | 1 | 1 | T3 | |
| chromit | 1 | 0.5 | T3 | |

### 6.7 D-typ (Tagish Lake, n=400)

Zdroj: Brown et al. 2000, Zolensky et al. 2002. Pro Flora interlopery D-typ je trochu spekulativní (D-type je hlavně v outer belt) — předpokládáme zachycené fragmenty.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| fylosilikat | 40 | 6 | T3 | |
| magnetit | 9 | 3 | T3 | |
| c_organic | 11 | 4 | T3 | nejvíc ze všech tříd |
| troilit | 6 | 2 | T3 | |
| karbonaty | 7 | 3 | T3 | |
| h2o_bound | 10 | 3 | T2 | |
| olivin | 8 | 3 | T3 | |
| pyroxen_lowca | 5 | 2 | T3 | |
| (NH₃·H₂O) | 4 | 3 | T3 | jen u nejtmavších, SPECULATIVE |

### 6.8 K-typ (CV/CO-like, n=100)

Zdroj: DeMeo et al. 2009, K-type spektra.

| mineral | mean % | σ % | reveal | poznámka |
|---|---|---|---|---|
| olivin | 45 | 6 | T3 | |
| pyroxen_lowca | 28 | 5 | T3 | |
| pyroxen_highca | 5 | 2 | T3 | |
| fe_ni_metal | 5 | 2 | T3 | |
| plagioklas | 6 | 2 | T3 | |
| fylosilikat | 7 | 3 | T3 | některé K mají hydratovaná zrna |
| troilit | 4 | 2 | T3 | |

---

## 7. Rare finds probability matrix

Per find: pravděpodobnost přítomnosti na asteroidu dané třídy. Pokud roll uspěje, find se objeví v `asteroid_rare_finds` s deterministickou abundancí (mírně náhodnou ze seedu).

| find | S | C/Ch | M | E | P | V | D | K | reveal | size_pref | poznámka |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **LEGENDARY** | | | | | | | | | | | |
| microdiamonds | 0.1% | — | 0.3% | — | — | 0.05% | 0.1% | — | T3 | small (<2km) | Canyon Diablo, ureility |
| lonsdaleite | — | — | — | — | 0.05% | — | 0.3% | — | T3 | small | Almahata Sitta |
| presolar_sic | — | 0.1% | — | — | 0.1% | — | 0.1% | 0.05% | T3 | any | Murchison, Allende |
| quasicrystal | — | — | 0.3% | — | — | — | — | — | T3 | small monolithic | Khatyrka |
| ribose | — | 0.3% | — | — | 0.1% | — | 0.2% | — | T3 | rubble pile (>1km) | Oba 2019 |
| magnetic_record | — | — | 1.5% | 0.1% | — | — | — | — | T2 (anomaly) | medium+ | M-type studies |
| **EXOTIC** | | | | | | | | | | | |
| amino_acids | — | 3% | — | — | 0.5% | — | 2% | 0.3% | T3 | rubble pile | Murchison, Ryugu |
| nucleobases | — | 1% | — | — | 0.3% | — | 0.5% | — | T3 | rubble pile | Murchison, NWA |
| tholins | — | 0.5% | — | — | 0.5% | — | 3% | — | T3 | dark albedo | Tagish Lake |
| fullerene | — | 0.5% | — | — | 0.2% | — | 0.3% | 0.1% | T3 | any | Allende |
| he3_saturation | 2% | 2% | 2% | 2% | 2% | 2% | 2% | 2% | T3 | slow rotation, old | povrch starých těles |
| n_compounds | — | 1% | — | — | 0.5% | — | 4% | — | T3 | very dark | NH₃·H₂O, Tagish Lake |
| schreibersite_rich | 0.2% | 0.3% | 3% | — | — | — | — | — | T3 | medium+ | extra fosfor |
| ti_concentrate | — | — | — | — | — | 5% | — | — | T2 (spectra) | medium+ | extra ilmenit |
| ree_concentrate | — | — | — | — | — | 2% | 0.3% | 1% | T3 | medium+ | eucrit KREEP-like |
| pt_jackpot | — | — | 8% | — | — | — | — | — | T3 | medium+ | PGM 1000× zemská kůra |
| xenolith_diff | 0.05% | 0.1% | 0.1% | 0.1% | 0.1% | 0.1% | 0.2% | 0.1% | T3 | any | Almahata Sitta |
| active_volatiles | — | 0.1% | — | — | 0.1% | — | 0.3% | — | T2 (debris) | small + slow | 133P, vzácné v inner belt |

**Předpokládané celkové počty z 10k pole** (Σ probability × count per class):

| Tier | Expected count | Design target | Status |
|---|---|---|---|
| LEGENDARY | ~25–30 | 15–50 | ✓ |
| EXOTIC | ~280–330 | 100–300 | ✓ |
| Σ rare | ~310–360 | 200–400 | ✓ |

Jeden asteroid může mít víc rare finds (např. C-type může mít amino_acids + nucleobases + fullerene současně). Probabilities jsou nezávislé.

---

## 8. Užitečnost — výsledný odhad

Asteroid je "užitečný" pokud:
- alespoň jeden bulk resource s `game_value × concentration` nad threshold, NEBO
- alespoň jeden rare find (LEGENDARY = vždy užitečný, EXOTIC = většinou).

Per-class odhad užitečnosti (kalibrováno z composition templates + rare finds):

| Třída | Počet | Užitečných | Důvod |
|---|---|---|---|
| S | 7 000 | ~8% (560) | Fe-Ni regolith + ojedinělá PGM žíla; nutí hráče sortovat větší tělesa |
| C/Ch | 1 300 | ~25% (325) | voda (T2) + organika (T3) |
| M | 200 | ~75% (150) | PGM jackpot + magnetic record + schreibersite |
| E | 200 | ~12% (24) | enstatit chudý, ale rare finds drive value |
| P | 200 | ~18% (36) | voda + organika, méně bohatá než C |
| V | 500 | ~12% (60) | Ti (ilmenit T2) + REE |
| D | 400 | ~30% (120) | nejbohatší na organiku + N + P |
| K | 100 | ~15% (15) | mix CV/CO charakteristik |
| **Σ** | **10 000** | **~1 290 (12.9%)** | |

Hráč se postupně naučí:
- **C, Ch = předvídatelná voda** — bezpečná volba pro propellant
- **M = vzácný, ale jackpot** — když ho najdu, je to výhra
- **D = exotické nálezy, organika** — pro vědecké body
- **V = titanium + REE** — specializovaná hodnota
- **S = většinou pozadí, občas překvapení** — průměrná těžba

---

## 9. Rozhodnuté a otevřené body

### 9.1 Rozhodnuto (implementováno)

- **Schéma:** 3 ploché tabulky `asteroids` / `asteroid_tier2` / `asteroid_tier3`,
  FK přes `asteroid_id`. Composition se neukládá jako JSONB blob ani jako řádky,
  ale jako čitelný textový řetězec v `asteroid_tier3.minerals`.
- **Rare finds:** nemají vlastní tabulku — promítají se do `asteroid_tier3.special`
  a `eco`. (Pokud bude potřeba filtrovat „kde je find X", bude nutná samostatná
  tabulka — viz 9.2.)
- **Pozice / API scény:** tělesa mají v DB uloženy **oskulující orbitální elementy**
  (`a, e, i, om, w, ma, epoch_jd`). Fyzické souřadnice (x, y, z, vx, vy, vz) se
  počítají Keplerovou propagací na datum mise (viz sekce 11.6 — denní snapshoty).
  Klient si scénu stahuje z tabulky `scene_snapshots` funkcí
  `nearby_asteroids(base_id, date, radius_km, max_n)` — max 100 těles seřazených
  podle fyzické vzdálenosti v km.

### 9.2 Otevřené body

1. **Bezpečnost klíčů (vysoká priorita).**
   - Legacy `service_role` JWT klíč byl natvrdo v `fetch_flora.py` a zůstává
     v git historii — nutno revokovat / zakázat legacy klíče v Supabase.
   - `hf_route_planner_API.html` používá legacy `anon` JWT klíč; po zakázání
     legacy klíčů ho je třeba vyměnit za nový **publishable** klíč.

2. **Kalibrace na 13 786 těles.** Cíle v sekcích 3, 7, 8 byly počítané pro
   10 000. Procenta zhruba platí, absolutní počty je vhodné přepočítat.

3. **Konstanty ceny trasy v klientovi.** `SPEED`, `DV_STOP`, `DV_RETURN`,
   `fuelUsed` v route planneru počítají v procentním prostoru mapy — po přechodu
   na fyzické souřadnice (km) z Keplerovy propagace je třeba je přeladit na
   reálnou škálu delta-v a vzdáleností (herní balance).

4. **Filtrovatelnost rare finds.** Pokud má hra umět dotaz „najdi tělesa
   s nálezem X", samotný textový `special` nestačí — bude potřeba indexovaná
   tabulka nebo JSONB.

5. **Shape model URI:** pro backbone tělesa s DAMIT modelem — URL na DAMIT,
   cache OBJ v Supabase Storage, nebo nic. (Neřešeno.)

6. **Time evolution:** orbitální elementy jsou statické v DB. Fyzické polohy
   pro libovolné datum se počítají Keplerovou propagací (bez perturbací planet,
   chyba ~100 000 km pro 10 let — pro filtr fyzické blízkosti dostačující).
   Pro přesné polohy konkrétních těles lze volitelně použít JPL Horizons API.

7. **API caching:** scéna ~100 těles ≈ 500 KB JSON. Cache na edge / CDN?

8. **Nový HTML klient (další chat):** rozdělit současný monolitický
   `hf_route_planner_API.html` na oddělený design a logiku; cíl použitelnost
   na PC i mobilu.

---

*v0.1 — 2026-05-18 — výchozí návrh: resource catalog (52 položek), composition templates (8 tříd), rare finds matrix (18 nálezů), užitečnostní rozvaha*  
*v0.2 — 2026-05-20 — sekce 0 (stav implementace): nasazeno 13 786 těles, 3-tabulkové schéma, ETL + RPC; aktualizována distribuce a otevřené body*

---

## 10. Proper elements — získání dat a mapa pole

### 10.1 Zdroj a postup stažení

**AstDyS-2** (`newton.spacedys.com/astdys`) poskytuje proper elements pro >600 000 číslovaných těles.

Postup:
1. `newton.spacedys.com/astdys/index.php?pc=5` → sekce "Synthetic proper elements"
2. Stáhnout bulk soubor `allnum.syn` (~30 MB)
3. Formát: `asteroid_number  a_p  e_p  sin(i_p)  σ_a  σ_e  σ_sin(i)  ...`
4. Filtrovat dle Flora family membership → ~13 000–14 000 řádků

> ⚠ Proper elements nejsou pro všechna tělesa — unnumbered a single-opposition mají jen osculating.

### 10.2 2D mapa pole — layout v prostoru vlastních elementů

**Osy mapy:**
```
X = a_p   (vlastní velká poloosa)    rozsah Flora: 2.17 – 2.33 AU
Y = e_p   (vlastní excentricita)     rozsah Flora: 0.05 – 0.20
```

Vzdálenost dvou bodů v tomto prostoru odpovídá Zappalàově metrice — mapa je zároveň polohová i delta-V smysluplná. Flora rodina tvoří přirozený cluster; interlopeři leží mimo centrum hustoty.

**Zappalàova metrika:**
```
d = n·a × √( k₁·(Δa/a)² + k₂·(Δe)² + k₃·(Δsin i)² )
k₁=5/4, k₂=2, k₃=2,  n·a ≈ 20 km/s pro Flora region
```

### 10.3 Filtr blízkých těles

**Primární filtr — fyzická vzdálenost (Keplerova propagace):**

```
pro každé těleso v DB:
  (x, y, z) = elements_to_cartesian(a, e, i, Ω, ω, M₀, epoch_jd → target_jd)
  d_km = |r_těleso - r_base|
  → zachovat tělesa s d_km < threshold
```

Doporučený threshold pro jednu scénu (~20–50 těles): **10–50 mil. km** od base.
Výsledek: ~50 těles fyzicky dostupných v daný měsíc mise (ověřeno výpočtem pro 8 Flora).

**Zappalàova metrika** zůstává jako **atribut trasy** (cena delta-V mezi dvojicí těles),
ne jako filtr scény:

```
d_Zapp = n·a × √( k₁·(Δa/a)² + k₂·(Δe)² + k₃·(Δsin i)² )
k₁=5/4, k₂=2, k₃=2,  n·a ≈ 20 km/s pro Flora region
```

Zappalà vzdálenost ~77 m/s (např. Flora↔Petermrva) = minimální Δv pro změnu orbity
při optimálním fázování. Zobrazuje se jako barva spojnice v route planneru.

---

## 11. Herní čas, pohyb lodi a snapshoty

### 11.1 Herní den = 1 reálný měsíc mise

Jeden "herní den" odpovídá **1 měsíci reálného mise času**. Hráč v průběhu dne prozkoumá asteroidy v okolí aktuální base, večer spustí přesun na novou base.

### 11.2 Motory — fyzikální model průzkumných lodí

Pro průzkumné mise jsou relevantní tři třídy motorů. Chemický pohon je vyřazen — příliš nízký Isp pro vzdálenosti asteroid beltu.

#### Přehled

| Motor | Isp | Tah | Zrychlení | Čas na 1 km/s | Přistání | Reálnost | Cena/poruchovost |
|---|---|---|---|---|---|---|---|
| **Iontový / Hall** | 3 000 s | 0.5 N | 0.3 mm/s² | ~55 hod | ✗ | dnes (Dawn, Hayabusa2) | nízká / spolehlivý |
| **NTR** (jaderný tepelný) | 900 s | 1 000 N | 670 mm/s² | ~25 s | ✓ | testováno, ne v provozu | střední / spolehlivý |
| **VASIMR** | 3 000–30 000 s | 10–50 N | 7–33 mm/s² | 1–2 hod | hraničně | ~2030+ | vysoká / poruchový |

#### Iontový motor (Ion / Hall effect)

**Princip:** Xenon se ionizuje elektrickým výbojem, ionty se urychlují na 30–80 km/s. Tah je minimální, ale motor běží měsíce až roky.

**Reálné příklady:** Dawn (Vesta + Ceres, Δv přes 11 km/s), Hayabusa2 (Ryugu).

**Propellant a H₂O:** standardně Xenon/Krypton. Voda jako propellant možná (elektrolýza → O⁺ ionty), ale méně efektivní.

**Herní role:** Průzkumník dlouhého dosahu — mnoho průletů, minimální zastávky.
```
Δv budget:   8–12 km/s / měsíc
Dosah:       5–8 mil. km / měsíc
Zastávky:    0–1 (brzdění trvá dny)
Průlety:     10–30 / měsíc
```

**Vzdělávací obsah pro hráče:**
> *"Iontový motor je jako větrný vůz — neuvěřitelně efektivní, ale nedokáže prudce zabočit. Dawn spotřebovala méně Xenonu než váha průměrného člověka a přesto změnila orbitu o 11 km/s. Nevýhoda: pokud chceš zastavit u asteroidu, začni brzdit týden předem."*

---

#### NTR — Jaderný tepelný motor (Nuclear Thermal Rocket)

**Princip:** Jaderný reaktor zahřeje kapalný vodík (nebo vodu) na 2 500–3 000 K. Plyn se expanduje tryskou — tah srovnatelný s chemickým motorem, Isp 2–3× lepší.

**Reálné příklady:**
- NERVA (NASA, 1960–1972) — 20 funkčních testů, Isp 825 s, tah 33 000 N. Připraveno k letu na Mars, program zrušen Nixonem.
- RD-0410 (SSSR) — paralelní vývoj, podobné parametry.
- DRACO (NASA/DARPA, 2025+) — aktuální program, plánovaný letový test 2027.

**Propellant a H₂O:** NTR může použít **vodu přímo** — reaktor ji přemění na přehřátou páru. Isp klesne na ~190 s (místo 900 s s H₂), ale voda je hustá, snadno skladovatelná a dostupná in-situ z C-typů. Klíčové herní propojení: **H₂O těžená z asteroidů = palivo NTR**.

**Herní role:** Všestranný průzkumník — může zastavit, může přistát, rozumný dosah.
```
Δv budget:   4–6 km/s / měsíc
Dosah:       3–4 mil. km / měsíc
Zastávky:    2–5 / měsíc
Průlety:     5–15 / měsíc
Přistání:    ✓ (asteroidy s únikovou rychlostí < 3 m/s)
```

**Vzdělávací obsah pro hráče:**
> *"NERVA byl připraven k letu na Mars v roce 1972 — dvakrát silnější a třikrát úspornější než chemické motory. Program zrušil Nixon, ne kvůli technice, ale kvůli rozpočtu. NTR může spalovat vodu přímo — nižší efektivita, ale žádný transport Xenonu ze Země. C-typ interloper v S-poli není jen vědecký nález — je to čerpací stanice."*

---

#### VASIMR — Variable Specific Impulse Magnetoplasma Rocket

**Princip:** Plyn (Argon nebo H₂) se ionizuje a zahřívá radiofrekvenčními vlnami na miliony kelvinů. Plazma udržována magnetickým polem, urychlována magnetickou tryskou. **Isp je variabilní** — pilot přepíná mezi vysokým tahem (nízký Isp, manévry) a vysokou účinností (vysoký Isp, dosah).

**Reálné příklady:**
- Ad Astra Rocket Company (Franklin Chang-Díaz, astronaut, 7 letů raketoplánem) — VF-200 testován na Zemi, 200 kW, 5.7 N.
- Žádný letový exemplář dosud. Plánované testování na ISS opakovaně odloženo.

**Omezení:** Vyžaduje 200 kW+ energie — za orbitou Marsu nutný jaderný reaktor. Komplexní systém = vyšší poruchovost (herní mechanika).

**Herní role:** Prémiový flexibilní motor — hráč přepíná režimy podle situace.
```
Δv budget:   6–10 km/s / měsíc (závisí na režimu)
Dosah:       4–7 mil. km / měsíc
Zastávky:    1–3 / měsíc (high-thrust režim)
Průlety:     15–25 / měsíc (high-Isp režim)
Poruchovost: herní mechanika — riziko výpadku, nutná údržba
```

**Vzdělávací obsah pro hráče:**
> *"VASIMR je jako auto s převodovkou — první rychlost dá tah pro manévry, šestá rychlost šetří palivo na dálnici. Vynalezl ho Franklin Chang-Díaz, který strávil 20 let vývojem poté, co sedmkrát letěl do vesmíru. Zatím nikdy neletěl v provozu — fyzika funguje, ale systém je složitý. Ve hře to znamená: výkon za cenu rizika výpadku."*

### 11.3 Relativní rychlostní vektor — směr rozhoduje

Pro každé těleso v okolí base se počítá relativní pohyb:

```python
dr        = r_target - r_base
dv        = v_target - v_base
dr_unit   = dr / |dr|
v_radial  = dot(dv, dr_unit)         # + = vzdaluje, - = přibližuje
v_tang    = sqrt(|dv|² - v_radial²)
dv_eff    = |v_tang| + max(0, v_radial)   # efektivní Δv pro rendezvous
```

| Situace | v_radial | Herní dopad |
|---|---|---|
| Těleso se přibližuje | < 0 | Levné — přiletí samo |
| Těleso se vzdaluje | > 0 | Drahé — musíš dohnat |
| Těleso letí kolmo | ≈ 0 | Boční manévr — středně drahé |

### 11.4 2D projekce — inklinace

Flora region: i < 9° → Z složka max 15 % chyba při X-Y projekci. PoC ignoruje Z; full game: Z jako třetí dimenze pohybu.

### 11.5 Vizuální vektory v mapě

```
● Zelená šipka   dv_eff < 80 m/s     "přibližující / levné"
● Žlutá šipka    80–300 m/s          "střední"
● Červená šipka  > 300 m/s           "rychlé, drahé"

Směr: projekce dv do 2D mapy
Délka: log(dv_eff)
```

### 11.6 Snapshoty a pohyb base

**Denní snapshot** (1× za 24 hodin):
```
offline job → Keplerova propagace 150k elementů na dnešní datum
→ pro každou aktivní base: top 100 nejbližších těles + [x,y,z,vx,vy,vz]
→ uložit do scene_snapshots (base_id, date, asteroid_data JSONB)
```

**Škálování:** 1 000 bases × 5 kB × 365 dní = ~1.8 GB/rok.

---

*v0.1 — 2026-05-18 — výchozí návrh*
*v0.2 — 2026-05-20 — stav implementace: 13 786 těles, 3-tabulkové schéma*
*v0.3 — 2026-05-25 — sekce 10 (proper elements, Zappalà mapa), sekce 11 (herní čas, motory Ion/NTR/VASIMR, relativní vektory, snapshoty)*
