-- schema.sql (Postgres)
CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  balance NUMERIC DEFAULT 0,
  pending_balance NUMERIC DEFAULT 0,
  total_earned NUMERIC DEFAULT 0,
  referrals_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS referrals (
  id SERIAL PRIMARY KEY,
  referrer_id BIGINT REFERENCES users(id),
  referred_id BIGINT REFERENCES users(id),
  reward_amount NUMERIC,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tasks (
  id SERIAL PRIMARY KEY,
  name TEXT,
  type TEXT,
  reward NUMERIC,
  metadata JSONB,
  active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS task_completions (
  id SERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  task_id INTEGER REFERENCES tasks(id),
  status TEXT, -- pending, verified, rejected
  proof TEXT,
  reward NUMERIC,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ads_viewed (
  id SERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  ad_id TEXT,
  reward NUMERIC,
  viewed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS withdrawals (
  id SERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  amount NUMERIC,
  method TEXT,
  account_info JSONB,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT now()
);
