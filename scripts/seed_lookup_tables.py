"""Seed the lookup tables from the clean-data dictionaries.

Source of truth is the CSV dictionaries used by the server's clean-data
pipeline, so DB codes/names match exactly what the pipeline emits:
    nio-perov-server/src/modules/data/clean_data/dictionaries/

Seeds (in FK order):
    - unit                    <- unit.csv          (factor/offset -> to_si_factor/to_si_offset)
    - property                <- property.csv
    - process_type            <- process_type.csv (+ param_template, defined below)
    - material                <- material.csv      (is_perovskite = category 'perovskite')
    - perovskite_composition  <- fixed-stoichiometry perovskites in material.csv
    - vendor                  <- canonical names in vendor_alias.csv

Note: unit.csv factors convert to the base unit of each quantity as used by
the pipeline (e.g. nm, μL, mg, °C), not strictly SI.

Not seeded: solvent_system (built per sample by the pipeline), material_source
and all data tables.

Run after create_data_tables.py:
    python scripts/seed_lookup_tables.py

Re-running is safe: existing rows are never overwritten.
"""
import csv
import json
from pathlib import Path

from db_connection import get_connection

DICT_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "nio-perov-server" / "src" / "modules" / "data" / "clean_data" / "dictionaries"
)

# fixed-stoichiometry ABX3 materials from material.csv (CsFAMA has no fixed ratio)
PEROVSKITE_COMPOSITIONS = {
    "MAPbCl3": [("A", "MA", 1), ("B", "Pb", 1), ("X", "Cl", 3)],
    "MAPbBr3": [("A", "MA", 1), ("B", "Pb", 1), ("X", "Br", 3)],
    "CsPbI3": [("A", "Cs", 1), ("B", "Pb", 1), ("X", "I", 3)],
}


# process_type.param_template: (param, default unit) per process type
# param names follow param_name.csv so they match what the pipeline loads
PARAM_TEMPLATES = {
    "WASH": [("duration", "min")],
    "SONICATE": [("duration", "min"), ("temperature", "°C")],
    "PLASMA": [("power", "W"), ("duration", "min")],
    "UV_OZONE": [("duration", "min")],
    "UV_TREAT": [("duration", "min")],
    "SURFACE_TREAT": [("duration", "s")],
    "SPIN_COAT": [("spin_speed", "rpm"), ("duration", "s"), ("acceleration", "rpm/s")],
    "BLADE_COAT": [("coating_speed", "mm/s"), ("gap", "μm"), ("temperature", "°C")],
    "SLOT_DIE": [("coating_speed", "mm/s"), ("gap", "μm"), ("temperature", "°C")],
    "DIP_COAT": [("duration", "s"), ("coating_speed", "mm/s")],
    "SPRAY_PYROLYSIS": [("temperature", "°C"), ("volume", "mL"), ("repetitions", "times")],
    "CBD": [("temperature", "°C"), ("duration", "min")],
    "ANTISOLVENT": [("drip_time", "s"), ("volume", "μL")],
    "THERMAL_EVAP": [("rate", "Å/s"), ("pressure", "Pa")],
    "EBEAM_EVAP": [("rate", "Å/s"), ("pressure", "Pa")],
    "SPUTTER": [("power", "W"), ("pressure", "Pa"), ("duration", "min")],
    "PRESPUTTER": [("power", "W"), ("duration", "min")],
    "ALD": [("temperature", "°C"), ("repetitions", "times")],
    "ANNEAL": [("temperature", "°C"), ("duration", "min"), ("ramp_rate", "°C/min")],
    "DRY": [("temperature", "°C"), ("duration", "min")],
    "STIR": [("stir_speed", "rpm"), ("duration", "h"), ("temperature", "°C")],
    "MIX": [("duration", "min")],
    "DISSOLVE": [("duration", "h"), ("temperature", "°C")],
    "PH_ADJUST": [],
    "VACUUM": [("pressure", "Pa"), ("duration", "s")],
}


