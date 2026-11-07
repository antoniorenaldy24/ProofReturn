"""Canonical 20-table PostgreSQL DDL and constraint definitions (Section 10.4, Section 30)."""

from __future__ import annotations

CANONICAL_TABLES: tuple[str, ...] = (
    "merchants",
    "staff_users",
    "shopper_accounts",
    "identity_link_events",
    "policies",
    "passports",
    "passport_events",
    "serial_registry",
    "orders",
    "order_items",
    "returns",
    "return_evidence",
    "assessments",
    "decisions",
    "keep_offers",
    "refund_actions",
    "custody_events",
    "webhook_events",
    "reviews",
    "appeals",
    "resale_listings",
    "agent_tokens",
)

INITIAL_MIGRATION_SQL = """-- ProofReturn SSOT v1.2.1 Canonical Schema (Section 10.4 & Section 30)

CREATE TABLE merchants (
    merchant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    instant_exposure_cap_minor BIGINT NOT NULL CHECK (instant_exposure_cap_minor >= 0),
    outstanding_instant_exposure_minor BIGINT NOT NULL DEFAULT 0 CHECK (outstanding_instant_exposure_minor >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE staff_users (
    staff_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    role TEXT NOT NULL,
    email_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE shopper_accounts (
    account_id TEXT PRIMARY KEY,
    identity_group_id TEXT NOT NULL,
    trust_tier TEXT NOT NULL DEFAULT 'NEW',
    cusum_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE identity_link_events (
    link_event_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES shopper_accounts(account_id),
    identity_group_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_hmac TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE policies (
    policy_version TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    jurisdiction TEXT NOT NULL,
    config_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE passports (
    passport_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    sku TEXT NOT NULL,
    tier TEXT NOT NULL,
    origin_grade TEXT NOT NULL,
    serial_commitment TEXT,
    head_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE passport_events (
    event_id TEXT PRIMARY KEY,
    passport_id TEXT NOT NULL REFERENCES passports(passport_id),
    seq_no INTEGER NOT NULL,
    prev_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    signature TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (passport_id, seq_no)
);

CREATE TABLE serial_registry (
    serial_commitment TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    passport_id TEXT NOT NULL REFERENCES passports(passport_id),
    order_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    account_id TEXT NOT NULL REFERENCES shopper_accounts(account_id),
    policy_version TEXT NOT NULL REFERENCES policies(policy_version),
    paypal_order_id TEXT NOT NULL,
    capture_id TEXT NOT NULL,
    capture_amount_minor BIGINT NOT NULL CHECK (capture_amount_minor >= 0),
    confirmed_refunded_minor BIGINT NOT NULL DEFAULT 0 CHECK (confirmed_refunded_minor >= 0),
    pending_refunded_minor BIGINT NOT NULL DEFAULT 0 CHECK (pending_refunded_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_inv01_cumulative_refund CHECK (
        confirmed_refunded_minor + pending_refunded_minor <= capture_amount_minor
    )
);

CREATE TABLE order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    passport_id TEXT REFERENCES passports(passport_id),
    sku TEXT NOT NULL,
    price_minor BIGINT NOT NULL CHECK (price_minor >= 0)
);

CREATE TABLE returns (
    return_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id TEXT NOT NULL REFERENCES order_items(order_item_id),
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    state TEXT NOT NULL,
    lane TEXT NOT NULL,
    timing TEXT NOT NULL,
    declared_grade TEXT,
    disputed BOOLEAN NOT NULL DEFAULT FALSE,
    appeal_open BOOLEAN NOT NULL DEFAULT FALSE,
    refiled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_returns_one_active_per_order_item
    ON returns(order_item_id)
    WHERE state NOT IN ('CLOSED', 'CANCELLED');

CREATE TABLE return_evidence (
    evidence_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    evidence_sha256 TEXT NOT NULL,
    nonce_return TEXT NOT NULL,
    encrypted_blob_uri TEXT,
    shredded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE assessments (
    assessment_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    predicted_grade TEXT NOT NULL,
    conformal_set JSONB NOT NULL,
    replay_label TEXT NOT NULL,
    forensic_flags JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    policy_version TEXT NOT NULL REFERENCES policies(policy_version),
    lane TEXT NOT NULL,
    timing TEXT NOT NULL,
    audit_probability DOUBLE PRECISION NOT NULL,
    x_minor BIGINT NOT NULL CHECK (x_minor >= 0),
    checkin_minor BIGINT NOT NULL CHECK (checkin_minor >= 0),
    holdback_minor BIGINT NOT NULL CHECK (holdback_minor >= 0),
    explanation_json JSONB NOT NULL CHECK (jsonb_typeof(explanation_json) = 'object'),
    signature TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE keep_offers (
    offer_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL UNIQUE REFERENCES returns(return_id),
    amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
    status TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE refund_actions (
    request_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    decision_id TEXT NOT NULL REFERENCES decisions(decision_id),
    tranche TEXT NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor >= 0),
    status TEXT NOT NULL,
    paypal_refund_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (decision_id, tranche)
);

CREATE TABLE custody_events (
    custody_event_id TEXT PRIMARY KEY,
    passport_id TEXT NOT NULL REFERENCES passports(passport_id),
    return_id TEXT REFERENCES returns(return_id),
    interval_name TEXT NOT NULL,
    grade_observed TEXT NOT NULL,
    weight_g INTEGER NOT NULL,
    seal_intact BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE webhook_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    reviewer_id TEXT NOT NULL REFERENCES staff_users(staff_id),
    verified_grade TEXT NOT NULL,
    outcome TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE appeals (
    appeal_id TEXT PRIMARY KEY,
    return_id TEXT NOT NULL REFERENCES returns(return_id),
    original_reviewer_id TEXT NOT NULL REFERENCES staff_users(staff_id),
    appeal_reviewer_id TEXT REFERENCES staff_users(staff_id),
    status TEXT NOT NULL,
    topup_amount_minor BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_appeal_different_reviewer CHECK (
        appeal_reviewer_id IS NULL OR appeal_reviewer_id <> original_reviewer_id
    )
);

CREATE TABLE resale_listings (
    listing_id TEXT PRIMARY KEY,
    passport_id TEXT NOT NULL REFERENCES passports(passport_id) ON DELETE RESTRICT,
    verified_grade TEXT NOT NULL DEFAULT 'B',
    price_minor BIGINT NOT NULL CHECK (price_minor >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    resale_order_id TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE agent_tokens (
    token_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id) ON DELETE RESTRICT,
    merchant_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    scopes TEXT NOT NULL,
    agent_label TEXT NOT NULL DEFAULT 'assistant',
    signature_hash TEXT NOT NULL DEFAULT '',
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at BIGINT NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE scheduler_leases (
    lease_name TEXT PRIMARY KEY,
    holder_id TEXT NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- INV-09 Append-only trigger for passport_events, decisions, and custody_events
CREATE OR REPLACE FUNCTION forbid_mutation_on_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'INV-09 violation: append-only table cannot be updated or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_passport_events_append_only
    BEFORE UPDATE OR DELETE ON passport_events
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation_on_append_only();
"""


def get_initial_migration_sql() -> str:
    """Return the canonical PostgreSQL DDL migration string."""
    return INITIAL_MIGRATION_SQL
