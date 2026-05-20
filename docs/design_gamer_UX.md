# HighFrontier — Design & UX
## Dokument pro herní mechaniky a player experience

> Stav: Draft v0.2 · Scope: Scénář 1 (Survey) + Scénář 2 (Mining)  
> Tento dokument navazuje na `highfrontier_poc_design_v03.md`  
> Kapitola 1: vědecké předpoklady → základ pro brainstorm herních mechanik  
> Kapitola 2: Route Planner — herní mechanika průzkumné mise

---

## 1. Vědecké předpoklady

### 1.1 Rodina Flora — základní parametry

**Orbitální region:**
- Velká poloosa: a = 2.17–2.33 AU
- Excentricita: e = 0.05–0.20
- Sklon: i = 1.5–8.0°

**Datová základna (JPL SBDB):**
- 71 183 číslovaných těles v orbitálním regionu (≈ D > 1 km)
- Celkový odhadovaný počet těles > 150 m: ~8 milionů
- Celkový odhadovaný počet těles > 50 m: ~127 milionů
- Spektrální složení: ~70 % S-typ, ~30 % interlopeři (zdroj L-chondritů)

**Datové pokrytí katalogizovaných těles:**
- Měřené albedo (WISE/NEOWISE): přibližně 30–40 % těles
- Spektrální třída: přibližně 10–15 % těles
- Rotační perioda: méně než 5 % těles
- Průměr (změřený): méně než 30 % těles; zbytek odhadnutý z H magnitudy

---

### 1.2 Prostorová hustota — asteroid field je prázdný vesmír

Toto je zásadní vědecký fakt s přímým dopadem na design.

**Střední vzdálenosti mezi sousedními tělesy v Flora regionu:**

| Velikost tělesa | Střední vzdálenost mezi sousedy |
|---|---|
| D > 1 km | ~3 000 000 km (8× vzdálenost Země–Měsíc) |
| D > 150 m | ~618 000 km |
| D > 50 m | ~247 000 km |
| D > 10 m | ~65 000 km |

**Ve válci 1/1000 AU (průměr 150 000 km, výška 150 000 km)** se statisticky nachází:
- D > 150 m: méně než 1 těleso
- D > 10 m: přibližně 10 těles

**Závěr:** Jakákoliv herní scéna s vizuálně hustým polem asteroidů je záměrná komprese reality (faktor 100–1 000×). Hra tuto kompresi musí přiznat nebo vědomě ignorovat.

---

### 1.3 Velikostní kategorie a fyzikální vlastnosti

Velikost tělesa určuje jeho fyzikální charakter, způsob těžby i vizuální podobu.

| Kategorie | Průměr | Struktura | Úniková rychlost | Tvar |
|---|---|---|---|---|
| Major | > 60 km | kompaktní, gravitačně stabilní | 40–80 m/s | zaoblený, potato |
| Large | 20–60 km | rubble pile nebo kompaktní | 10–40 m/s | zaoblený, DAMIT konvexní |
| Medium | 5–20 km | rubble pile (typický) | 3–10 m/s | zaoblený s povrchovými prvky |
| Small | 1–5 km | přechodový (rubble pile → monolitický) | < 3 m/s | přechodový tvar |
| Tiny | 150 m–1 km | monolitický (pevnost > gravitace) | < 1 m/s | **hranaté, klínovité** |
| Boulder | < 150 m | monolitický fragment | cm/s | **výrazně hranaté** |

**Klíčová hranice na ~150 m:** pod touto velikostí dominuje pevnost materiálu nad gravitací → tělesa jsou monolitická a hranaté fragmenty. Nad touto hranicí dominuje gravitace → tělesa jsou rubble pile s zaobleným tvarem.

---

### 1.4 Zdroje 3D tvarů pro procedurální systém

**DAMIT** (Karlova Universita Praha, `damit.cuni.cz`):
- Přes 5 700 tvarových modelů odvozených z lightcurve inversion
- Formát: Wavefront OBJ, watertight, two-manifold
- Omezení: výhradně konvexní tvary
- Vhodné pro: Medium a Large kategorie (rubble pile)

**ASU CAS Praha** (`shapemodels.asu.cas.cz`):
- 868 modelů z X-ray CT skenů fragmentů hypervelocity impaktu
- Formát: OBJ, rozlišení ~50 μm; výrazně hranaté, klínovité
- Vhodné pro: Tiny a Boulder kategorie (< 150 m)
- Licence: volné pro nekomerční použití (kontakt: david.capek@asu.cas.cz)

**NASA Spacecraft modely** (Eros, Itokawa, Ryugu, Bennu, Vesta, Psyche):
- Nekonvexní, dramatické, hi-res, glTF/OBJ, veřejná doména
- Vhodné pro: ikonické "boss" asteroidy ve scéně

