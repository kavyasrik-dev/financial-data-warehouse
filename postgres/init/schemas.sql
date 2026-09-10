CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;

GRANT USAGE ON SCHEMA raw, staging, warehouse, analytics TO warehouse_app;
GRANT CREATE ON SCHEMA staging, warehouse, analytics TO warehouse_app;

CREATE TABLE IF NOT EXISTS raw.ingestion_batches (
    load_batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system VARCHAR(64) NOT NULL,
    source_name TEXT,
    pipeline_name VARCHAR(128) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'started',
    records_loaded BIGINT NOT NULL DEFAULT 0,
    error_message TEXT,
    CONSTRAINT chk_ingestion_batches_status
        CHECK (status IN ('started', 'completed', 'failed'))
);

CREATE TABLE IF NOT EXISTS raw.customers (
    source_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    customer_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    country TEXT NOT NULL,
    customer_status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    source_system VARCHAR(64) NOT NULL DEFAULT 'generated',
    source_file TEXT,
    source_extracted_at TIMESTAMPTZ,
    source_record_hash TEXT,
    load_batch_id UUID NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_customers_load_batch
        FOREIGN KEY (load_batch_id) REFERENCES raw.ingestion_batches(load_batch_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS raw.cards (
    source_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_id VARCHAR(64) NOT NULL,
    customer_id VARCHAR(64) NOT NULL,
    card_number TEXT NOT NULL,
    card_type VARCHAR(32) NOT NULL,
    expiry_date DATE NOT NULL,
    card_status VARCHAR(32) NOT NULL,
    source_system VARCHAR(64) NOT NULL DEFAULT 'generated',
    source_file TEXT,
    source_extracted_at TIMESTAMPTZ,
    source_record_hash TEXT,
    load_batch_id UUID NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_cards_load_batch
        FOREIGN KEY (load_batch_id) REFERENCES raw.ingestion_batches(load_batch_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS raw.transactions (
    source_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL,
    customer_id VARCHAR(64) NOT NULL,
    card_id VARCHAR(64) NOT NULL,
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    amount NUMERIC(18, 2) NOT NULL,
    currency CHAR(3) NOT NULL,
    merchant_name TEXT NOT NULL,
    merchant_category VARCHAR(128) NOT NULL,
    transaction_type VARCHAR(32) NOT NULL,
    transaction_status VARCHAR(32) NOT NULL,
    source_system VARCHAR(64) NOT NULL DEFAULT 'generated',
    source_file TEXT,
    source_extracted_at TIMESTAMPTZ,
    source_record_hash TEXT,
    load_batch_id UUID NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_transactions_load_batch
        FOREIGN KEY (load_batch_id) REFERENCES raw.ingestion_batches(load_batch_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    customer_name_masked TEXT NOT NULL,
    email_masked TEXT NOT NULL,
    phone_masked TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    country TEXT NOT NULL,
    customer_status VARCHAR(32) NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ NOT NULL DEFAULT '9999-12-31 00:00:00+00',
    is_current BOOLEAN NOT NULL DEFAULT true,
    record_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (customer_id, effective_from)
);

CREATE TABLE IF NOT EXISTS warehouse.dim_card (
    card_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    card_id VARCHAR(64) NOT NULL UNIQUE,
    customer_id VARCHAR(64) NOT NULL,
    masked_card_number VARCHAR(32) NOT NULL,
    card_type VARCHAR(32) NOT NULL,
    expiry_date DATE NOT NULL,
    card_status VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    year INTEGER NOT NULL,
    week INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(16) NOT NULL,
    month_name VARCHAR(16) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.fact_transactions (
    transaction_sk BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL UNIQUE,
    customer_sk BIGINT NOT NULL REFERENCES warehouse.dim_customer(customer_sk),
    card_sk BIGINT NOT NULL REFERENCES warehouse.dim_card(card_sk),
    date_key INTEGER NOT NULL REFERENCES warehouse.dim_date(date_key),
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    transaction_type VARCHAR(32) NOT NULL,
    transaction_status VARCHAR(32) NOT NULL,
    amount NUMERIC(18, 2) NOT NULL CHECK (amount >= 0),
    currency CHAR(3) NOT NULL,
    merchant_name TEXT NOT NULL,
    merchant_category VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_customers_customer_id ON raw.customers (customer_id);
CREATE INDEX IF NOT EXISTS idx_raw_customers_batch_id ON raw.customers (load_batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_customers_source_record_hash ON raw.customers (source_record_hash);
CREATE INDEX IF NOT EXISTS idx_raw_cards_customer_id ON raw.cards (customer_id);
CREATE INDEX IF NOT EXISTS idx_raw_cards_card_id ON raw.cards (card_id);
CREATE INDEX IF NOT EXISTS idx_raw_cards_batch_id ON raw.cards (load_batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_cards_source_record_hash ON raw.cards (source_record_hash);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_transaction_id ON raw.transactions (transaction_id);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_customer_id ON raw.transactions (customer_id);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_card_id ON raw.transactions (card_id);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_timestamp ON raw.transactions (transaction_timestamp);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_batch_id ON raw.transactions (load_batch_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_transactions_source_record_hash ON raw.transactions (source_record_hash);
CREATE INDEX IF NOT EXISTS idx_dim_customer_business_current ON warehouse.dim_customer (customer_id, is_current);
CREATE INDEX IF NOT EXISTS idx_fact_transactions_date_key ON warehouse.fact_transactions (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_transactions_customer_sk ON warehouse.fact_transactions (customer_sk);
CREATE INDEX IF NOT EXISTS idx_fact_transactions_card_sk ON warehouse.fact_transactions (card_sk);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA raw, staging, warehouse, analytics TO warehouse_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw, staging, warehouse, analytics TO warehouse_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA staging, warehouse, analytics
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO warehouse_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA staging, warehouse, analytics
    GRANT USAGE, SELECT ON SEQUENCES TO warehouse_app;

ALTER ROLE warehouse_app IN DATABASE financial_warehouse
    SET search_path = analytics, warehouse, staging, raw, public;
