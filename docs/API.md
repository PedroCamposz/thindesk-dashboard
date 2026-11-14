# Documentação da API — Thindesk Insight

**Autor:** Pedro Henrique Campos · **Versão:** 1.0.0 · **Base URL:** `http://localhost:5000/api/v1`

A API é REST, recebe e devolve **JSON (UTF-8)** e está ligada a um banco **SQLite**. Todos os exemplos abaixo são respostas reais geradas pela própria API (com a data de referência fixada em 14/11/2026 12:00).

## Sumário

| # | Método | Endpoint | Requisito | Descrição |
|---|---|---|---|---|
| 1 | GET | `/health` | RNF | Verifica se a API e o banco estão no ar |
| 2 | GET | `/filtros` | RF05 | Opções para montar os filtros (tipos, técnicos, setores, status, prioridades) |
| 3 | GET | `/indicadores` | RF01 | Indicadores gerais (totais, backlog, SLA, tempo médio, satisfação) |
| 4 | GET | `/chamados/periodo` | RF02 | Série temporal de abertos × resolvidos (dia/semana/mês) |
| 5 | GET | `/chamados/situacao` | RF03 | Quantidade e % por status + fila por prioridade |
| 6 | GET | `/tipos/ranking` | RF04 | Tipos de chamado mais atendidos |
| 7 | GET | `/tecnicos/desempenho` | RF01 | Desempenho por técnico |
| 8 | GET | `/insights/saude` | Diferencial | Índice de Saúde da Operação (0–100) |
| 9 | GET | `/insights/sla-risco` | Diferencial | Radar de SLA: chamados da fila estourados ou prestes a estourar |
| 10 | GET | `/insights/mapa-calor` | Diferencial | Demanda por dia da semana × hora |
| 11 | GET | `/chamados` | RF05/RF06 | Lista paginada, com busca, filtros e ordenação |
| 12 | GET | `/chamados/{id}` | RF03 | Detalhe do chamado + considerações técnicas |
| 13 | POST | `/chamados` | RF07 | Abre um chamado (SLA calculado automaticamente) |
| 14 | PATCH | `/chamados/{id}/status` | RF07 | Atualiza o status (com máquina de estados) |
| 15 | POST | `/chamados/{id}/consideracoes` | RF07 | Registra uma consideração técnica |

---

## Padrões gerais

### Formato de sucesso
```json
{
  "dados": { "...": "conteúdo do endpoint" },
  "meta": { "gerado_em": "2026-11-14 12:00:00", "filtros_aplicados": { "status": ["resolvido"] } }
}
```

### Formato de erro (todos os endpoints)
```json
{ "erro": { "codigo": "PARAMETRO_INVALIDO", "mensagem": "Texto em português para o usuário.", "detalhes": { } } }
```

| HTTP | `codigo` | Quando acontece |
|---|---|---|
| 400 | `PARAMETRO_INVALIDO` | Filtro/parâmetro de query inválido (data fora do formato, status inexistente, id que não existe, limite fora da faixa…) |
| 400 | `JSON_INVALIDO` | Corpo de POST/PATCH ausente ou que não é um objeto JSON |
| 404 | `NAO_ENCONTRADO` | Chamado não existe |
| 404 | `ROTA_NAO_ENCONTRADA` | Endpoint inexistente |
| 405 | `METODO_NAO_PERMITIDO` | Método HTTP errado (ex.: `DELETE /indicadores`) |
| 409 | `TRANSICAO_INVALIDA` | Mudança de status não permitida pela regra de negócio |
| 422 | `VALIDACAO` | Corpo JSON com campos inválidos (lista cada campo em `detalhes`) |
| 500 | `ERRO_INTERNO` | Falha inesperada (registrada no log do servidor) |

### Filtros comuns (query string) — RF05

Aceitos em `/indicadores`, `/chamados/periodo`, `/chamados/situacao`, `/tipos/ranking`, `/tecnicos/desempenho`, `/insights/*` e `/chamados`.