**JPL Radar modely** (Kleopatra, Geographos, Psyche, Betulia):
- Nekonvexní tvary ze zemských radarových pozorování

---

### 1.5 Interlopeři ve Flora poli

**Podíl:** ~30 % těles v oblasti jsou interlopeři (Flora je dynamicky otevřená rodina).

| Těleso | Typ | Albedo | Charakter |
|---|---|---|---|
| 317 Roxane | E | 0.926 | nejjasnější těleso v poli |
| 72 Feronia | TDG | 0.083 | tmavé, neobvyklá taxonomie |
| 336 Lacadiera | D | 0.054 | nejtmavší v poli |
| 2468 Repin | V | ~0.35 | bazaltické, tmavě červené |
| 2912 Lapalma | V | ~0.35 | bazaltické |
| 2778 Tangshan | Cb | 0.044 | tmavé C s hydroxyl absorpcí |

**Klíčová asymetrie:** 59 ze 100 vybraných těles pro PoC scénu nemá žádné spektrální určení. Hráč neví, zda jde o S-typ nebo interloper, dokud neskení.

---

### 1.6 Binární a vícenásobné systémy

**Prevalence:** ~2 % těles v hlavním pásu má satelit → Flora rodina obsahuje odhadem ~275 binárních systémů.

**3749 Balam** (D = 4.1 km) — trinary systém; nejvolněji vázaný binární systém v celém hlavním pásu.

**3841 Dicicco** (D ≈ 5.5 km) — synchronní binární; měsíc na orbitě a = 12 km.

**8 Flora** (D = 136 km) — Hillova sféra 27 709 km; žádný potvrzený satelit.

---

### 1.7 Přirozené koncentrace malých kamenů

**A) Povrch rubble pile asteroidu** — Ryugu: ~5 balvanů > 2 m na km²; Bennu: >100 balvanů > 1 m na km² v hustých oblastech.

**B) Ejecta field čerstvě impaktovaného asteroidu** — Dimorphos: 4 734 balvanů > 5 m; detekce čerstvým kráterem v albedo mapě.

**C) Equatoriální debris u YORP-spinning tělesa** — rotační perioda < 2–3 hod → aktivní shazování materiálu z rovníku; detekce anomálně krátkou periodou + top-shaped tvarem.

---

### 1.8 Ekonomická logika těžaře

**Delta-v hierarchie (od nejlevnějšího):**
1. Povrchový materiál tělesa, na kterém již stojím — nulové delta-v
2. Sekundární těleso v binárním systému — mikroskopické delta-v
3. Těleso ve stejné rodině — nízké delta-v
4. Přechod do jiné rodiny — vysoké delta-v

**Hodnotová hierarchie:** PGM (M, S-typ) > H₂O jako palivo (C, Ch) > Fe-Ni (M, S) > He-3 (všechna tělesa)

**Sweet spot pro těžbu:** 5–15 km — dost materiálu, úniková rychlost < 10 m/s, typicky rubble pile.

---

## 2. Route Planner — herní mechanika průzkumné mise

### 2.1 Herní koncept

Hráč plánuje trasu průzkumné sondy polem asteroidů před startem mise. Jde o **variantu Orienteering Problemu** (ne čistý TSP): hráč nevytíví všechna tělesa, ale vybírá podmnožinu a jejich pořadí tak, aby maximalizoval vědeckou hodnotu katalogu při omezených zdrojích.

**Dvě fáze:**
1. **Plánování (Route Planner)** — hráč volí pořadí těles a typ průletu; simulátor ukazuje spotřebu H₂O a cestovní čas
2. **Mise (za letu)** — u každého tělesa se hráč rozhodne stop/flyby podle toho, co vidí (rotace, hustota kamenů, povrchové inkluze)

### 2.2 Fyzikální model

#### Delta-v manévru

Správný vzorec — vektorový rozdíl normalizovaných rychlostí:

```
Δv = |v_výstupní − v_vstupní|   (oba vektory délky 1 = cruise speed)
   = 2 · sin(θ/2)               kde θ = úhel zahnutí
   ∈ ⟨0; 2⟩
```

Implementace v JS (bez trigonometrie):
```javascript
function normalize(a, b) {
  const len = Math.hypot(b.x-a.x, b.y-a.y);
  return {x:(b.x-a.x)/len, y:(b.y-a.y)/len};
}
function dvFlyby(prev, curr, next) {
  const v1 = normalize(prev, curr);
  const v2 = normalize(curr, next);
  return Math.hypot(v2.x-v1.x, v2.y-v1.y);  // = 2·sin(θ/2) ∈ [0,2]
}
```

#### Zastávka vs. průlet

