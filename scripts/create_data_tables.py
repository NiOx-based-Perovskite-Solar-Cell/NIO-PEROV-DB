"""Create the perovskite data tables (papers, samples, layers, processes, ...).

Lookup tables (shared vocabulary):
    - unit                    : unit_code + conversion to SI
    - property                : measurable property (PCE, Voc, Jsc, ...)
    - process_type            : process kind (SPIN_COAT, ...) + param template
    - material                : chemical / material catalogue
    - perovskite_composition  : A/B/X site ions of a perovskite material
    - vendor, material_source : where a material was bought
    - solvent_system          : solvent mixture, components in solvent_component

Data tables (one paper -> many samples -> many layers):
    - paper, sample, layer, process_step, process_param,
      layer_ingredient, measurement, stability_test

Requires the auth tables (paper.created_by -> user_sys), so run
create_auth_tables.py first:
    python scripts/create_data_tables.py

Enums are VARCHAR + CHECK (easier to extend than Postgres ENUM types).
Re-running is safe: everything is IF NOT EXISTS.
"""
from db_connection import get_connection

# (table, id column, sequence) -> same explicit-sequence pattern as the auth tables
SEQUENCES = [
    ("property", "property_id", "property_id_seq"),
    ("process_type", "process_type_id", "process_type_id_seq"),
    ("material", "material_id", "material_id_seq"),
    ("vendor", "vendor_id", "vendor_id_seq"),
    ("material_source", "source_id", "material_source_id_seq"),
    ("solvent_system", "solvent_system_id", "solvent_system_id_seq"),
    ("paper", "paper_id", "paper_id_seq"),
    ("sample", "sample_id", "sample_id_seq"),
    ("layer", "layer_id", "layer_id_seq"),
    ("process_step", "step_id", "process_step_id_seq"),
    ("process_param", "param_id", "process_param_id_seq"),
    ("layer_ingredient", "ingredient_id", "layer_ingredient_id_seq"),
    ("measurement", "measurement_id", "measurement_id_seq"),
    ("stability_test", "test_id", "stability_test_id_seq"),
]

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------
CREATE_UNIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS unit (
    unit_code VARCHAR(30) PRIMARY KEY,
    quantity VARCHAR(100) NOT NULL,
    to_si_factor NUMERIC NOT NULL DEFAULT 1,
    to_si_offset NUMERIC NOT NULL DEFAULT 0
);
"""

CREATE_PROPERTY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS property (
    property_id INTEGER PRIMARY KEY DEFAULT nextval('property_id_seq'),
    code VARCHAR(50) NOT NULL UNIQUE,
    unit VARCHAR(30) REFERENCES unit(unit_code),
    valid_min NUMERIC,
    valid_max NUMERIC
);
"""

CREATE_PROCESS_TYPE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS process_type (
    process_type_id INTEGER PRIMARY KEY DEFAULT nextval('process_type_id_seq'),
    code VARCHAR(50) NOT NULL UNIQUE,
    category VARCHAR(100),
    param_template JSONB NOT NULL DEFAULT '{}'
);
"""

CREATE_MATERIAL_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS material (
    material_id INTEGER PRIMARY KEY DEFAULT nextval('material_id_seq'),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    form VARCHAR(100),
    formula VARCHAR(255),
    is_perovskite BOOLEAN NOT NULL DEFAULT FALSE
);
"""

# one row per ion on a site, e.g. (FA, A, 0.85), (Cs, A, 0.15), (Pb, B, 1), (I, X, 3)
CREATE_PEROVSKITE_COMPOSITION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS perovskite_composition (
    material_id INTEGER NOT NULL REFERENCES material(material_id) ON DELETE CASCADE,
    site VARCHAR(1) NOT NULL CHECK (site IN ('A', 'B', 'X')),
    ion VARCHAR(50) NOT NULL,
    fraction NUMERIC NOT NULL,
    PRIMARY KEY (material_id, site, ion)
);
"""

CREATE_VENDOR_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS vendor (
    vendor_id INTEGER PRIMARY KEY DEFAULT nextval('vendor_id_seq'),
    name VARCHAR(255) NOT NULL UNIQUE,
    country VARCHAR(100)
);
"""

