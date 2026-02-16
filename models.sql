-- Automated Payment Reconciliation System - Database Schema

-- Payments table (ledger entries)
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    amount NUMERIC(15, 2) NOT NULL,
    date DATE NOT NULL,
    reference TEXT,
    payee TEXT,
    raw JSONB,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bank transactions table
CREATE TABLE IF NOT EXISTS bank_transactions (
    id SERIAL PRIMARY KEY,
    amount NUMERIC(15, 2) NOT NULL,
    date DATE NOT NULL,
    reference TEXT,
    payee TEXT,
    raw JSONB,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Matches table (reconciliation results)
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    payment_id INTEGER REFERENCES payments(id) ON DELETE CASCADE,
    bank_txn_id INTEGER REFERENCES bank_transactions(id) ON DELETE CASCADE,
    match_score INTEGER NOT NULL,
    match_type TEXT NOT NULL,
    matched_at TIMESTAMPTZ DEFAULT NOW(),
    reviewer TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    UNIQUE(payment_id, bank_txn_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_payments_amount ON payments(amount);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_bank_amount ON bank_transactions(amount);
CREATE INDEX IF NOT EXISTS idx_bank_date ON bank_transactions(date);
CREATE INDEX IF NOT EXISTS idx_bank_status ON bank_transactions(status);
CREATE INDEX IF NOT EXISTS idx_matches_payment_id ON matches(payment_id);
CREATE INDEX IF NOT EXISTS idx_matches_bank_txn_id ON matches(bank_txn_id);



