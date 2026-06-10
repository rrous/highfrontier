"""
Tests for the daily snapshot job — Kepler propagation and the relative-motion
fields (poloha XYZ + deltaV XYZ + dv_eff, db_design.md §11.3/§11.6).

Run: pytest pipeline/test_snapshot_daily.py -v
"""

from __future__ import annotations

import math

import pytest

from snapshot_daily import AU_M, build_snapshot, date_to_jd, propagate, solve_kepler
from datetime import date


# ── Kepler solver ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("M_deg,e", [(0, 0.1), (90, 0.156), (180, 0.5), (300, 0.8)])
def test_solve_kepler_satisfies_equation(M_deg, e):
    M = math.radians(M_deg)
    E = solve_kepler(M, e)
    M_norm = math.fmod(M, 2 * math.pi)
    if M_norm > math.pi:
        M_norm -= 2 * math.pi
    assert abs(E - e * math.sin(E) - M_norm) < 1e-9


def test_date_to_jd_reference():
    # J2000.0 epoch: 2000-01-01 12:00 TT = JD 2451545.0 → midnight is 2451544.5
    assert date_to_jd(date(2000, 1, 1)) == pytest.approx(2451544.5)


# ── propagation sanity ────────────────────────────────────────────────────────

FLORA = dict(a_au=2.2016, ecc=0.1562, inc_deg=5.89,
             node_deg=110.87, peri_deg=285.42, ma0_deg=100.0,
             epoch_jd=2460800.5)


def test_propagate_radius_and_speed_in_orbit_bounds():
    x, y, z, vx, vy, vz = propagate(**FLORA, target_jd=FLORA["epoch_jd"] + 200)
    r_au = math.sqrt(x * x + y * y + z * z) / AU_M
    a, e = FLORA["a_au"], FLORA["ecc"]
    assert a * (1 - e) - 1e-6 <= r_au <= a * (1 + e) + 1e-6
    v = math.sqrt(vx * vx + vy * vy + vz * vz) / 1000.0
    assert 14.0 < v < 23.0  # main-belt heliocentric speed, km/s


def test_propagate_conserves_vis_viva():
    MU = 1.32712440041e20
    x, y, z, vx, vy, vz = propagate(**FLORA, target_jd=FLORA["epoch_jd"] + 1234.5)
    r = math.sqrt(x * x + y * y + z * z)
    v2 = vx * vx + vy * vy + vz * vz
    a_m = FLORA["a_au"] * AU_M
    assert v2 == pytest.approx(MU * (2.0 / r - 1.0 / a_m), rel=1e-9)


# ── snapshot relative-motion fields ───────────────────────────────────────────

def _row(idx, name, **el):
    return {"id": idx, "name": name, "spectral_type": "S",
            "a_au_osc": el["a_au"], "e_osc": el["ecc"], "i_deg_osc": el["inc_deg"],
            "node_deg": el["node_deg"], "peri_deg": el["peri_deg"],
            "ma_deg": el["ma0_deg"], "epoch_jd": el["epoch_jd"]}


@pytest.fixture(scope="module")
def snapshot_items():
    neighbour = dict(FLORA, a_au=2.2539, ecc=0.1372, inc_deg=3.37, ma0_deg=104.0)
    bodies = [_row(1, "Flora", **FLORA), _row(2, "Neighbour", **neighbour)]
    items = build_snapshot(bodies, base_id_in_bodies=1, target_jd=FLORA["epoch_jd"] + 50)
    assert len(items) == 2
    return {it["name"]: it for it in items}


REQUIRED_FIELDS = [
    "x_km", "y_km", "z_km", "vx_kms", "vy_kms", "vz_kms",
    "dx_km", "dy_km", "dz_km", "d_km",
    "dvx_kms", "dvy_kms", "dvz_kms",
    "dv_kms", "v_radial_kms", "v_tang_kms", "dv_eff_kms",
]


def test_items_carry_position_and_deltav_xyz(snapshot_items):
    for it in snapshot_items.values():
        for f in REQUIRED_FIELDS:
            assert f in it, f"missing field {f}"


def test_base_row_is_zeroed(snapshot_items):
    base = snapshot_items["Flora"]
    for f in ["dx_km", "dy_km", "dz_km", "d_km",
              "dvx_kms", "dvy_kms", "dvz_kms",
              "dv_kms", "v_radial_kms", "v_tang_kms", "dv_eff_kms"]:
        assert base[f] == pytest.approx(0.0, abs=1e-12)


def test_derived_fields_consistent(snapshot_items):
    it = snapshot_items["Neighbour"]
    dv = math.sqrt(it["dvx_kms"] ** 2 + it["dvy_kms"] ** 2 + it["dvz_kms"] ** 2)
    assert it["dv_kms"] == pytest.approx(dv, rel=1e-12)

    v_radial = (it["dvx_kms"] * it["dx_km"] + it["dvy_kms"] * it["dy_km"]
                + it["dvz_kms"] * it["dz_km"]) / it["d_km"]
    assert it["v_radial_kms"] == pytest.approx(v_radial, rel=1e-9)

    # Pythagorean split and the §11.3 effective-rendezvous formula.
    assert it["v_tang_kms"] ** 2 + it["v_radial_kms"] ** 2 == pytest.approx(
        it["dv_kms"] ** 2, rel=1e-9)
    assert it["dv_eff_kms"] == pytest.approx(
        it["v_tang_kms"] + max(0.0, it["v_radial_kms"]), rel=1e-12)
    assert it["dv_eff_kms"] >= it["v_tang_kms"]
