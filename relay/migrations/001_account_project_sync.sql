-- First-party Godot account and project sync schema for Neon PostgreSQL.
-- Apply only after reviewing the migration against the deployed database.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE,
  display_name TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS devices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  device_label TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('linux','android')),
  credential_hash BYTEA NOT NULL UNIQUE,
  credential_version INTEGER NOT NULL DEFAULT 1,
  last_seen_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS devices_account_active_idx ON devices(account_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS enrollment_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  ticket_hash BYTEA NOT NULL UNIQUE,
  intended_platform TEXT NOT NULL CHECK (intended_platform IN ('linux','android')),
  expires_at TIMESTAMPTZ NOT NULL,
  redeemed_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS enrollment_tickets_expiry_idx ON enrollment_tickets(expires_at);

CREATE TABLE IF NOT EXISTS device_pair_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  initiating_device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  code_hash BYTEA NOT NULL UNIQUE,
  intended_platform TEXT NOT NULL CHECK (intended_platform IN ('linux','android')),
  device_label TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  approved_at TIMESTAMPTZ,
  consumed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  engine_version TEXT NOT NULL DEFAULT '4.7.2',
  head_revision BIGINT NOT NULL DEFAULT 0 CHECK (head_revision >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS projects_account_updated_idx ON projects(account_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS project_members (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner','editor','viewer')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, account_id)
);

CREATE TABLE IF NOT EXISTS project_revisions (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  revision BIGINT NOT NULL CHECK (revision > 0),
  parent_revision BIGINT NOT NULL CHECK (parent_revision >= 0),
  author_device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
  manifest_sha256 CHAR(64) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, revision)
);

CREATE TABLE IF NOT EXISTS project_files (
  project_id UUID NOT NULL,
  revision BIGINT NOT NULL,
  relative_path TEXT NOT NULL,
  file_sha256 CHAR(64),
  byte_size BIGINT NOT NULL DEFAULT 0 CHECK (byte_size >= 0),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  content_manifest JSONB NOT NULL DEFAULT '[]'::jsonb,
  PRIMARY KEY (project_id, revision, relative_path),
  FOREIGN KEY (project_id, revision) REFERENCES project_revisions(project_id, revision) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS project_files_path_history_idx ON project_files(project_id, relative_path, revision DESC);

CREATE TABLE IF NOT EXISTS project_changes (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  sequence BIGINT GENERATED ALWAYS AS IDENTITY,
  revision BIGINT NOT NULL,
  change_type TEXT NOT NULL CHECK (change_type IN ('create','update','rename','delete','conflict')),
  relative_path TEXT NOT NULL,
  device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, sequence),
  FOREIGN KEY (project_id, revision) REFERENCES project_revisions(project_id, revision) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS device_sync_cursors (
  device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  last_sequence BIGINT NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (device_id, project_id)
);

CREATE TABLE IF NOT EXISTS project_blobs (
  sha256 CHAR(64) PRIMARY KEY,
  object_key TEXT NOT NULL UNIQUE,
  byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
  verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
