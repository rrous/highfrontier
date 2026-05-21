// Educational layer — §7.
// Central glossary: terms used in the UI linked to short explanations.
// Texts are sourced from docs/db_design.md and docs/highfrontier_poc_design_v04.md.

export interface GlossaryEntry {
  term: string;
  short: string;  // one-line tooltip
  long?: string;  // optional extended explanation
}

export const GLOSSARY: GlossaryEntry[] = [
  { term: 'Δv', short: 'Delta-v — změna rychlosti v m/s. Základní "měna" pohybu v prostoru.' },
  { term: 'Ve', short: 'Výtoková rychlost motoru (m/s). Vyšší Ve = efektivnější motor (Tsiolkovského rovnice).' },
  { term: 'Tsiolkovsky', short: 'Raketová rovnice: spotřeba paliva závisí exponenciálně na Δv a Ve.' },
  { term: 'albedo', short: 'Odrazivost povrchu (0–1). Nízká albeda = tmavý uhlíkatý povrch.' },
  { term: 'S-typ', short: 'Silikatický asteroid — olivin, pyroxen, stopové PGM. Nejčastější ve Flora poli.' },
  { term: 'C-typ', short: 'Uhlikatý asteroid — tmavý, vodnaté minerály, organika.' },
  { term: 'M-typ', short: 'Kovový asteroid — Fe-Ni jádro, potenciálně PGM jackpot.' },
  { term: 'V-typ', short: 'Vestoidní fragment — bazalt, HED meteority.' },
  { term: 'E-typ', short: 'Enstatitový asteroid — velmi vysoká albedo, světlý povrch.' },
  { term: 'D-typ', short: 'Tmavý organický asteroid — Tagish Lake analog.' },
  { term: 'P-typ', short: 'Primitivní temný asteroid.' },
  { term: 'K-typ', short: 'Přechodový typ (S/C) — CV/CO chondrity.' },
  { term: 'rubble pile', short: 'Kupa sutin: asteroid bez pevného jádra, držený pohromadě gravitací.' },
  { term: 'interloper', short: 'Těleso dynamicky vnořené do Flora rodiny, ale jiného původu.' },
  { term: 'Tier 1', short: 'Katalogová data (JPL/WISE) — viditelná bez průletu.' },
  { term: 'Tier 2', short: 'Data z průletu — albedo, hustota, rotace, spektrum.' },
  { term: 'Tier 3', short: 'Data ze zastávky — mineralogie, rare finds.' },
];

export function lookup(term: string): GlossaryEntry | undefined {
  const t = term.toLowerCase();
  return GLOSSARY.find(e => e.term.toLowerCase() === t);
}
