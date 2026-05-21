# HighFrontier — Design dokument aplikace

> Stav: v1 (draft) · Umístění: `app/` · Cíl: nová verze klientské aplikace
> Navazuje na `docs/highfrontier_poc_design_v04.md`, `docs/db_design.md`,
> `docs/design_gamer_UX.md`

---

## 0. Kontext a vztah k existujícím dokumentům

Projekt HighFrontier dnes stojí na třech návrhových dokumentech v `docs/` a jednom
funkčním prototypu klienta v rootu repozitáře (`hf_route_planner_API.html`).
Prototyp ověřil dvě klíčové věci: mechaniku **Route Planneru** (plánování trasy
průzkumné mise) a **napojení na živá data v Supabase** (13 786 těles rodiny Flora).
Svůj účel splnil.

Pro další vývoj ale prototyp nestačí:

- Je to jeden HTML soubor (~1000 řádků) bez oddělení designu, logiky a dat.
- Fyzikální model počítá v **procentním prostoru mapy** místo reálných jednotek
  (viz `db_design.md` §9.2 bod 3, `design_gamer_UX.md` §2.6).
- Chybí struktura pro multiplayer, vzdělávací vrstvu a budoucí port na Godot.

Tento dokument zakládá **novou verzi aplikace**. Adresář `app/` bude postupně
hostit celou novou klientskou aplikaci; `app/DESIGN.md` je její technický návrh.

**Mapa dokumentů projektu:**

| Dokument | Co řeší |
|---|---|
| `docs/highfrontier_poc_design_v04.md` | Herní koncept, core loop, vizuální systém asteroidů, resource taxonomy, Tier model |
| `docs/db_design.md` | Obsah a schéma databáze, composition templates, rare finds, stav Supabase |
| `docs/design_gamer_UX.md` | Vědecké předpoklady, mechanika Route Planneru, fyzikální model, UI popis |
| **`app/DESIGN.md`** (tento) | **Technický návrh klientské aplikace: architektura, tech stack, struktura kódu, multiplayer, roadmapa** |

`docs/*` zůstávají zdrojem pravdy pro **vědu a herní design**. `app/DESIGN.md` je
zdrojem pravdy pro **technickou realizaci aplikace**. Kde se tento dokument dotýká
herního obsahu, odkazuje na `docs/*` a nedubluje je.

---

## 1. Vize a rozsah

HighFrontier je **multiplayerová hard-sci-fi hra o průzkumu asteroidů**. Hráč
plánuje a provádí průzkumné mise polem reálných těles rodiny Flora, skenuje je
spektrometrem a buduje katalog (viz core loop v `highfrontier_poc_design_v04.md` §2).
Data jsou ukotvena v reálném vědeckém katalogu (JPL/WISE) — to, co věda nezná,
je herní mechanika (Tier model, `db_design.md` §1).

**Cílové platformy:**

- **PC-first** — primární cíl, plná funkcionalita včetně vzdělávací vrstvy.
- **Mobil** — sekundární cíl; aplikace má být použitelná na dotykovém zařízení,
  ale rozsah obsahu (zejména vzdělávací texty) se na PC a mobilu může lišit.
- **Godot (výhled)** — částečný nebo úplný port na Godot 4 jako nativní/herně
  bohatší klient. Architektura tomu musí jít vstříc (viz §3).

**V rozsahu této verze aplikace:**

- Route Planner přenesený do nové, modulární struktury.
- Reálný fyzikální model letu (hybrid — viz §5).
- Přímé odkazy na záznamy v JPL databázi (§6).
- Vzdělávací vrstva (§7).
- Efemerní multiplayer presence (§4).

**Mimo rozsah této verze (popsáno jako směr, neimplementuje se):**

- Persistentní sdílení katalogů mezi hráči (§4).
- Konfigurace lodi a filtrování mapy podle charakteristik (§9).
- Plná 3D scéna průzkumu / přechod na Godot (§3).
- Scénář 2 (Mining) a ekonomický systém.

---

## 2. Produktové principy

1. **Iterativní vývoj.** Aplikace se staví v malých ověřitelných krocích. Každý
   krok produkuje něco spustitelného. Herní logika (zejména balanc fyziky) se
   ladí průběžně, ne najednou na konci.
2. **Vědecky ukotvené.** Veškerá data pocházejí z reálného JPL/WISE katalogu
   (`db_design.md` §2). Nejistota v datech je feature, ne bug.