def read_csv(name):
    """Read a dictionary CSV, skipping '#' comment lines."""
    with open(DICT_DIR / name, encoding="utf-8", newline="") as f:
        lines = [line for line in f if line.strip() and not line.startswith("#")]
    return list(csv.DictReader(lines))


def num(value):
    value = (value or "").strip()
    return value if value else None


def seed_units(cur):
    rows = read_csv("unit.csv")
    for r in rows:
        cur.execute(
            """
            INSERT INTO unit (unit_code, quantity, to_si_factor, to_si_offset)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (unit_code) DO NOTHING;
            """,
            (r["unit"], r["quantity"], r["factor"], r["offset"]),
        )
    return len(rows)


def seed_properties(cur):
    rows = read_csv("property.csv")
    for r in rows:
        cur.execute(
            """
            INSERT INTO property (code, unit, valid_min, valid_max)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING;
            """,
            (r["code"], num(r["unit"]), num(r["valid_min"]), num(r["valid_max"])),
        )
    return len(rows)


def seed_process_types(cur):
    rows = read_csv("process_type.csv")
    for r in rows:
        cur.execute(
            """
            INSERT INTO process_type (code, category)
            VALUES (%s, %s)
            ON CONFLICT (code) DO NOTHING;
            """,
            (r["code"], r["category"]),
        )
    return len(rows)


def seed_param_templates(cur):
    """Fill process_type.param_template (only while it is still empty '{}').

    Format: {"params": [{"param": <process_param.param>, "unit": <default unit_code>}]}
    The admin UI shows these as input fields; the unit select lists every unit
    with the same quantity as the default one.
    """
    cur.execute("SELECT unit_code FROM unit;")
    units = {row[0] for row in cur.fetchall()}
    for code, params in PARAM_TEMPLATES.items():
        missing = [u for _, u in params if u not in units]
        if missing:
            raise ValueError(f"{code}: unknown unit(s) {missing}")
        template = {"params": [{"param": p, "unit": u} for p, u in params]}
        cur.execute(
            """
            UPDATE process_type SET param_template = %s::jsonb
            WHERE code = %s AND param_template = '{}'::jsonb;
            """,
            (json.dumps(template, ensure_ascii=False), code),
        )
    return len(PARAM_TEMPLATES)


def seed_materials(cur):
    # material.name has no UNIQUE constraint -> insert only if the name is new
    rows = read_csv("material.csv")
    for r in rows:
        cur.execute(
            """
            INSERT INTO material (name, category, is_perovskite)
            SELECT %s, %s, %s
            WHERE NOT EXISTS (SELECT 1 FROM material WHERE name = %s);
            """,
            (r["name"], r["category"], r["category"] == "perovskite", r["name"]),
        )
    return len(rows)


def seed_perovskite_compositions(cur):
    count = 0
    for name, ions in PEROVSKITE_COMPOSITIONS.items():
        for site, ion, fraction in ions:
            cur.execute(
                """
                INSERT INTO perovskite_composition (material_id, site, ion, fraction)
                SELECT material_id, %s, %s, %s FROM material WHERE name = %s
                ON CONFLICT (material_id, site, ion) DO NOTHING;
                """,
                (site, ion, fraction, name),
            )
            count += 1
    return count


def seed_vendors(cur):
    names = sorted({r["vendor"] for r in read_csv("vendor_alias.csv")})
    for name in names:
        cur.execute(
            "INSERT INTO vendor (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;",
            (name,),
        )
    return len(names)


SEEDERS = [
    ("unit", seed_units),
    ("property", seed_properties),
    ("process_type", seed_process_types),
    ("process_type", seed_param_templates),
    ("material", seed_materials),
    ("perovskite_composition", seed_perovskite_compositions),
    ("vendor", seed_vendors),
]


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for table, seeder in SEEDERS:
                    n = seeder(cur)
                    cur.execute(f"SELECT count(*) FROM {table};")
                    print(f"{table:<24} source rows: {n:>4}   rows in table: {cur.fetchone()[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
