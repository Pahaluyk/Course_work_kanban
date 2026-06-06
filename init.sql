CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20)  NOT NULL DEFAULT 'developer'
                               CHECK (role IN ('manager','developer','observer')),
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    owner_id    UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_members (
    id         UUID      PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID      NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id    UUID      NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    joined_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    status      VARCHAR(20)  NOT NULL DEFAULT 'backlog'
                             CHECK (status IN ('backlog','todo','in_progress','review','done')),
    priority    VARCHAR(10)  NOT NULL DEFAULT 'medium'
                             CHECK (priority IN ('low','medium','high')),
    due_date    DATE,
    project_id  UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    assignee_id UUID         REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attachments (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    filename    VARCHAR(255) NOT NULL,
    filepath    TEXT         NOT NULL,
    task_id     UUID         NOT NULL REFERENCES tasks(id)    ON DELETE CASCADE,
    uploaded_by UUID         NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    uploaded_at TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_project    ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee   ON tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_members_project  ON project_members(project_id);
CREATE INDEX IF NOT EXISTS idx_attachments_task ON attachments(task_id);