3. **Vzdělávací.** Hra zároveň učí. Každý termín, zkratka a veličina jsou
   vysvětlitelné přímo v aplikaci (§7).
4. **Oddělení vrstev.** Design, herní logika a datový přístup jsou oddělené od
   začátku — náprava monolitu prototypu (§3).
5. **Připraveno na multiplayer i Godot, ale ne přeinženýrované.** Architektura
   nechává švy pro budoucí vrstvy; neimplementuje je předčasně.

---

## 3. Architektura aplikace

### 3.1 Plánovaná adresářová struktura

```
app/
├── DESIGN.md            — tento dokument
├── index.html           — vstupní bod
├── ui/                  — DESIGN: komponenty, layouty, styly, vykreslení mapy
├── game/                — HERNÍ LOGIKA: frameworkově nezávislé jádro (čistý TS)
│   ├── physics/          — model letu, delta-v, Tsiolkovsky (viz §5)
│   ├── routeplanner/     — plánování trasy, waypointy, scoring
│   └── model/            — herní datové typy (Asteroid, Scene, Catalog…)
├── data/                — DATA: přístup k Supabase, RPC volání, mapování DTO
├── net/                 — MULTIPLAYER: abstrakce presence vrstvy (viz §4)
├── education/           — vzdělávací vrstva: glosář, vysvětlivky, externí odkazy (§7)
└── assets/              — statické zdroje
```

Klíčový princip: **`game/` neimportuje nic z `ui/` ani z konkrétního UI
frameworku.** Je to čistý TypeScript. To je předpoklad pro:
- testovatelnost herní logiky bez DOM,
- výměnu UI vrstvy,
- port na Godot (logiku lze přepsat 1:1, protože nemá webové závislosti).

### 3.2 Tech stack — kritéria a doporučení

**Kritéria volby:**

| Kritérium | Proč |
|---|---|
| PC-first, použitelné i na mobilu | viz §1 |
| Robustní pro velkou, dlouho budovanou aplikaci | iterativní vývoj přes mnoho kroků |
| Dobré pro content-heavy UI | vzdělávací vrstva je textově bohatá |
| Canvas / vykreslovací vrstva | mapa asteroidů se kreslí pixel/vektorově |
| Snadný build a deploy | rychlá iterace |
| Rozumná cesta ke Godotu | minimalizovat ztráty při budoucím portu |
| Typová bezpečnost | velká codebase, méně regresí |

**Doporučení:**

- **Build:** Vite — rychlý dev server, minimální konfigurace, standard.
- **Jazyk:** TypeScript — typová bezpečnost je u takto rostoucí codebase nutnost,
  ne luxus.
- **UI framework:** **Svelte** jako primární návrh. Důvody: malý objem boilerplate
  (rychlá iterace), kompilace do efektivního kódu (dobré i na mobilu), čistý
  oddělený CSS scope na komponentu. **React** je plně akceptovatelná alternativa
  — větší ekosystém a více vývojářů ho zná; pokud se ukáže, že tým/AI nástroje
  pracují lépe s Reactem, je to legitimní volba. Rozhodnutí mezi nimi se uzavře
  po prvním prototypovém kroku (§12).
- **Herní jádro (`game/`):** žádný framework — čistý TypeScript. To je úmyslné
  oddělení, aby výměna UI vrstvy ani port na Godot nezasáhly logiku.
- **Vykreslení mapy:** HTML Canvas 2D pro start (prototyp ho už používá);
  WebGL/PixiJS jako možné budoucí rozšíření, pokud bude potřeba výkon.
- **Backend:** beze změny — Supabase (PostgreSQL + RPC), tak jak je popsáno
  v `db_design.md`.

### 3.3 Oddělení design / logika / data

Náprava monolitu prototypu (`db_design.md` §9.2 bod 8). Tok dat:

```
Supabase  ──RPC──▶  data/   ──DTO──▶  game/   ──stav──▶  ui/   ──▶  obrazovka
                                        ▲                  │
                                        └──── akce hráče ───┘
```

- `data/` zná Supabase a SQL, nezná herní pravidla.
- `game/` zná herní pravidla, nezná Supabase ani DOM.
- `ui/` zná zobrazení a vstup, nezná SQL ani fyzikální vzorce.

### 3.4 Cesta ke Godotu