| Parâmetro | Tipo | Exemplo | Regra |
|---|---|---|---|
| `data_inicio` | data `AAAA-MM-DD` | `2026-10-01` | Filtra pela data de abertura (inclusive) |
| `data_fim` | data `AAAA-MM-DD` | `2026-10-31` | Inclusive; não pode ser menor que `data_inicio` |
| `status` | lista separada por vírgula | `aberto,em_andamento` | `aberto`, `em_andamento`, `aguardando`, `resolvido`, `cancelado` |
| `prioridade` | lista separada por vírgula | `alta,critica` | `baixa`, `media`, `alta`, `critica` |
| `tipo_id` | inteiro ≥ 1 | `4` | Precisa existir |
| `tecnico_id` | inteiro ≥ 1 | `3` | Precisa existir |
| `setor_id` | inteiro ≥ 1 | `2` | Precisa existir |

> Segurança: todos os valores vão para o SQL como **parâmetros** (`?`), nunca concatenados — não há SQL injection (há teste automatizado para isso).

---

## 1. `GET /health`
Verifica se a API está no ar e se o banco responde.

```bash
curl http://localhost:5000/api/v1/health
```
```json
{ "dados": { "status": "ok", "banco": "conectado", "versao": "1.0.0" }, "meta": { "gerado_em": "2026-11-14 12:00:00" } }
```
**Erros:** `500 ERRO_INTERNO` se o banco estiver indisponível.

---

## 2. `GET /filtros`
Retorna as opções que o dashboard usa para preencher os campos de filtro.

```bash
curl http://localhost:5000/api/v1/filtros
```
```json
{
  "dados": {
    "tipos": [ { "id": 1, "nome": "Acesso e Senhas", "sla_horas": 4 }, { "id": 4, "nome": "Hardware", "sla_horas": 24 } ],
    "tecnicos": [ { "id": 1, "nome": "Ana Souza", "nivel": "N2" } ],
    "setores": [ { "id": 7, "nome": "Atendimento" } ],
    "status": [ { "valor": "aberto", "rotulo": "Aberto" } ],
    "prioridades": [ "baixa", "media", "alta", "critica" ],
    "periodo_disponivel": { "data_inicio": "2026-05-19", "data_fim": "2026-11-14" }
  }
}
```
*(listas resumidas)* · **Erros:** nenhum específico.

---

## 3. `GET /indicadores` — RF01
Indicadores gerais. Quando `data_inicio` e `data_fim` são enviados, também compara com o **período anterior de mesmo tamanho**.

| Campo da resposta | Significado |
|---|---|
| `total_chamados` | Chamados abertos no período/filtro |
| `abertos`, `em_andamento`, `aguardando`, `resolvidos`, `cancelados` | Contagem por status |
| `backlog` | Chamados ainda na fila (aberto + em andamento + aguardando) |
| `atrasados` | Chamados da fila com prazo de SLA já vencido |
| `taxa_resolucao_pct` | resolvidos ÷ total × 100 |
| `tempo_medio_resolucao_horas` | Média (resolvido_em − aberto_em) dos resolvidos |
| `taxa_cumprimento_sla_pct` | % dos resolvidos dentro do prazo |
| `satisfacao_media` | Média das notas 1–5 |
| `variacao_periodo_anterior_pct` | Variação do total vs. período anterior (`null` se não houver base) |

```bash
curl "http://localhost:5000/api/v1/indicadores?data_inicio=2026-10-16&data_fim=2026-11-14"
```
```json
{
  "dados": {
    "total_chamados": 156, "abertos": 10, "em_andamento": 13, "aguardando": 5,
    "resolvidos": 124, "cancelados": 4, "backlog": 28, "atrasados": 10,
    "taxa_resolucao_pct": 79.5, "tempo_medio_resolucao_horas": 6.1,
    "taxa_cumprimento_sla_pct": 90.3, "satisfacao_media": 4.18,
    "variacao_periodo_anterior_pct": 0.0, "total_periodo_anterior": 156
  },
  "meta": { "gerado_em": "2026-11-14 12:00:00", "filtros_aplicados": { "data_inicio": "2026-10-16", "data_fim": "2026-11-14" } }
}
```
**Erros:** `400 PARAMETRO_INVALIDO` (ex.: `?data_inicio=14/11/2026`):
```json
{ "erro": { "codigo": "PARAMETRO_INVALIDO", "mensagem": "'data_inicio' deve estar no formato AAAA-MM-DD.", "detalhes": { "parametro": "data_inicio", "valor": "14/11/2026" } } }
```

