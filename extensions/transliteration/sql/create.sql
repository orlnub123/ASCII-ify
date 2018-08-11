CREATE TYPE transliteration_type AS ENUM ('username', 'nickname');
CREATE SCHEMA transliteration
    CREATE TABLE users (
        id bigint PRIMARY KEY
    )
    CREATE TABLE guilds (
        id bigint PRIMARY KEY,
        automate boolean DEFAULT FALSE NOT NULL
    )
    CREATE TABLE members (
        user_id bigint REFERENCES users ON DELETE CASCADE,
        guild_id bigint REFERENCES guilds ON DELETE CASCADE,
        PRIMARY KEY (user_id, guild_id)
    )
    CREATE TABLE usernames (
        id serial PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES users,
        username varchar(32) NOT NULL,
        created_at timestamptz DEFAULT now() NOT NULL
    )
    CREATE TABLE nicknames (
        id serial PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES users,
        guild_id bigint NOT NULL REFERENCES guilds,
        nickname varchar(32) NOT NULL,
        ignore boolean DEFAULT FALSE NOT NULL,
        created_at timestamptz DEFAULT now() NOT NULL,
        FOREIGN KEY (user_id, guild_id) REFERENCES members (user_id, guild_id)
    )
    CREATE TABLE transliterations (
        id serial PRIMARY KEY,
        user_id bigint NOT NULL REFERENCES users,
        guild_id bigint NOT NULL REFERENCES guilds,
        type transliteration_type NOT NULL,
        original varchar(32) NOT NULL,
        manual boolean NOT NULL,
        created_at timestamptz DEFAULT now() NOT NULL,
        FOREIGN KEY (user_id, guild_id) REFERENCES members (user_id, guild_id)
    );
