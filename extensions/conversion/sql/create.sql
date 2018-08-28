CREATE SCHEMA conversion
    CREATE TABLE guilds (
        id bigint PRIMARY KEY,
        pm boolean DEFAULT TRUE NOT NULL
    );