---

## 4. `GET /chamados/periodo` — RF02
Série temporal para o gráfico. Dias/semanas/meses sem chamados aparecem com **zero** (o gráfico não “pula” datas).

| Parâmetro | Padrão | Valores |
|---|---|---|
| `agrupamento` | `dia` | `dia`, `semana` (chave = segunda-feira da semana), `mes` (`AAAA-MM`) |
| `data_inicio` / `data_fim` | últimos 30 dias | intervalo máximo de 2 anos |
| + filtros comuns | | |

```bash
curl "http://localhost:5000/api/v1/chamados/periodo?agrupamento=semana&data_inicio=2026-10-26&data_fim=2026-11-14"
```
```json
{
  "dados": {
    "agrupamento": "semana", "data_inicio": "2026-10-26", "data_fim": "2026-11-14",
    "totais": { "abertos": 111, "resolvidos": 80 },
    "serie": [
      { "periodo": "2026-10-26", "abertos": 31, "resolvidos": 29, "saldo": 2,  "taxa_sla_pct": 93.1, "tempo_medio_resolucao_horas": 6.8 },
      { "periodo": "2026-11-02", "abertos": 22, "resolvidos": 22, "saldo": 0,  "taxa_sla_pct": 95.5, "tempo_medio_resolucao_horas": 5.9 },
      { "periodo": "2026-11-09", "abertos": 58, "resolvidos": 29, "saldo": 29, "taxa_sla_pct": 86.2, "tempo_medio_resolucao_horas": 6.6 }
    ]
  }
}
```
**Erros:** `400` para `agrupamento` inválido (`"'agrupamento' deve ser 'dia', 'semana' ou 'mes'."`), datas inválidas ou intervalo > 2 anos.

---

## 5. `GET /chamados/situacao` — RF03
Distribuição por status (sempre devolve os 5 status, mesmo com zero) e a fila separada por prioridade.

```bash
curl "http://localhost:5000/api/v1/chamados/situacao?data_inicio=2026-10-16&data_fim=2026-11-14"
```
```json
{
  "dados": {
    "total": 156,
    "status": [
      { "status": "aberto", "rotulo": "Aberto", "quantidade": 10, "percentual": 6.4 },
      { "status": "em_andamento", "rotulo": "Em andamento", "quantidade": 13, "percentual": 8.3 },
      { "status": "aguardando", "rotulo": "Aguardando usuário", "quantidade": 5, "percentual": 3.2 },
      { "status": "resolvido", "rotulo": "Resolvido", "quantidade": 124, "percentual": 79.5 },
      { "status": "cancelado", "rotulo": "Cancelado", "quantidade": 4, "percentual": 2.6 }
    ],
    "backlog_por_prioridade": { "baixa": 7, "media": 10, "alta": 9, "critica": 2 }
  }
}
```
**Erros:** `400 PARAMETRO_INVALIDO` nos filtros.

---

## 6. `GET /tipos/ranking` — RF04
Ranking dos tipos mais atendidos, com participação, tempo médio e cumprimento de SLA de cada tipo.

| Parâmetro | Padrão | Faixa |
|---|---|---|
| `limite` | 5 | 1 a 50 |

