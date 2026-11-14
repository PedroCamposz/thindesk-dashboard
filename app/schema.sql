-- =============================================================
-- Thindesk Insight - Modelo de dados (SQLite)
-- Autor: Pedro Henrique Campos
-- =============================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS consideracoes_tecnicas;
DROP TABLE IF EXISTS chamados;
DROP TABLE IF EXISTS tecnicos;
DROP TABLE IF EXISTS tipos_chamado;
DROP TABLE IF EXISTS setores;

-- Setores (departamentos) que abrem chamados
CREATE TABLE setores (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT NOT NULL UNIQUE
);

-- Tipos / categorias de chamado, cada um com SLA base em horas
CREATE TABLE tipos_chamado (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nome       TEXT    NOT NULL UNIQUE,
    sla_horas  INTEGER NOT NULL CHECK (sla_horas > 0)
);

-- Técnicos responsáveis pelo atendimento
CREATE TABLE tecnicos (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nome   TEXT NOT NULL,
    nivel  TEXT NOT NULL CHECK (nivel IN ('N1', 'N2', 'N3')),
    ativo  INTEGER NOT NULL DEFAULT 1
);

-- Chamados técnicos
CREATE TABLE chamados (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo        TEXT    NOT NULL,
    descricao     TEXT,
    tipo_id       INTEGER NOT NULL REFERENCES tipos_chamado(id),
    setor_id      INTEGER NOT NULL REFERENCES setores(id),
    tecnico_id    INTEGER REFERENCES tecnicos(id),
    prioridade    TEXT    NOT NULL CHECK (prioridade IN ('baixa', 'media', 'alta', 'critica')),
    status        TEXT    NOT NULL CHECK (status IN ('aberto', 'em_andamento', 'aguardando', 'resolvido', 'cancelado')),
    aberto_em     TEXT    NOT NULL,            -- 'YYYY-MM-DD HH:MM:SS'
    prazo_sla     TEXT    NOT NULL,            -- data/hora limite do SLA
    resolvido_em  TEXT,                        -- preenchido quando status = resolvido
    satisfacao    INTEGER CHECK (satisfacao BETWEEN 1 AND 5),
    atualizado_em TEXT    NOT NULL
);

-- Considerações técnicas (pareceres) registradas pelos técnicos
CREATE TABLE consideracoes_tecnicas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chamado_id  INTEGER NOT NULL REFERENCES chamados(id) ON DELETE CASCADE,
    tecnico_id  INTEGER NOT NULL REFERENCES tecnicos(id),
    texto       TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL
);

CREATE INDEX idx_chamados_aberto_em    ON chamados(aberto_em);
CREATE INDEX idx_chamados_resolvido_em ON chamados(resolvido_em);
CREATE INDEX idx_chamados_status       ON chamados(status);
CREATE INDEX idx_chamados_tipo         ON chamados(tipo_id);
CREATE INDEX idx_chamados_tecnico      ON chamados(tecnico_id);
CREATE INDEX idx_consid_chamado        ON consideracoes_tecnicas(chamado_id);