| Vrstva | Osud při portu na Godot |
|---|---|
| `game/` (logika, fyzika, model) | **portuje se** — přepis čistého TS do GDScript/C# je přímočarý |
| `data/` (Supabase přístup) | **portuje se** — Supabase má klientské knihovny i mimo web |
| `net/` (multiplayer abstrakce) | **portuje se** — abstrakce zůstává, mění se implementace kanálu |
| `ui/` (web komponenty, Canvas) | **zahazuje se** — nahradí Godot scény a uzly |

Proto je hranice `game/` ↔ `ui/` tvrdá. Čím čistší je `game/`, tím levnější je
port. Detailní Godot scéna (3D průzkum) je popsána v `highfrontier_poc_design_v04.md`
§13 a je mimo rozsah této webové aplikace.

---

## 4. Multiplayer architektura

### 4.1 Co multiplayer v této verzi je

**Efemerní presence.** Hráči se navzájem vidí, pokud se **záměrně potkají** ve
stejné sdílené session a stejném regionu mapy. Žádný persistentní stav, žádné
ukládání cizích hráčů, žádný účet potřebný pro solo hru. Když hráč session opustí,
ostatním zmizí.

Solo hra je výchozí a plně funkční **bez** multiplayeru. Presence je tenká vrstva
navíc, ne základ.

### 4.2 Realizace

- **Kanál:** Supabase Realtime — Presence a Broadcast kanály. Presence drží
  seznam aktuálně připojených hráčů v kanálu; Broadcast přenáší jejich polohu
  na mapě.
- **Granularita:** kanál odpovídá sdílené session + regionu. Hráči ve stejném
  regionu se v něm potkají; jinak se nevidí.
- **Stav:** vysílá se jen efemerní poloha/identita. Nic se neukládá do DB.

### 4.3 Architektonické švy

Modul `net/` je **abstrakce**. Definuje rozhraní typu „připoj se do session,
vysílej moji polohu, odebírej polohy ostatních". Implementace (Supabase Realtime)
je za tímto rozhraním. Důsledky:

- `game/` a `ui/` o Supabase Realtime nevědí, mluví jen s `net/`.
- Solo hra `net/` vůbec nevolá.
- Budoucí port na Godot vymění implementaci `net/`, ne rozhraní.

### 4.4 Odložené — persistentní vrstva