```bash
curl "http://localhost:5000/api/v1/tipos/ranking?limite=3"
```
```json
{
  "dados": {
    "total_geral": 928,
    "ranking": [
      { "posicao": 1, "tipo_id": 1, "tipo": "Acesso e Senhas", "sla_base_horas": 4, "total": 204, "resolvidos": 195, "participacao_pct": 22.0, "tempo_medio_resolucao_horas": 2.7, "taxa_cumprimento_sla_pct": 81.0 },
      { "posicao": 2, "tipo_id": 3, "tipo": "Software e Instalação", "sla_base_horas": 16, "total": 146, "resolvidos": 139, "participacao_pct": 15.7, "tempo_medio_resolucao_horas": 10.1, "taxa_cumprimento_sla_pct": 88.5 },
      { "posicao": 3, "tipo_id": 4, "tipo": "Hardware", "sla_base_horas": 24, "total": 135, "resolvidos": 125, "participacao_pct": 14.5, "tempo_medio_resolucao_horas": 12.9, "taxa_cumprimento_sla_pct": 84.8 }
    ]
  }
}
```
**Erros:** `400` se `limite` não for inteiro entre 1 e 50.

---

## 7. `GET /tecnicos/desempenho`
```bash
curl "http://localhost:5000/api/v1/tecnicos/desempenho?tecnico_id=3"
```
```json
{
  "dados": [
    { "tecnico_id": 3, "nome": "Carla Mendes", "nivel": "N3", "atribuidos": 161, "resolvidos": 149, "em_fila": 7,
      "tempo_medio_resolucao_horas": 4.5, "taxa_cumprimento_sla_pct": 95.3, "satisfacao_media": 4.36 }
  ],
  "meta": { "gerado_em": "2026-11-14 12:00:00", "filtros_aplicados": { "tecnico_id": 3 } }
}
```
**Erros:** `400` nos filtros (ex.: `tecnico_id=999` → `"'tecnico_id' = 999 não existe."`).

---

## 8. `GET /insights/saude` — diferencial
**Índice de Saúde da Operação** (0 a 100) = `0,4 × SLA cumprido` + `0,3 × satisfação normalizada ((nota−1)/4 × 100)` + `0,3 × % da fila sem atraso`.
Classificação: **Excelente** ≥ 85 · **Boa** ≥ 70 · **Atenção** ≥ 50 · **Crítica** < 50. Também gera **alertas** em texto.

```bash
curl http://localhost:5000/api/v1/insights/saude
```
```json
{
  "dados": {
    "indice": 76.6, "classificacao": "Boa",
    "componentes": { "sla": 84.1, "satisfacao": 79.0, "backlog_sem_atraso": 64.3 },
    "pesos": { "sla": 0.4, "satisfacao": 0.3, "backlog_sem_atraso": 0.3 },
    "alertas": [ "10 de 28 chamados da fila estão com SLA estourado." ]
  }
}
```

---

## 9. `GET /insights/sla-risco` — diferencial
**Radar de SLA**: analisa só a fila (aberto, em andamento, aguardando) e classifica cada chamado pelo % do prazo já consumido:
`estourado` (prazo vencido) · `critico` (≥ 75%) · `atencao` (≥ 50%) · `no_prazo`. Lista os mais urgentes primeiro.

| Parâmetro | Padrão | Faixa |
|---|---|---|
| `limite` | 10 | 1 a 100 |

```bash
curl "http://localhost:5000/api/v1/insights/sla-risco?limite=2"
```
```json
{
  "dados": {
    "resumo": { "estourado": 10, "critico": 5, "atencao": 4, "no_prazo": 9 },
    "chamados": [
      { "id": 916, "titulo": "Licença do software expirada", "status": "aguardando", "prioridade": "baixa", "tipo": "Software e Instalação",
        "setor": "RH", "tecnico": "Carla Mendes", "prazo_sla": "2026-11-14 05:43:04", "horas_restantes": -6.3, "sla_consumido_pct": 126.2, "nivel": "estourado" },
      { "id": 903, "titulo": "Instalar pacote Office", "status": "em_andamento", "prioridade": "media", "tipo": "Software e Instalação",
        "setor": "Logística", "tecnico": "Ana Souza", "prazo_sla": "2026-11-14 06:32:19", "horas_restantes": -5.5, "sla_consumido_pct": 134.1, "nivel": "estourado" }
    ]
  }
}
```

---

## 10. `GET /insights/mapa-calor` — diferencial
Matriz 7 × 24 (segunda a domingo × 0h a 23h) com a quantidade de chamados abertos, e o horário de pico.