CREATE_MATERIAL_SOURCE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS material_source (
    source_id INTEGER PRIMARY KEY DEFAULT nextval('material_source_id_seq'),
    material_id INTEGER NOT NULL REFERENCES material(material_id),
    vendor_id INTEGER REFERENCES vendor(vendor_id),
    purity_pct NUMERIC CHECK (purity_pct BETWEEN 0 AND 100),
    grade VARCHAR(100)
);
"""

CREATE_SOLVENT_SYSTEM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS solvent_system (
    solvent_system_id INTEGER PRIMARY KEY DEFAULT nextval('solvent_system_id_seq'),
    label VARCHAR(255),
    basis VARCHAR(3) NOT NULL DEFAULT 'v/v' CHECK (basis IN ('v/v', 'w/w'))
);
"""

# solvent_system.solvent_component (material_id, fraction) as its own table,
# e.g. DMF:DMSO 4:1 -> (DMF, 0.8), (DMSO, 0.2)
CREATE_SOLVENT_COMPONENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS solvent_component (
    solvent_system_id INTEGER NOT NULL REFERENCES solvent_system(solvent_system_id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES material(material_id),
    fraction NUMERIC NOT NULL,
    PRIMARY KEY (solvent_system_id, material_id)
);
"""

# ---------------------------------------------------------------------------
# Data tables (deleting a paper cascades down to everything under it)
# ---------------------------------------------------------------------------
CREATE_PAPER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS paper (
    paper_id BIGINT PRIMARY KEY DEFAULT nextval('paper_id_seq'),
    doi VARCHAR(255) UNIQUE,
    journal VARCHAR(255),
    year SMALLINT,
    title TEXT,
    source TEXT[] NOT NULL DEFAULT '{}',
    created_by BIGINT REFERENCES user_sys(user_sys_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# submission_id: no submission table yet -> plain column, add the FK later
CREATE_SAMPLE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sample (
    sample_id BIGINT PRIMARY KEY DEFAULT nextval('sample_id_seq'),
    paper_id BIGINT NOT NULL REFERENCES paper(paper_id) ON DELETE CASCADE,
    sample_no SMALLINT,
    label VARCHAR(255),
    architecture VARCHAR(3) CHECK (architecture IN ('nip', 'pin')),
    is_control BOOLEAN NOT NULL DEFAULT FALSE,
    submission_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (paper_id, sample_no)
);
"""

CREATE_LAYER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS layer (
    layer_id BIGINT PRIMARY KEY DEFAULT nextval('layer_id_seq'),
    sample_id BIGINT NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    position SMALLINT NOT NULL,
    sub_order SMALLINT NOT NULL DEFAULT 0,
    role VARCHAR(50),
    material_id INTEGER REFERENCES material(material_id),
    thickness_nm SMALLINT,
    thickness_min_nm SMALLINT,
    thickness_max_nm SMALLINT,
    UNIQUE (sample_id, position, sub_order)
);
"""

CREATE_PROCESS_STEP_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS process_step (
    step_id BIGINT PRIMARY KEY DEFAULT nextval('process_step_id_seq'),
    layer_id BIGINT NOT NULL REFERENCES layer(layer_id) ON DELETE CASCADE,
    step_order SMALLINT NOT NULL,
    process_type_id INTEGER REFERENCES process_type(process_type_id),
    scope VARCHAR(50),
    description TEXT,
    UNIQUE (layer_id, step_order)
);
"""

CREATE_PROCESS_PARAM_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS process_param (
    param_id BIGINT PRIMARY KEY DEFAULT nextval('process_param_id_seq'),
    step_id BIGINT NOT NULL REFERENCES process_step(step_id) ON DELETE CASCADE,
    param VARCHAR(100) NOT NULL,
    value NUMERIC,
    value_min NUMERIC,
    value_max NUMERIC,
    qualifier VARCHAR(1) NOT NULL DEFAULT '=' CHECK (qualifier IN ('=', '<', '>', '≈')),
    unit VARCHAR(30) REFERENCES unit(unit_code)
);
"""

CREATE_LAYER_INGREDIENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS layer_ingredient (
    ingredient_id BIGINT PRIMARY KEY DEFAULT nextval('layer_ingredient_id_seq'),
    layer_id BIGINT NOT NULL REFERENCES layer(layer_id) ON DELETE CASCADE,
    material_id INTEGER REFERENCES material(material_id),
    role VARCHAR(50),
    solvent_system_id INTEGER REFERENCES solvent_system(solvent_system_id),
    amount NUMERIC,
    unit VARCHAR(30) REFERENCES unit(unit_code)
);
"""

CREATE_MEASUREMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS measurement (
    measurement_id BIGINT PRIMARY KEY DEFAULT nextval('measurement_id_seq'),
    sample_id BIGINT NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    property_id INTEGER NOT NULL REFERENCES property(property_id),
    statistic VARCHAR(30),
    scan VARCHAR(2) NOT NULL DEFAULT 'NA' CHECK (scan IN ('RS', 'FS', 'NA')),
    value NUMERIC,
    error NUMERIC,
    unit VARCHAR(30) REFERENCES unit(unit_code)
);
"""

CREATE_STABILITY_TEST_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stability_test (
    test_id BIGINT PRIMARY KEY DEFAULT nextval('stability_test_id_seq'),
    sample_id BIGINT NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    atmosphere VARCHAR(100),
    light VARCHAR(100),
    mode VARCHAR(100),
    isos_code VARCHAR(30),
    encapsulated BOOLEAN,
    temperature_c NUMERIC,
    rh_pct NUMERIC,
    rh_min_pct NUMERIC,
    rh_max_pct NUMERIC,
    duration_h NUMERIC,
    retention_pct NUMERIC,
    t80_h NUMERIC
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_sample_paper_id ON sample(paper_id);
CREATE INDEX IF NOT EXISTS idx_layer_material_id ON layer(material_id);
CREATE INDEX IF NOT EXISTS idx_process_param_step_id ON process_param(step_id);
CREATE INDEX IF NOT EXISTS idx_layer_ingredient_layer_id ON layer_ingredient(layer_id);
CREATE INDEX IF NOT EXISTS idx_measurement_sample_id ON measurement(sample_id);
CREATE INDEX IF NOT EXISTS idx_measurement_property_id ON measurement(property_id);
CREATE INDEX IF NOT EXISTS idx_stability_test_sample_id ON stability_test(sample_id);
CREATE INDEX IF NOT EXISTS idx_material_source_material_id ON material_source(material_id);
"""

# creation order matters (FK targets first)
CREATE_TABLES = [
    ("unit", CREATE_UNIT_TABLE_SQL),
    ("property", CREATE_PROPERTY_TABLE_SQL),
    ("process_type", CREATE_PROCESS_TYPE_TABLE_SQL),
    ("material", CREATE_MATERIAL_TABLE_SQL),
    ("perovskite_composition", CREATE_PEROVSKITE_COMPOSITION_TABLE_SQL),
    ("vendor", CREATE_VENDOR_TABLE_SQL),
    ("material_source", CREATE_MATERIAL_SOURCE_TABLE_SQL),
    ("solvent_system", CREATE_SOLVENT_SYSTEM_TABLE_SQL),
    ("solvent_component", CREATE_SOLVENT_COMPONENT_TABLE_SQL),
    ("paper", CREATE_PAPER_TABLE_SQL),
    ("sample", CREATE_SAMPLE_TABLE_SQL),
    ("layer", CREATE_LAYER_TABLE_SQL),
    ("process_step", CREATE_PROCESS_STEP_TABLE_SQL),
    ("process_param", CREATE_PROCESS_PARAM_TABLE_SQL),
    ("layer_ingredient", CREATE_LAYER_INGREDIENT_TABLE_SQL),
    ("measurement", CREATE_MEASUREMENT_TABLE_SQL),
    ("stability_test", CREATE_STABILITY_TEST_TABLE_SQL),
]


def main():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for _, _, seq in SEQUENCES:
                    cur.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq};")
                for _, sql in CREATE_TABLES:
                    cur.execute(sql)
                for table, column, seq in SEQUENCES:
                    cur.execute(f"ALTER SEQUENCE {seq} OWNED BY {table}.{column};")
                cur.execute(CREATE_INDEXES_SQL)
        print(f"Created (or already exist): {', '.join(name for name, _ in CREATE_TABLES)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
