CREATE TABLE IF NOT EXISTS skill_embeddings (
    skill_text   TEXT    NOT NULL,
    model        TEXT    NOT NULL DEFAULT 'text-embedding-3-small',
    embedding    BLOB    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (skill_text, model)
);