```bash
curl "http://localhost:5000/api/v1/insights/mapa-calor?data_inicio=2026-10-16&data_fim=2026-11-14"
```
```json
{
  "dados": {
    "dias": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
    "horas": [0, 1, 2, "...", 23],
    "matriz": [[0, 0, 0, 0, 0, 0, 0, 1, 2, 5, 3, 2, "..."], "..."],
    "maximo": 9,
    "pico": { "dia": "Sex", "hora": 10, "quantidade": 9 }
  }
}
```

---

## 11. `GET /chamados`
Lista paginada.

| Parâmetro | Padrão | Valores |
|---|---|---|
| `pagina` | 1 | ≥ 1 |
| `por_pagina` | 20 | 1 a 100 |
| `ordenar` | `aberto_em` | `id`, `aberto_em`, `prazo_sla`, `status`, `prioridade` |
| `direcao` | `desc` | `asc`, `desc` |
| `busca` | — | texto no título ou número exato do chamado |
| + filtros comuns | | |

```bash
curl "http://localhost:5000/api/v1/chamados?por_pagina=2&status=em_andamento"
```
```json
{
  "dados": {
    "pagina": 1, "por_pagina": 2, "total": 13, "total_paginas": 7,
    "dados": [
      { "id": 907, "titulo": "Configurar e-mail no celular", "descricao": "Configurar e-mail no celular - solicitado pelo setor RH.",
        "tipo_id": 6, "tipo": "E-mail", "setor_id": 2, "setor": "RH", "tecnico_id": 3, "tecnico": "Carla Mendes",
        "prioridade": "alta", "status": "em_andamento", "aberto_em": "2026-11-14 11:03:54", "prazo_sla": "2026-11-14 15:03:54",
        "resolvido_em": null, "satisfacao": null, "atualizado_em": "2026-11-14 11:03:54", "horas_resolucao": null, "dentro_sla": true }
    ]
  }
}
```
**Erros:** `400` para `pagina`, `por_pagina`, `ordenar` ou `direcao` inválidos.

---

## 12. `GET /chamados/{id}`
Detalhe com as **considerações técnicas** (histórico de pareceres) em ordem cronológica.

```bash
curl http://localhost:5000/api/v1/chamados/12
```
```json
{
  "dados": {
    "id": 12, "titulo": "Erro de autenticação no VPN", "tipo": "Acesso e Senhas", "setor": "RH", "tecnico": "Ana Souza",
    "prioridade": "media", "status": "resolvido", "aberto_em": "2026-06-02 13:53:03", "prazo_sla": "2026-06-02 17:53:03",
    "resolvido_em": "2026-06-02 15:27:09", "horas_resolucao": 1.6, "dentro_sla": true,
    "consideracoes_tecnicas": [
      { "id": 33, "texto": "Necessário aguardar retorno do usuário para validar a solução.", "criado_em": "2026-06-02 14:22:27", "tecnico_id": 1, "tecnico": "Ana Souza" },
      { "id": 35, "texto": "Teste final aprovado pelo usuário. Chamado pronto para encerramento.", "criado_em": "2026-06-02 15:21:16", "tecnico_id": 1, "tecnico": "Ana Souza" }
    ]
  }
}
```
**Erros:** `404 NAO_ENCONTRADO` → `{ "erro": { "codigo": "NAO_ENCONTRADO", "mensagem": "Chamado 99999 não encontrado." } }`

---

## 13. `POST /chamados` — RF07
Abre um chamado. O **prazo de SLA é calculado pela API**: `SLA base do tipo × fator da prioridade` (crítica 0,25 · alta 0,5 · média 1 · baixa 1,5). Responde **201** com o cabeçalho `Location`.

| Campo | Obrigatório | Regra |
|---|---|---|
| `titulo` | sim | 3 a 120 caracteres (espaços extras são removidos) |
| `descricao` | não | até 2000 caracteres |
| `tipo_id` | sim | inteiro existente |
| `setor_id` | sim | inteiro existente |
| `prioridade` | não (padrão `media`) | `baixa`, `media`, `alta`, `critica` |
| `tecnico_id` | não | inteiro existente |

