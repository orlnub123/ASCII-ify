CREATE SCHEMA statistics
    CREATE TABLE commands (
        id serial PRIMARY KEY,
        user_id bigint NOT NULL,
        channel_id bigint NOT NULL,
        guild_id bigint,
        command text NOT NULL,
        cog text DEFAULT NULL,
        completed boolean DEFAULT FALSE NOT NULL,
        used_at timestamptz DEFAULT now() NOT NULL
    )
    CREATE TABLE errors (
        id serial PRIMARY KEY,
        command integer REFERENCES commands NOT NULL,
        type text NOT NULL
    )
    CREATE TABLE api_latencies (
        id serial PRIMARY KEY,
        latency double precision NOT NULL CHECK (latency > 0),
        measured_at timestamptz DEFAULT now() NOT NULL
    )
    CREATE TABLE gateway_latencies (
        id serial PRIMARY KEY,
        latency double precision NOT NULL CHECK (latency > 0),
        measured_at timestamptz DEFAULT now() NOT NULL
    );
