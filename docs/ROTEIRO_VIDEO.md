# Roteiro do vídeo (até 3 minutos) — Thindesk Insight

**Apresentador:** Pedro Henrique Campos

**Antes de gravar:**
1. Rode `python run.py --reset` (dados “limpos”) e depois `python run.py`.
2. Abra no navegador: `http://localhost:5000` (tela cheia, zoom 90% se precisar).
3. Deixe aberto em outra aba: o repositório no GitHub e o arquivo `docs/API.md`.
4. Deixe um terminal pronto na pasta do projeto para rodar `python -m pytest`.

> Dica: fale com calma, não precisa decorar palavra por palavra. Os tempos são aproximados; o total fica em ~2 min 50 s.

---

### Cena 1 — Abertura (0:00 – 0:15)
**Na tela:** dashboard aberto, parado no topo.

> “Olá, eu sou o Pedro Henrique Campos, de Sistemas de Informação da UMC. Este é o **Thindesk Insight**, um dashboard administrativo integrado ao sistema de chamados Thindesk. A ideia foi ir além de um painel que só mostra números: ele também **avisa o que precisa de atenção**, pra ajudar o responsável a decidir.”

### Cena 2 — Arquitetura e decisões (0:15 – 0:40)
**Na tela:** GitHub → abra `docs/DOCUMENTACAO.md` e role até o diagrama de arquitetura e o DER.

> “A solução tem duas partes: uma **API REST em Python com Flask**, ligada a um **banco SQLite**, e o dashboard em HTML, CSS e JavaScript, que consome essa API. Escolhi SQLite porque não precisa de instalação nenhuma, e deixei **todos os cálculos no back-end**, assim a regra de negócio fica em um lugar só. O banco tem chamados, tipos com SLA, setores, técnicos e as considerações técnicas em uma tabela separada, pra guardar o histórico.”

### Cena 3 — Indicadores e filtros (RF01, RF05) (0:40 – 1:05)
**Na tela:** volte ao dashboard. Mostre os cartões. Troque o período para “Últimos 90 dias” e o tipo para “Hardware”. Depois clique em “Limpar filtros”.

> “No topo ficam os **indicadores gerais**: total de chamados comparado com o período anterior, a fila, quantos já estouraram o SLA, tempo médio de resolução, percentual de SLA cumprido e satisfação. Aqui em cima estão os **filtros** — período, tipo, técnico, setor, prioridade e status. Quando eu mudo um filtro, **todos os blocos** consultam a API de novo com esse filtro.”

### Cena 4 — Gráficos, situação e tipos (RF02, RF03, RF04) (1:05 – 1:30)
**Na tela:** passe o mouse no gráfico de linhas; clique em “Semana”. Aponte para “Situação dos chamados” e “Tipos mais atendidos”.

> “Esse gráfico mostra **abertos contra resolvidos por período**, por dia, semana ou mês, e no tooltip aparece o SLA e o tempo médio daquele dia. Aqui está a **situação** dos chamados por status e a fila por prioridade, e aqui o **ranking dos tipos mais atendidos** — dá pra ver que Acesso e Senhas lidera.”

### Cena 5 — O diferencial (1:30 – 2:00)
**Na tela:** aponte para o Índice de Saúde, depois o Radar de SLA, depois o Mapa de calor.

> “Agora a parte diferente. O **Índice de Saúde** junta SLA, satisfação e atraso da fila em uma nota de 0 a 100 e já escreve o alerta. O **Radar de SLA** mostra, em ordem de urgência, quais chamados já estouraram ou estão quase estourando o prazo — com ícone e texto, não só cor. E o **mapa de calor** mostra em que dia e horário mais chega chamado, o que ajuda a decidir quando reforçar a equipe.”

### Cena 6 — Atualização de dados (RF06, RF07) (2:00 – 2:30)
**Na tela:** clique no primeiro chamado do Radar → mostre as considerações técnicas → registre uma consideração → mude o status para “Em andamento”. Feche. Clique em “+ Novo chamado”, crie um com prioridade Alta.

> “Clicando num chamado, vejo os detalhes e as **considerações técnicas**. Posso registrar uma nova e **mudar o status** — e a API valida as transições: por exemplo, não dá pra resolver um chamado que ninguém começou a atender, ela devolve erro 409. Também dá pra abrir um chamado novo, e o **prazo de SLA é calculado automaticamente** pelo tipo e pela prioridade. O painel ainda se **atualiza sozinho a cada 30 segundos** e avisa se a API cair.”

### Cena 7 — API, testes e Gitflow (2:30 – 2:50)
**Na tela:** mostre rapidamente `docs/API.md` (sumário dos 15 endpoints). No terminal, rode `python -m pytest` e mostre “59 passed”. No GitHub, abra o seletor de branches.

> “A API tem **15 endpoints documentados** com parâmetros, exemplos e erros. Fiz **59 testes automatizados**, que conferem os cálculos com valores exatos, os filtros e os erros — todos passando. E o código está no GitHub seguindo o **Gitflow**: main, develop, as features da API, do dashboard e dos testes, e a release 1.0.0.”

### Cena 8 — Encerramento (2:50 – 3:00)
**Na tela:** volte ao dashboard.

> “Então é isso: um painel que mostra, explica e ajuda a decidir. Obrigado!”

---

## Checklist rápido do que precisa aparecer no vídeo

- [ ] Seu nome e o nome do projeto
- [ ] Indicadores gerais (RF01)
- [ ] Gráfico por período (RF02)
- [ ] Situação dos chamados (RF03)
- [ ] Tipos mais atendidos (RF04)
- [ ] Uso dos filtros (RF05)
- [ ] Dados vindo da API / atualização automática (RF06, RF07)
- [ ] Alterar algo e ver o painel atualizar (RF07)
- [ ] Justificativa das decisões (Flask, SQLite, cálculos no back-end, endpoints separados)
- [ ] Testes passando
- [ ] Branches do Gitflow no GitHub
