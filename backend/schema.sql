-- Post-Sales AI Analytics Platform — Sprint 1 schema

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin','management','engineering','qa','customer_service');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL,
    is_first_login BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(150),
    email VARCHAR(150),
    phone VARCHAR(50),
    region VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(100),
    model_number VARCHAR(100),
    release_date DATE
);

CREATE TABLE IF NOT EXISTS complaints (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    description TEXT NOT NULL,
    channel VARCHAR(100),
    status VARCHAR(50) DEFAULT 'open',
    source_record_id VARCHAR(100) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS complaint_insights (
    id SERIAL PRIMARY KEY,
    complaint_id INTEGER NOT NULL REFERENCES complaints(id),
    sentiment VARCHAR(20),
    severity VARCHAR(20),
    symptoms TEXT,
    category VARCHAR(100),
    processed_text TEXT,
    model_version VARCHAR(50),
    confidence NUMERIC(5,4),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS warranty_claims (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    claim_date DATE,
    status VARCHAR(50),
    cost NUMERIC(10,2),
    source_record_id VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS service_records (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    service_date DATE,
    description TEXT,
    technician_notes TEXT,
    source_record_id VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS product_returns (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    return_date DATE,
    reason VARCHAR(150),
    source_record_id VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS failures (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    complaint_id INTEGER REFERENCES complaints(id),
    failure_date DATE,
    description TEXT,
    source_record_id VARCHAR(100) UNIQUE
);

CREATE TABLE IF NOT EXISTS failure_causes (
    id SERIAL PRIMARY KEY,
    failure_id INTEGER REFERENCES failures(id),
    cause_name VARCHAR(150),
    probability NUMERIC(5,2),
    confidence NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(id),
    predicted_cause VARCHAR(150),
    probability NUMERIC(5,2),
    evidence_summary TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50),
    product_id INTEGER REFERENCES products(id),
    message TEXT,
    severity VARCHAR(20),
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sync_logs (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50),
    last_synced_at TIMESTAMP,
    records_processed INTEGER,
    status VARCHAR(20)
);