| Manévr | Δv | Poznámka |
|---|---|---|
| Průlet rovně (0°) | 0 | žádná korekce |
| Průlet 90° | √2 ≈ 1.41 | typická odbočka |
| Průlet U-turn (180°) | 2 | maximální korekce |
| Zastávka (stop) | 2 | = U-turn; decelerate + re-accelerate |
| Návrat na BASE | 1 | fixní; počítá se jako poslední manévr |

**Zastávka = U-turn** v ceně Δv — fyzikálně správně (`DV_STOP = 2.0`). Výhoda zastávky: libovolný směr odjezdu.

#### Tsiolkovského rovnice

Palivo tvoří **50 % celkové hmotnosti** při plné nádrži (`M_dry = H₂O_budget`).

```
fuel_used = (M_dry + W_aktuální) · (1 − exp(−Δv / Ve))
```

kde `Ve` = exhaust velocity (ladit podle vybavení sondy; default Ve = 21).

Výsledek: plná nádrž = manévr stojí ~1.4× víc než prázdná nádrž. Každý další manévr je levnější — **pořadí manévrů je jedno** (závisí pouze na celkovém Δv), ale Tsiolkovský vytváří nelineární závislost na zbývající vodě.

**Výpočet probíhá sekvenčně** v pořadí waypointů; návrat na BASE se počítá jako poslední (nejlevnější).

#### Cestovní čas

Cestovní čas závisí na celkové délce trasy; **nezávisí na spotřebě H₂O**. Je druhým optimalizačním parametrem — kratší trasa = více času pro průzkum u těles = lepší data = vyšší skóre.

### 2.3 Herní dilema (TSP varianta)

Hráč vidí ~12 těles, palivo vystačí na ~5–6 waypointů (mix zastávek a průletů). Kombinací pořadí je tisíce — skutečná výzva.

**Klíčová rozhodnutí:**
- Těleso "cestou" = levný průlet nebo zastávka bez přirážky za zahnutí
- Ostrý zahyb = zbytečná spotřeba H₂O
- C-typ interloper = priorita jako zdroj paliva (viz kap. 1.8)
- Zastávka u zajímavého tělesa = lepší data, ale stojí jako U-turn

**Čas H₂O jako palivový volič:** Při plánování si hráč nastaví množství vody (více = větší dosah, ale těžší loď = dražší každý manévr — Tsiolkovsky). V plné hře: volitelná rychlost letu a vybavení (Ve motoru) jako mise-level parametry.

### 2.4 UI — Route Planner (mobilní, flat mapa)

**Header (jeden řádek):**
- H₂O bar: `■ manévry` + `░ rezerva na zastávky` + číselná hodnota zbývající vody
- Cestovní čas trasy v minutách (zelená = krátká, červená = dlouhá)
- `?` tlačítko → legenda overlay

**Mapa:**
- Scrollovatelná horizontálně (~760 px, přibližně čtverec na telefonu)
- Asteroidy jako barevné kruhy (barva = spektrální třída)
- 1. klepnutí = zastávka (zelená, plný kruh kolem); 2. klepnutí = průlet (žlutá, přerušovaná); 3. klepnutí = vyřadit
- Číslo pořadí na každém waypointu; hover = tooltip `Δv / H₂O spotřeba`
- Trasa: plné modré čáry s šipkami; koláček u průletu (výseč) = vizuál Δv manévru (zelená/žlutá/červená)
- Zastávka = plný zelený kruh místo koláčku
- Návrat na BASE jako světle modrá čára bez šipky

**Legenda (overlay):**
- Spektrální třídy + jejich vědecký smysl
- Vysvětlení koláčků a stop/flyby

### 2.5 Otevřená témata — Route Planner

| # | Téma | Priorita |
|---|---|---|
| RP-1 | INFO panel u objektu — basic (flyby) a detailní (stop) data | **příští chat** |
| RP-2 | Fog of war — spektrální třída viditelná předem vs. až po skenu | střední |
| RP-3 | Cestovní rychlost jako volitelný parametr (více rychlosti = více H₂O/min) | střední |
| RP-4 | Ve motoru jako upgrade parametr | nízká (plná hra) |
| RP-5 | Gravitační assist od velkých těles (8 Flora) jako skrytá zkratka | nízká |
| RP-6 | Návrat H₂O z C-typ zastávky (in-situ těžba vody) | nízká |

---

## 3. UX a vizuální jazyk — připravuje se

---

## 4. Scény a level design — připravuje se

---

*v0.1 — 2026-05-13 — Kapitola 1: Vědecké předpoklady*  
*v0.2 — 2026-05-14 — Kapitola 2: Route Planner (fyzikální model, herní dilema, UI popis)*