Mimo rozsah této verze, ale architektura na to nechává místo: **„dávkové"
sdílení výsledků průzkumu** — hráč po misi nahraje svůj katalog, jiní hráči si
ho mohou stáhnout/koupit (vazba na scénář „těžaři" v `highfrontier_poc_design_v04.md`).
To vyžaduje autentizaci a persistentní tabulky. Neimplementuje se nyní; až bude
relevantní, vznikne samostatný návrh. `net/` rozhraní se rozšíří, nezahodí.

---

## 5. Model letu — hybrid

Toto je jádro nové verze. Cílem je zážitek na pomezí deskové hry **High Frontier 4**
(diskrétní plánování, čitelná abstrakce) a **Kerbal Space Program** (poctivá
fyzika, hráč rozumí proč).

### 5.1 Princip hybridu

| Vrstva | Co dělá |
|---|---|
| **Pod kapotou — reálné jednotky** | Veškeré výpočty v SI: souřadnice v rychlostním prostoru (m/s), delta-v v m/s, Tsiolkovského rovnice, tah a hmotnost lodi |
| **Plánovací UI — diskrétní kroky** | Hráč skládá trasu z waypointů, volí stop/flyby, vidí čitelné Δv koláčky — jako desková hra, ne jako spojitý simulátor |
| **Vzdělávací vrstva — skutečná čísla** | Vedle herní abstrakce se zobrazí reálné hodnoty (Δv v m/s, spotřeba paliva v kg, čas) — hráč vidí, co abstrakce znamená |

Hráč tedy plánuje **diskrétně a čitelně**, ale počítá se **reálně**, a kdykoli
si může nechat ukázat skutečná čísla.

### 5.2 Reálné jednotky pod kapotou

Datový základ už existuje: tělesa mají souřadnice v proper-element rychlostním
prostoru (`x_pos`, `y_pos`, `z_pos` v m/s — `db_design.md` §9.1, ETL
`pipeline/transform_to_db.py`). Model letu na tom staví:

- **Delta-v manévru** — vektorový rozdíl rychlostí, viz `design_gamer_UX.md` §2.2.
  Vzorec `Δv = |v_out − v_in|` platí; nově se počítá ve **skutečných m/s**, ne
  v normalizovaných jednotkách délky 1.
- **Tsiolkovského rovnice** — `fuel_used = (M_dry + W) · (1 − exp(−Δv / Ve))`.
  `Ve` (výtoková rychlost motoru) v m/s — reálná hodnota podle typu motoru, ne
  herní konstanta 21.
- **Tah a hmotnost** — loď má hmotnost, motor tah; ovlivňují, co je v rámci
  rozpočtu delta-v dosažitelné.

### 5.3 Diskrétní plánovací UI

Zachovat osvědčené z prototypu (`design_gamer_UX.md` §2.4):

- Waypointy na mapě, pořadové číslo, klepnutí přepíná stop → flyby → vyřadit.
- Δv koláček (výseč) u průletu vizualizuje úhel zahnutí; barva zelená/žlutá/červená.
- Zastávka jako plný kruh.
- `dvFlyby` (úhel zahnutí, `2·sin(θ/2)`) je **měřítkově invariantní** a platí
  beze změny — viz `design_gamer_UX.md` §2.6.

### 5.4 Náprava prototypu — přechod na reálnou škálu

Konkrétní technický dluh k odstranění (`db_design.md` §9.2 bod 3,
`design_gamer_UX.md` §2.6):

| Konstanta / výpočet | Stav v prototypu | Cílový stav |
|---|---|---|
| `SPEED` | procentní prostor mapy | reálná cestovní rychlost (m/s) |
| `DV_STOP`, `DV_RETURN` | herní konstanty v % prostoru | odvozené z reálného delta-v v m/s |
| `Ve` | default 21 (bezrozměrné) | výtoková rychlost motoru v m/s |
| délka trasy, čas | % prostoru | reálná škála |
| `dvFlyby` | OK (invariantní) | beze změny |

Přeladění je zároveň herní balanc — je to iterační krok, ne jednorázový výpočet.

### 5.5 Mapování inspirace

Dokument bude udržovat tabulku „HF4 koncept ↔ KSP koncept ↔ naše řešení", aby
bylo jasné, odkud která mechanika pochází a jak je adaptována. Výchozí body:

| HF4 (desková hra) | KSP (simulátor) | HighFrontier |
|---|---|---|
| Pohyb po diskrétních polích rychlostní mapy | Spojitá orbitální mechanika | Diskrétní waypointy v reálném rychlostním prostoru |
| „Burn" karty / žetony | Δv budget, Tsiolkovsky | Reálný Tsiolkovsky pod diskrétním plánováním |
| Hráč čte rychlostní mapu jako herní plán | Hráč čte navball a manévr nódy | Plánovací mapa + vzdálenostní vrstva s reálnými čísly |

### 5.6 Vzdělávací vrstva v modelu letu

Každý prvek plánu má „co to znamená" zobrazení: Δv koláček → kolik m/s a kolik kg
paliva; cestovní čas → reálné jednotky; rozpočet delta-v → proč Tsiolkovsky dělá
plnou nádrž dražší. Vazba na §7.

---

## 6. Přímá vazba na JPL databázi

Každé těleso ve scéně má v INFO panelu **klikatelný odkaz na svůj záznam v JPL
Small-Body Database**. Hráč tak může kdykoli ověřit, že jde o reálné těleso, a
prozkoumat oficiální data.

- **Cíl odkazu:** JPL SBDB lookup pro konkrétní těleso, identifikované jeho
  označením / `source_id` (orbitální elementy v `db_design.md` §2 jsou označené
  jako REAL — provazba na reálný katalog existuje).
- **Umístění v UI:** INFO panel tělesa (`design_gamer_UX.md` §2.5, téma RP-1),
  jako odkaz „zobrazit v JPL SBDB".
- **Rozsah:** malá, ale brzká změna — patří mezi první kroky po přenosu Route
  Planneru (§11).

Konkrétní formát URL se ověří proti aktuálnímu rozhraní JPL SBDB při implementaci
a zapíše se do `data/` vrstvy.

---

## 7. Vzdělávací vrstva

PC verze aplikace vysvětluje hráči **všechny** termíny, zkratky, spektrální třídy
a fyzikální veličiny. Cílem je, aby hra zároveň učila reálnou planetární vědu a
astronautiku.

**Mechanismy:**

- **Glosář** — centrální seznam pojmů (spektrální třídy C/S/M/V/E/D/P/K/U,
  delta-v, albedo, Tsiolkovsky, rubble pile, Tier model…).
- **Tooltip / hover vysvětlivky** — termín v UI je propojený s glosářem; najetí
  nebo klepnutí ukáže krátké vysvětlení.
- **„Co to znamená" panely** — u herních hodnot (Δv koláček, hustota, nejistota
  skenu) volitelný panel s reálným významem (vazba na §5.6).
