-- Initialize database for WeKnora
-- Creates necessary schemas and extensions for pgvector

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for WeKnora if not exists
CREATE SCHEMA IF NOT EXISTS public;

-- Grant privileges
GRANT ALL PRIVILEGES ON SCHEMA public TO weknora;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO weknora;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO weknora;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO weknora;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO weknora;
