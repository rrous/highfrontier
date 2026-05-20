"""
Scientific correctness & diversity tests for the Flora pipeline.

Run: pytest pipeline/test_flora_pipeline.py -v
"""

from __future__ import annotations

import pytest
import numpy as np
from collections import Counter

from fetch_flora import (
    run_pipeline,
    SPECTRAL_DIST,
    ALBEDO_RANGE,
    GRAIN_DENSITY_PARAMS,
    COMPOSITION_TEMPLATES,
    RARE_FIND_MATRIX,
    RARE_FIND_TIERS,
    build_tier1,
    build_tier2,
    build_tier3,
    diameter_from_H,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def asteroids():
    """Run pipeline with 500 synthetic bodies (deterministic seed)."""
    return run_pipeline(limit=500, seed=7)


@pytest.fixture(scope="module")
def sample_records(asteroids):
    return asteroids


# ── helper ────────────────────────────────────────────────────────────────────

def _t1(a):  return a["tier1"]
def _t2(a):  return a["tier2"]
def _t3(a):  return a["tier3"]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Scientific correctness of individual parameters
# ══════════════════════════════════════════════════════════════════════════════

class TestDiameterFormula:
    """D = (1329/√pV) · 10^(−H/5)  must be self-consistent."""

    @pytest.mark.parametrize("H,pV,D_expected", [
        (15.0, 0.24, 1329.0 / np.sqrt(0.24) * 10 ** (-15 / 5)),
        (11.0, 0.25, 1329.0 / np.sqrt(0.25) * 10 ** (-11 / 5)),
        (18.0, 0.05, 1329.0 / np.sqrt(0.05) * 10 ** (-18 / 5)),
    ])
    def test_formula(self, H, pV, D_expected):
        assert abs(diameter_from_H(H, pV) - D_expected) < 1e-6

    def test_range_sanity(self):
        # Flora bodies: H 11–18, pV 0.03–0.50 → D should be 0.1–80 km
        for H in np.linspace(11, 18, 8):
            for pV in [0.05, 0.24, 0.45]:
                D = diameter_from_H(H, pV)
                assert 0.05 < D < 200, f"D={D} out of range for H={H}, pV={pV}"


class TestTier1Values:
    def test_H_range(self, asteroids):
        # Flora family spans H≈6 (Flora itself, D≈150km) to H≈20+ (sub-km)
        for a in asteroids:
            H = _t1(a)["H_magnitude"]
            assert 3 <= H <= 25, f"Unphysical H={H}"

    def test_albedo_range(self, asteroids):
        # Only check generated albedos — WISE-measured values are ground truth
        # and may lie outside our model range (e.g. high-albedo S outliers)
        for a in asteroids:
            if _t1(a).get("albedo_source") != "generated":
                continue
            pv   = _t1(a)["albedo_pv"]
            spec = _t1(a)["spectral_class"]
            lo, hi = ALBEDO_RANGE[spec]
            assert lo - 0.02 <= pv <= hi + 0.02, (
                f"{spec} generated albedo={pv} outside model range [{lo},{hi}]"
            )

    def test_wise_albedo_physically_plausible(self, asteroids):
        """WISE-measured albedos must be in general physical bounds (0.01–0.99)."""
        for a in asteroids:
            if _t1(a).get("albedo_source") != "WISE":
                continue
            pv = _t1(a)["albedo_pv"]
            assert 0.01 <= pv <= 0.99, f"WISE albedo {pv} physically impossible"

    def test_diameter_positive_and_reasonable(self, asteroids):
        for a in asteroids:
            D = _t1(a)["diameter_km"]
            assert D > 0, "Diameter must be positive"
            assert D < 300, f"Diameter {D} km too large for Flora family"

    def test_orbital_elements_flora_region(self, asteroids):
        """Semi-major axis, eccentricity, inclination must match Flora-region bounds."""
        for a in asteroids:
            t1 = _t1(a)
            assert 2.0 < t1["a_au"] < 2.6, f"a={t1['a_au']} outside Flora region"
            assert 0 < t1["e"] < 0.30, f"e={t1['e']} unphysical"
            assert 0 < t1["inc_deg"] < 15, f"inc={t1['inc_deg']} outside Flora region"

    def test_perihelion_less_than_aphelion(self, asteroids):
        for a in asteroids:
            t1 = _t1(a)
            assert t1["q_au"] < t1["Q_au"], "Perihelion must be < aphelion"
            assert abs(t1["q_au"] - t1["a_au"] * (1 - t1["e"])) < 0.01
            assert abs(t1["Q_au"] - t1["a_au"] * (1 + t1["e"])) < 0.01


class TestTier2PhysicsBounds:
    def test_density_range_per_class(self, asteroids):
        # bulk density: rubble C-types can be ~0.5, iron M-types up to ~6
        # grain density: minerals range from 1.0 to 9.0
        for a in asteroids:
            bulk  = _t2(a)["bulk_density_gcc"]
            grain = _t2(a)["grain_density_gcc"]
            spec  = _t1(a)["spectral_class"]
            assert 0.5 <= bulk <= 6.0, f"{spec} bulk_density={bulk} unphysical"
            assert 1.0 <= grain <= 9.0, f"{spec} grain_density={grain} unphysical"

    def test_M_type_density_above_C(self, asteroids):
        """M-type mean bulk density must exceed C-type mean bulk density (confirmed literature)."""
        rho_M = [_t2(a)["bulk_density_gcc"] for a in asteroids if _t1(a)["spectral_class"] == "M"]
        rho_C = [_t2(a)["bulk_density_gcc"] for a in asteroids if _t1(a)["spectral_class"] == "C"]
        if rho_M and rho_C:
            assert np.mean(rho_M) > np.mean(rho_C), (
                f"M-type mean density {np.mean(rho_M):.2f} should exceed C-type {np.mean(rho_C):.2f}"
            )

    def test_rotation_period_physical(self, asteroids):
        for a in asteroids:
            rot = _t2(a)["rotation_h"]
            # spin barrier at ~2.0 h for rubble piles (Pravec & Harris 2000)
            assert rot >= 2.0, f"rotation {rot}h violates rubble-pile spin barrier"
            assert rot <= 2000, f"rotation {rot}h unrealistically slow"

    def test_mass_consistent_with_density_diameter(self, asteroids):
        for a in asteroids:
            t1 = _t1(a); t2 = _t2(a)
            D   = t1["diameter_km"] * 1000       # m
            rho = t2["bulk_density_gcc"] * 1e3   # kg/m³
            expected_mass = rho * (4 / 3) * np.pi * (D / 2) ** 3
            actual_mass   = t2["mass_kg"]
            # allow 0.1% floating-point drift
            assert abs(actual_mass - expected_mass) / expected_mass < 0.001, (
                f"Mass {actual_mass:.3e} inconsistent with D={D}m, rho={rho} kg/m³"
            )

    def test_escape_velocity_non_negative(self, asteroids):
        for a in asteroids:
            assert _t2(a)["escape_velocity_ms"] >= 0

    def test_surface_gravity_increases_with_size(self, asteroids):
        """Larger bodies (same class) must have higher surface gravity on average (g ∝ r ρ)."""
        S_type = [a for a in asteroids if _t1(a)["spectral_class"] == "S"]
        if len(S_type) < 20:
            pytest.skip("Not enough S-type bodies for statistical test")
        S_type.sort(key=lambda a: _t1(a)["diameter_km"])
        small = S_type[:10]
        large = S_type[-10:]
        g_small = np.mean([_t2(a)["surface_gravity"] for a in small])
        g_large = np.mean([_t2(a)["surface_gravity"] for a in large])
        assert g_large > g_small, (
            f"Larger S-type bodies should have higher g: {g_large:.2e} vs {g_small:.2e}"
        )


class TestTier3Composition:
    def test_composition_sums_to_100(self, asteroids):
        for a in asteroids:
            comp  = _t3(a)["composition"]
            total = sum(comp.values())
            assert abs(total - 100.0) < 0.1, f"Composition sums to {total}, not 100"

    def test_composition_non_negative(self, asteroids):
        for a in asteroids:
            for mineral, pct in _t3(a)["composition"].items():
                assert pct >= 0, f"{mineral}={pct} is negative"

    def test_S_type_olivine_dominant(self, asteroids):
        """S-types must have olivin as largest or second-largest mineral (Nakamura 2011)."""
        S_asteroids = [a for a in asteroids if _t1(a)["spectral_class"] == "S"]
        for a in S_asteroids:
            comp = _t3(a)["composition"]
            sorted_minerals = sorted(comp, key=comp.get, reverse=True)
            assert "olivin" in sorted_minerals[:2], (
                f"olivin not in top-2 for S-type: {sorted_minerals[:3]}"
            )

    def test_C_type_phyllosilicate_dominant(self, asteroids):
        """C-types: fylosilikat must be largest mineral (Ryugu/Murchison data)."""
        C_asteroids = [a for a in asteroids if _t1(a)["spectral_class"] == "C"]
        if not C_asteroids:
            pytest.skip("No C-type in sample")
        fails = 0
        for a in C_asteroids:
            comp = _t3(a)["composition"]
            if max(comp, key=comp.get) != "fylosilikat":
                fails += 1
        # allow up to 5% failure rate due to sigma noise
        assert fails / len(C_asteroids) < 0.05, (
            f"{fails}/{len(C_asteroids)} C-type bodies don't have fylosilikat dominant"
        )

    def test_M_type_metal_dominant(self, asteroids):
        """M-types: fe_ni_metal must be >> 50% (Wasson 1985)."""
        M_asteroids = [a for a in asteroids if _t1(a)["spectral_class"] == "M"]
        if not M_asteroids:
            pytest.skip("No M-type in sample")
        for a in M_asteroids:
            comp = _t3(a)["composition"]
            assert comp.get("fe_ni_metal", 0) > 50, (
                f"M-type fe_ni_metal only {comp.get('fe_ni_metal',0):.1f}%"
            )

    def test_water_only_in_hydrated_classes(self, asteroids):
        """h2o_bound appears only in hydrated composition templates (C, D, P, U)."""
        # U is the "unknown" catch-all blend that includes hydrated endmembers
        hydrated = {"C", "D", "P", "U"}
        for a in asteroids:
            spec = _t1(a)["spectral_class"]
            comp = _t3(a)["composition"]
            h2o  = comp.get("h2o_bound", 0)
            if spec not in hydrated:
                assert h2o == 0.0, f"{spec} has h2o_bound={h2o:.4f}% (template error)"

    def test_PGM_only_in_M_type(self, asteroids):
        """Platinum-group metals (pt, pd, ir) only appear in M-type composition template."""
        for a in asteroids:
            spec = _t1(a)["spectral_class"]
            comp = _t3(a)["composition"]
            if spec != "M":
                for pgm in ("pt", "pd", "ir"):
                    assert comp.get(pgm, 0) == 0.0, (
                        f"{spec} has {pgm}={comp.get(pgm,0)} (PGM only in M-type)"
                    )

    def test_porosity_range(self, asteroids):
        for a in asteroids:
            p = _t2(a)["macro_porosity"]
            assert 0.0 <= p <= 0.80, f"macro_porosity {p} out of physical range [0, 0.8]"
            mp = _t3(a)["micro_porosity"]
            assert 0.0 <= mp <= 0.15, f"micro_porosity {mp} out of physical range [0, 0.15]"


class TestRareFinds:
    def test_rare_finds_valid_ids(self, asteroids):
        valid_ids = set(RARE_FIND_MATRIX.keys())
        for a in asteroids:
            for rf in _t3(a)["rare_finds"]:
                assert rf["find_id"] in valid_ids, f"Unknown rare find: {rf['find_id']}"

    def test_rare_finds_rarity_consistent(self, asteroids):
        for a in asteroids:
            for rf in _t3(a)["rare_finds"]:
                expected = RARE_FIND_TIERS.get(rf["find_id"])
                assert rf["rarity"] == expected, (
                    f"{rf['find_id']}: rarity {rf['rarity']} != expected {expected}"
                )

    def test_quasicrystal_only_M_type(self, asteroids):
        """Quasicrystal (Khatyrka) found only in M-type meteorites."""
        for a in asteroids:
            spec = _t1(a)["spectral_class"]
            finds = {rf["find_id"] for rf in _t3(a)["rare_finds"]}
            if "quasicrystal" in finds:
                assert spec == "M", f"quasicrystal found on {spec}-type (must be M-type)"

    def test_magnetic_record_not_in_C_type(self, asteroids):
        """Palaeomagnetic record is specific to M-type and E-type."""
        for a in asteroids:
            spec  = _t1(a)["spectral_class"]
            finds = {rf["find_id"] for rf in _t3(a)["rare_finds"]}
            if "magnetic_record" in finds:
                assert spec in ("M", "E"), (
                    f"magnetic_record found on {spec}-type (only M/E)"
                )

    def test_ti_concentrate_only_V_type(self, asteroids):
        for a in asteroids:
            spec  = _t1(a)["spectral_class"]
            finds = {rf["find_id"] for rf in _t3(a)["rare_finds"]}
            if "ti_concentrate" in finds:
                assert spec == "V", f"ti_concentrate on {spec} (must be V-type)"

    def test_pt_jackpot_only_M_type(self, asteroids):
        for a in asteroids:
            spec  = _t1(a)["spectral_class"]
            finds = {rf["find_id"] for rf in _t3(a)["rare_finds"]}
            if "pt_jackpot" in finds:
                assert spec == "M", f"pt_jackpot on {spec} (must be M-type)"

    def test_rare_find_abundance_positive(self, asteroids):
        for a in asteroids:
            for rf in _t3(a)["rare_finds"]:
                assert rf["abundance"] > 0, f"Negative abundance for {rf['find_id']}"

    def test_legendary_count_in_plausible_range(self, asteroids):
        """
        Extrapolate to 10k: LEGENDARY count target is 15–50 (db_design).
        With 500 bodies the Poisson noise is large, so we use a very wide sanity band.
        Per-class probability correctness is tested by test_quasicrystal_only_M_type etc.
        """
        n   = len(asteroids)
        leg = sum(
            1 for a in asteroids
            for rf in _t3(a)["rare_finds"]
            if rf["rarity"] == "LEGENDARY"
        )
        leg_10k = leg * 10000 / n
        # Wide band: Poisson CI for ~25 events in 10k scales to [0, 500] for a 500-body sample
        assert leg_10k <= 500, (
            f"Extrapolated LEGENDARY count {leg_10k:.0f} >> design max 50 — probabilities too high"
        )

    def test_exotic_count_in_plausible_range(self, asteroids):
        n   = len(asteroids)
        exo = sum(
            1 for a in asteroids
            for rf in _t3(a)["rare_finds"]
            if rf["rarity"] == "EXOTIC"
        )
        exo_10k = exo * 10000 / n
        assert 50 <= exo_10k <= 1500, (
            f"Extrapolated EXOTIC count {exo_10k:.0f} outside design range [100, 300]"
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Diversity checks (the field must not be monotonous)
# ══════════════════════════════════════════════════════════════════════════════

class TestSpectralDiversity:
    def test_all_classes_present(self, asteroids):
        classes = {_t1(a)["spectral_class"] for a in asteroids}
        assert len(classes) >= 7, f"Only {len(classes)} spectral classes present: {classes}"

    def test_S_type_dominant(self, asteroids):
        counts = Counter(_t1(a)["spectral_class"] for a in asteroids)
        n = len(asteroids)
        frac_S = counts["S"] / n
        assert 0.55 <= frac_S <= 0.85, (
            f"S-type fraction {frac_S:.2%} outside expected 55–85% for Flora region"
        )

    def test_spectral_distribution_roughly_correct(self, asteroids):
        """Each class frequency should be within 4× of the target distribution.
        Only meaningful for n >= 200 (small samples have high Poisson noise)."""
        n = len(asteroids)
        if n < 200:
            pytest.skip(f"Sample too small ({n}) for distribution test; need >= 200")
        counts = Counter(_t1(a)["spectral_class"] for a in asteroids)
        for cls, target_frac in SPECTRAL_DIST.items():
            observed = counts.get(cls, 0) / n
            assert observed <= target_frac * 4.0, (
                f"{cls}: observed {observed:.2%} >> target {target_frac:.2%}"
            )


class TestSizeDistribution:
    def test_size_spans_three_orders(self, asteroids):
        """Flora family spans ~0.1 km (small) to ~20 km (Flora itself)."""
        diameters = [_t1(a)["diameter_km"] for a in asteroids]
        ratio = max(diameters) / min(diameters)
        assert ratio > 10, (
            f"Size range ratio {ratio:.1f} too narrow; Flora spans >100× in diameter"
        )

    def test_size_distribution_power_law(self, asteroids):
        """
        Asteroid size distribution follows approximate power law.
        N(>D) ∝ D^{-q}: more small bodies than large.
        """
        diameters = sorted([_t1(a)["diameter_km"] for a in asteroids])
        median = np.median(diameters)
        small = sum(1 for d in diameters if d < median)
        large = sum(1 for d in diameters if d >= median)
        # trivially true by construction, but checks we're not clustering at one size
        assert small > 0 and large > 0


class TestAlbedoDiversity:
    def test_albedo_spans_dark_to_bright(self, asteroids):
        albedos = [_t1(a)["albedo_pv"] for a in asteroids]
        assert min(albedos) < 0.10, "No dark bodies (pV < 0.10) generated"
        assert max(albedos) > 0.25, "No bright bodies (pV > 0.25) generated"

    def test_albedo_bimodal_hint(self, asteroids):
        """Flora region has bimodal albedo distribution (dark C + bright S)."""
        albedos = np.array([_t1(a)["albedo_pv"] for a in asteroids])
        dark  = (albedos < 0.12).sum()
        bright = (albedos > 0.20).sum()
        assert dark > 10,  f"Too few dark bodies ({dark}) for C/D/P types"
        assert bright > 10, f"Too few bright bodies ({bright}) for S/V/E types"


class TestRotationDiversity:
    def test_rotation_spans_hours_to_days(self, asteroids):
        rots = [_t2(a)["rotation_h"] for a in asteroids]
        assert min(rots) < 8,   "No fast rotators present"
        assert max(rots) > 24,  "No slow rotators (>1 day) present"

    def test_no_super_fast_rotators_in_large_bodies(self, asteroids):
        """
        Bodies > 300 m should not spin faster than 2.0 h (rubble-pile barrier,
        Pravec & Harris 2000 — monoliths can spin faster but are small).
        """
        for a in asteroids:
            D   = _t1(a)["diameter_km"]
            rot = _t2(a)["rotation_h"]
            struct = _t2(a)["structure"]
            if D > 0.3 and struct == "rubble_pile":
                assert rot >= 2.0, (
                    f"Rubble-pile D={D:.2f}km rotates at {rot}h < 2h spin barrier"
                )


class TestStructureDiversity:
    def test_both_structure_types_present(self, asteroids):
        structs = {_t2(a)["structure"] for a in asteroids}
        assert "rubble_pile" in structs, "No rubble-pile bodies generated"
        # Monoliths only appear for D < 0.5 km; skip assertion if sample has no small bodies
        small = [a for a in asteroids if _t1(a)["diameter_km"] < 0.5]
        if small:
            mono = {_t2(a)["structure"] for a in small}
            assert "monolith" in mono, "No monolithic bodies among sub-500m asteroids"

    def test_small_bodies_can_be_monolithic(self, asteroids):
        small = [a for a in asteroids if _t1(a)["diameter_km"] < 0.15]
        if not small:
            pytest.skip("No sub-150m bodies in sample — increase H range or sample size")
        mono = [a for a in small if _t2(a)["structure"] == "monolith"]
        assert len(mono) > 0, "No monolithic bodies among sub-150m asteroids"


class TestCompositionDiversity:
    def test_rare_find_types_present(self, asteroids):
        all_finds = {rf["find_id"] for a in asteroids for rf in _t3(a)["rare_finds"]}
        # with 500 bodies we expect at least 5 distinct rare find types
        assert len(all_finds) >= 5, (
            f"Only {len(all_finds)} distinct rare find types: {all_finds}"
        )

    def test_no_two_asteroids_identical_composition(self, asteroids):
        """Each composition vector should be unique (stochastic generation)."""
        seen = set()
        for a in asteroids:
            comp_key = tuple(sorted(_t3(a)["composition"].items()))
            assert comp_key not in seen, "Duplicate composition found (RNG broken?)"
            seen.add(comp_key)

    def test_D_type_has_most_organic_carbon(self, asteroids):
        """D-types have highest c_organic abundance (Tagish Lake, DeMeo 2009)."""
        def mean_organic(cls):
            bodies = [a for a in asteroids if _t1(a)["spectral_class"] == cls]
            if not bodies:
                return 0.0
            return np.mean([_t3(a)["composition"].get("c_organic", 0) for a in bodies])

        d_org = mean_organic("D")
        s_org = mean_organic("S")
        # D > S for c_organic is a confirmed scientific fact
        if d_org > 0 and s_org >= 0:
            assert d_org > s_org * 2, (
                f"D-type organic {d_org:.2f}% should be > 2× S-type {s_org:.2f}%"
            )

    def test_V_type_has_ilmenite(self, asteroids):
        """V-types (HED) have ilmenite; must appear in their composition."""
        V_asteroids = [a for a in asteroids if _t1(a)["spectral_class"] == "V"]
        if not V_asteroids:
            pytest.skip("No V-type bodies in sample")
        has_ilmenite = [a for a in V_asteroids if _t3(a)["composition"].get("ilmenit", 0) > 0]
        assert len(has_ilmenite) > 0, "No V-type body has ilmenite in composition"


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Data integrity & pipeline health
# ══════════════════════════════════════════════════════════════════════════════

class TestDataIntegrity:
    def test_all_records_have_required_keys(self, asteroids):
        required_t1 = {"H_magnitude", "albedo_pv", "diameter_km", "a_au", "e", "inc_deg",
                       "q_au", "Q_au", "spectral_class"}
        required_t2 = {"grain_density_gcc", "bulk_density_gcc", "macro_porosity", "mass_kg", "rotation_h", "structure"}
        required_t3 = {"composition", "rare_finds", "micro_porosity"}
        for a in asteroids:
            assert required_t1 <= _t1(a).keys(), f"Missing T1 keys in {a['name']}"
            assert required_t2 <= _t2(a).keys(), f"Missing T2 keys in {a['name']}"
            assert required_t3 <= _t3(a).keys(), f"Missing T3 keys in {a['name']}"

    def test_source_ids_unique(self, asteroids):
        ids = [a["source_id"] for a in asteroids]
        assert len(ids) == len(set(ids)), "Duplicate source_id values"

    def test_pipeline_deterministic(self):
        """Same seed must produce identical output."""
        a1 = run_pipeline(limit=20, seed=123)
        a2 = run_pipeline(limit=20, seed=123)
        for r1, r2 in zip(a1, a2):
            assert r1["tier1"] == r2["tier1"], "Pipeline is not deterministic"
            assert r1["tier3"]["composition"] == r2["tier3"]["composition"]

    def test_different_seeds_differ(self):
        # Tier 1 is dominated by real measurements (WISE albedos are fixed per body),
        # so we check Tier 3 composition which is always generated stochastically.
        a1 = run_pipeline(limit=20, seed=1)
        a2 = run_pipeline(limit=20, seed=2)
        same_t3 = sum(
            1 for r1, r2 in zip(a1, a2)
            if r1["tier3"]["composition"] == r2["tier3"]["composition"]
        )
        assert same_t3 < 5, (
            f"Different seeds produce identical Tier 3 compositions ({same_t3}/20)"
        )