- **Externí odkazy** — JPL SBDB (§6), WISE/NEOWISE, DAMIT, Wikipedia. Odkazy se
  generují jen pro účely vzdělávání hráče (povolené použití URL).

**Zdroj textů:** `db_design.md` a `highfrontier_poc_design_v04.md` už nesou
vědecké poznámky (provenance dat, composition templates, resource taxonomy,
vědecká motivace parametrů). Vzdělávací vrstva je z velké části kurátorství
těchto poznámek do hráči srozumitelné podoby.

**Modul:** `app/education/` — glosář a vysvětlivky jako data, oddělené od `ui/`.

**PC vs. mobil:** plný rozsah vysvětlivek cílí na PC; na mobilu se rozsah může
zúžit kvůli prostoru (otevřený bod, §12).

---

## 8. AI-asistovaný design workflow

Vývoj aplikace využívá AI nástroje záměrně a soustavně. Je důležité oddělit dvě
různé věci, které mají různé technické nároky.

### 8.1 Návrh a kód UI — Claude

Pro návrh a iteraci web a mobilního rozhraní (výhledově i podkladů pro Godot
scény) **není potřeba žádný speciální produkt ani nastavení**. Claude pracuje ve
dvou režimech:

- **Claude Code** — generuje rovnou komponenty do repozitáře (`app/ui/`).
- **claude.ai s artefakty** — umí vytvořit klikací HTML/React mockup k prohlédnutí
  v prohlížeči ještě před napsáním produkčního kódu.

Aby návrh probíhal hladce, je vhodné mít připravené dva vstupy (nejsou blokery,
ale výrazně pomáhají — viz krok roadmapy v §11):

- **Design tokeny** — barvy, rozestupy, typografie jako jeden zdroj pravdy
  v `app/ui/`. Spektrální paleta už existuje v `highfrontier_poc_design_v04.md`
  §9.2 — stačí ji odtud vytáhnout.
- **Soupis komponent a breakpointů** — co se kreslí a pro jaké rozměry (PC vs.
  mobil), aby měl návrh jasné zadání.

### 8.2 Generování obrázků průletů — samostatný image model

Vizualizace průletů kolem asteroidů jsou **odlišný úkol**: Claude je textový/kódový
model a obrázky negeneruje. Tato část workflow proto **vyžaduje navíc** samostatný
image model (např. Imagen, DALL·E, Stable Diffusion) a jeho API klíč/přístup.
Volba konkrétního modelu je otevřený bod (§12).

Zamýšlený pipeline:

1. Vygenerovat obrázek průletu pro dané těleso samostatným image modelem (vstup:
   spektrální třída, tvar, velikost, albedo — parametry z `db_design.md` /
   `highfrontier_poc_design_v04.md`).
2. Schválení (lidská kontrola, aby obrázek odpovídal vědeckým parametrům tělesa).
3. Upload do **Supabase Storage**.
4. Odkaz na obrázek se uloží k tělesu a klient ho cachuje.

### 8.3 Vazba na vizuální systém

Generované obrázky musí respektovat spektrální paletu a charakter podle
`highfrontier_poc_design_v04.md` §9. AI generování obrázků je doplněk, ne náhrada
procedurálního vizuálního systému.

Realizace image pipeline (§8.2) je samostatný krok roadmapy (§11).

---

## 9. Konfigurace lodi a filtrování mapy (budoucí verze)

Nastíněno jako směr, ne detailní návrh této verze.

- **Konfigurace lodi** rozhodne o:
  - **dosahu** — rozpočet delta-v daný palivem, hmotností a motorem (`Ve`, tah —
    viz §5.2); konfigurace je vstup do modelu letu;
  - **druhu průzkumu** — jaké typy těles a jaká Tier data loď zvládne podle
    svého vybavení (skener, sondy — vazba na Tier model
    `highfrontier_poc_design_v04.md` §16.7).