```bash
curl -X POST http://localhost:5000/api/v1/chamados -H "Content-Type: application/json" \
  -d '{"titulo":"Projetor da sala 3 sem imagem","descricao":"Projetor liga mas não exibe imagem.","tipo_id":4,"setor_id":2,"prioridade":"alta"}'
```
```json
{
  "dados": {
    "id": 929, "titulo": "Projetor da sala 3 sem imagem", "tipo": "Hardware", "setor": "RH", "tecnico_id": null,
    "prioridade": "alta", "status": "aberto", "aberto_em": "2026-11-14 12:00:00", "prazo_sla": "2026-11-15 00:00:00",
    "dentro_sla": true, "consideracoes_tecnicas": []
  }
}
```
**Erros:** `400 JSON_INVALIDO` · `422 VALIDACAO`:
```json
{ "erro": { "codigo": "VALIDACAO", "mensagem": "Dados do chamado inválidos.",
  "detalhes": { "titulo": "'titulo' deve ter entre 3 e 120 caracteres.", "tipo_id": "'tipo_id' = 99 não existe.", "setor_id": "'setor_id' é obrigatório." } } }
```

---

## 14. `PATCH /chamados/{id}/status` — RF07
Atualiza o status seguindo a **máquina de estados**:

```
aberto ──► em_andamento ──► resolvido
  │            │  ▲  │          │
  │            ▼  │  │          └──► em_andamento (reabertura)
  │        aguardando│
  └────────────┴─────┴──► cancelado (final)
```

| De | Para (permitido) |
|---|---|
| aberto | em_andamento, cancelado |
| em_andamento | aguardando, resolvido, cancelado |
| aguardando | em_andamento, cancelado |
| resolvido | em_andamento (reabrir) |
| cancelado | — |

| Campo | Obrigatório | Regra |
|---|---|---|
| `status` | sim | um dos 5 status |
| `tecnico_id` | não | atribui/troca o técnico |
| `satisfacao` | não | inteiro 1–5, **só** ao resolver |

Ao resolver, a API grava `resolvido_em`; ao reabrir, limpa `resolvido_em` e `satisfacao`.

```bash
curl -X PATCH http://localhost:5000/api/v1/chamados/929/status -H "Content-Type: application/json" -d '{"status":"em_andamento","tecnico_id":3}'
```
```json
{ "dados": { "id": 929, "status": "em_andamento", "tecnico_id": 3, "tecnico": "Carla Mendes", "...": "..." } }
```
**Erros:** `404` · `422 VALIDACAO` (status/satisfação/técnico inválidos) · `409 TRANSICAO_INVALIDA`:
```json
{ "erro": { "codigo": "TRANSICAO_INVALIDA", "mensagem": "Não é permitido mudar de 'em_andamento' para 'aberto'.",
  "detalhes": { "status_atual": "em_andamento", "permitidos": ["aguardando", "cancelado", "resolvido"] } } }
```

---

## 15. `POST /chamados/{id}/consideracoes` — RF07
Registra uma consideração técnica (parecer) no histórico do chamado. Responde **201**.

| Campo | Obrigatório | Regra |
|---|---|---|
| `tecnico_id` | sim | inteiro existente |
| `texto` | sim | 5 a 1000 caracteres |

```bash
curl -X POST http://localhost:5000/api/v1/chamados/929/consideracoes -H "Content-Type: application/json" \
  -d '{"tecnico_id":3,"texto":"Cabo HDMI substituído; aguardando teste do usuário."}'
```
```json
{ "dados": { "id": 2688, "chamado_id": 929, "texto": "Cabo HDMI substituído; aguardando teste do usuário.", "criado_em": "2026-11-14 12:00:00", "tecnico_id": 3, "tecnico": "Carla Mendes" } }
```
**Erros:** `404` (chamado não existe) · `422 VALIDACAO` (`texto` curto/ausente, `tecnico_id` ausente/inexistente) · `400 JSON_INVALIDO`.
