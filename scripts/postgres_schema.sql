-- EIS Parser PostgreSQL schema
-- Run with: psql "$DATABASE_URL" -f scripts/postgres_schema.sql

CREATE TABLE IF NOT EXISTS zakupki (
    reg_number TEXT PRIMARY KEY,
    description TEXT,
    update_date TEXT,
    bid_end_date TEXT,
    initial_price REAL,
    link TEXT,
    combined_text TEXT,
    two_gis_url TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'raw',
    prepared_by_user_id INTEGER,
    prepared_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_results (
    reg_number TEXT PRIMARY KEY,
    zakupka_name TEXT,
    address TEXT,
    city TEXT,
    area_min_m2 REAL,
    area_max_m2 REAL,
    rooms TEXT,
    rooms_parsed TEXT,
    floor TEXT,
    building_floors_min TEXT,
    year_build_str TEXT,
    wear_percent REAL,
    zakazchik TEXT,
    FOREIGN KEY (reg_number) REFERENCES zakupki (reg_number)
);

CREATE TABLE IF NOT EXISTS listings (
    id BIGSERIAL PRIMARY KEY,
    zakupka_reg_number TEXT NOT NULL,
    rank INTEGER,
    price_rub INTEGER NOT NULL,
    address TEXT,
    rooms INTEGER,
    area_m2 REAL,
    floor INTEGER,
    building_floors INTEGER,
    building_year INTEGER,
    two_gis_url TEXT,
    external_source TEXT,
    external_url TEXT,
    fetched_at TEXT NOT NULL,
    query_url TEXT,
    FOREIGN KEY (zakupka_reg_number) REFERENCES zakupki(reg_number)
);

CREATE INDEX IF NOT EXISTS idx_listings_zakupka ON listings(zakupka_reg_number);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price_rub);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    reg_number TEXT NOT NULL,
    stage INTEGER NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected', 'skipped', 'selected')),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_decisions_user_stage ON decisions(user_id, stage);
CREATE INDEX IF NOT EXISTS idx_decisions_reg_user ON decisions(reg_number, user_id);

CREATE TABLE IF NOT EXISTS user_overrides (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    reg_number TEXT NOT NULL,
    field_name TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, reg_number, field_name)
);

CREATE INDEX IF NOT EXISTS idx_overrides_reg ON user_overrides(reg_number);

CREATE TABLE IF NOT EXISTS user_selections (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    reg_number TEXT NOT NULL,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reg_number) REFERENCES zakupki(reg_number),
    UNIQUE(user_id, reg_number)
);

CREATE INDEX IF NOT EXISTS idx_user_selections_user_id ON user_selections(user_id);