- **Filtrování mapy** — mapa se nebude omezovat na ~100 nejbližších těles, ale
  umožní zobrazit větší oblasti s tělesy dané **charakteristiky** (velikost,
  rotace, spektrum). To je rozšíření dotazovací vrstvy: dnešní RPC
  `nearby_asteroids` (`db_design.md` §9.1) vrací max 100 těles podle vzdálenosti;
  filtrování podle charakteristik bude potřebovat další RPC nebo parametry.

Tyto funkce navazují na konec roadmapy (§11) a získají vlastní návrh, až se k nim
vývoj dostane.

---

## 10. Inspirace

| Zdroj | Co z něj přebíráme |
|---|---|
| **Kerbal Space Program** (PC hra) | Poctivá fyzika jako zdroj zábavy; hráč rozumí, proč manévr stojí to, co stojí; delta-v jako centrální měna |
| **High Frontier 4** (desková hra) | Diskrétní, čitelné plánování v rychlostním prostoru; hra jako rozhodovací hlavolam, ne reflexní simulátor |
| **Reálné mise** (Dawn, Hayabusa, NEAR, OSIRIS-REx) | Tier model měření — co lze zjistit z dálky, z průletu a ze zastávky (`highfrontier_poc_design_v04.md` §16.7) |

Společný jmenovatel: hry, které jsou zábavné **díky** věrnosti reálným principům,
ne navzdory ní.

---

## 11. Iterativní roadmapa

Pořadí kroků. Každý krok produkuje něco spustitelného a ověřitelného.

1. **Skelet `app/` a tech stack** — Vite + TypeScript + UI framework, prázdná
   adresářová struktura (§3.1), spustitelný „hello world".
2. **Design tokeny a soupis komponent** — vytáhnout spektrální paletu a další
   tokeny do `app/ui/`, sepsat komponenty a breakpointy (PC/mobil) jako zadání
   pro návrh UI (§8.1). Malý krok, ale zrychluje vše další.
3. **Přenos Route Planneru** — přesun mechaniky z `hf_route_planner_API.html` do
   nové modulární struktury (`game/`, `ui/`, `data/`), funkčně rovnocenný
   prototypu.
4. **Přeladění fyziky na reálné jednotky** — náprava konstant podle §5.4;
   hybridní model letu (§5).
5. **JPL odkazy** — klikatelný odkaz na SBDB v INFO panelu (§6).
6. **Vzdělávací vrstva** — glosář, vysvětlivky, externí odkazy (§7).
7. **Efemerní multiplayer presence** — modul `net/`, Supabase Realtime (§4).
8. **AI image pipeline** — výběr image modelu a generování/ukládání obrázků
   průletů (§8.2).
9. **Konfigurace lodi a filtry mapy** — viz §9; vlastní návrh před realizací.

Kroky 1–4 jsou jádro a měly by jít po sobě. Kroky 5–8 jsou do velké míry
nezávislé a lze je řadit podle priority. Krok 9 je budoucí verze.

---

## 12. Otevřené otázky

| # | Otázka | Souvislost |
|---|---|---|
| OQ-1 | Svelte vs. React — finální volba po prototypovém kroku | §3.2, krok 1 |
| OQ-2 | Balanc reálné fyziky — konkrétní hodnoty `SPEED`, `Ve`, rozpočtů delta-v | §5.4, krok 3 |
| OQ-3 | Rozsah vzdělávací vrstvy na mobilu vs. PC | §7 |
| OQ-4 | Výběr image modelu pro generování průletů (Imagen / DALL·E / SD) + rozsah pipeline (kolik těles, jak často, schvalovací proces) | §8.2 |
| OQ-5 | Struktura persistentní vrstvy pro dávkové sdílení katalogů | §4.4 |
| OQ-6 | Vykreslení mapy — kdy (a zda) přejít z Canvas 2D na WebGL | §3.2 |
| OQ-7 | Přesný formát URL JPL SBDB lookup | §6 |
| OQ-8 | Bezpečnost klíčů Supabase — výměna legacy `anon` JWT za publishable klíč | `db_design.md` §9.2 bod 1 |

---

*v1 — 2026-05-21 — výchozí návrh: architektura aplikace, tech stack, hybridní
model letu, multiplayer presence, vzdělávací vrstva, AI workflow, roadmapa*
