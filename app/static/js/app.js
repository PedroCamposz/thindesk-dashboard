/* Thindesk Insight — controle do dashboard (RF01–RF07) — Pedro Henrique Campos */
(() => {
  const $ = (s) => document.querySelector(s);
  const { fmtNum, esc } = Graficos;
  const INTERVALO_AUTO_MS = 30000;

  const estado = {
    opcoes: null,
    agrupamento: "dia",
    pagina: 1,
    ordenar: "aberto_em",
    direcao: "desc",
    busca: "",
    timer: null,
    carregando: false,
  };

  const ROTULO_STATUS = { aberto: "Aberto", em_andamento: "Em andamento", aguardando: "Aguardando", resolvido: "Resolvido", cancelado: "Cancelado" };
  const ROTULO_PRIOR = { baixa: "Baixa", media: "Média", alta: "Alta", critica: "Crítica" };
  const NIVEL = {
    estourado: { r: "Estourado", i: "✖" }, critico: { r: "Crítico", i: "▲" },
    atencao: { r: "Atenção", i: "●" }, no_prazo: { r: "No prazo", i: "✔" },
  };
  const TRANSICOES = {
    aberto: ["em_andamento", "cancelado"], em_andamento: ["aguardando", "resolvido", "cancelado"],
    aguardando: ["em_andamento", "cancelado"], resolvido: ["em_andamento"], cancelado: [],
  };

  /* ------------------------------------------------------------ utilidades */
  const isoLocal = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const dataBR = (txt) => {
    if (!txt) return "—";
    const [d, h] = txt.split(" ");
    const [a, m, dia] = d.split("-");
    return `${dia}/${m}/${a}${h ? " " + h.slice(0, 5) : ""}`;
  };
  const horas = (h) => {
    if (h === null || h === undefined) return "—";
    const abs = Math.abs(h);
    const txt = abs >= 48 ? `${fmtNum(abs / 24, 1)} d` : abs >= 1 ? `${fmtNum(abs, 1)} h` : `${Math.round(abs * 60)} min`;
    return h < 0 ? `-${txt}` : txt;
  };
  const badgeStatus = (s) => `<span class="badge s-${s}">${ROTULO_STATUS[s] || s}</span>`;
  const badgeNivel = (n) => `<span class="badge n-${n}">${NIVEL[n].i} ${NIVEL[n].r}</span>`;
  const prior = (p) => `<span class="p-${p}">${p === "critica" ? "▲▲ " : p === "alta" ? "▲ " : ""}${ROTULO_PRIOR[p]}</span>`;

  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { t.hidden = true; }, 3200);
  }

  function preencherSelect(sel, itens, valor, rotulo) {
    const primeiro = sel.querySelector("option[value='']");
    sel.innerHTML = "";
    if (primeiro) sel.appendChild(primeiro);
    itens.forEach((i) => {
      const o = document.createElement("option");
      o.value = valor(i);
      o.textContent = rotulo(i);
      sel.appendChild(o);
    });
  }

  /* ------------------------------------------------------------ RF05 filtros */
  function aplicarPreset() {
    const p = $("#f-preset").value;
    if (p === "custom") return;
    const fim = new Date();
    const ini = new Date();
    ini.setDate(fim.getDate() - (+p - 1));
    $("#f-inicio").value = isoLocal(ini);
    $("#f-fim").value = isoLocal(fim);
  }

  function filtrosAtuais() {
    return {
      data_inicio: $("#f-inicio").value,
      data_fim: $("#f-fim").value,
      tipo_id: $("#f-tipo").value,
      tecnico_id: $("#f-tecnico").value,
      setor_id: $("#f-setor").value,
      prioridade: $("#f-prioridade").value,
      status: $("#f-status").value,
    };
  }

  function validarDatas() {
    const i = $("#f-inicio").value, f = $("#f-fim").value;
    if (i && f && i > f) {
      toast("A data inicial não pode ser maior que a final.");
      return false;
    }
    return true;
  }

  /* ------------------------------------------------------------ RF07 estado de erro / conexão */
  function mostrarErro(msg) {
    $("#alerta-texto").textContent = `⚠ ${msg}`;
    $("#alerta-erro").hidden = false;
    $("#status-api").className = "pill pill-erro";
    $("#status-api").textContent = "● API offline";
  }
  function limparErro() {
    $("#alerta-erro").hidden = true;
    $("#status-api").className = "pill pill-ok";
    $("#status-api").textContent = "● API online";
  }

  /* ------------------------------------------------------------ renderizações */
  function renderKpis(k) {
    const variacao = k.variacao_periodo_anterior_pct;
    const subVar = variacao === null ? "sem comparação" :
      `${variacao > 0 ? "▲" : variacao < 0 ? "▼" : "="} ${fmtNum(Math.abs(variacao), 1)}% vs. período anterior`;
    const cards = [
      { r: "Total de chamados", v: fmtNum(k.total_chamados), s: subVar, cls: variacao > 0 ? "sobe" : variacao < 0 ? "desce" : "" },
      { r: "Na fila (backlog)", v: fmtNum(k.backlog), s: `${k.abertos} abertos · ${k.em_andamento} em andamento · ${k.aguardando} aguardando` },
      { r: "SLA estourado na fila", v: fmtNum(k.atrasados), s: k.backlog ? `${fmtNum((k.atrasados / k.backlog) * 100, 0)}% da fila` : "fila vazia" },
      { r: "Resolvidos", v: fmtNum(k.resolvidos), s: `taxa de resolução ${fmtNum(k.taxa_resolucao_pct, 1)}%` },
      { r: "Tempo médio de resolução", v: k.tempo_medio_resolucao_horas === null ? "—" : `${fmtNum(k.tempo_medio_resolucao_horas, 1)}<small> h</small>`, s: "da abertura à solução" },
      { r: "SLA cumprido", v: k.taxa_cumprimento_sla_pct === null ? "—" : `${fmtNum(k.taxa_cumprimento_sla_pct, 1)}<small>%</small>`, s: "dos chamados resolvidos" },
      { r: "Satisfação média", v: k.satisfacao_media === null ? "—" : `${fmtNum(k.satisfacao_media, 2)}<small> /5</small>`, s: "avaliação dos usuários" },
    ];
    $("#kpis").innerHTML = cards.map((c) => `
      <div class="kpi"><div class="rotulo">${c.r}</div><div class="valor">${c.v}</div><div class="sub ${c.cls || ""}">${c.s}</div></div>`).join("");
  }

  function renderSituacao(d) {
    const el = $("#situacao");
    el.classList.remove("carregando");
    Graficos.barras(el, d.status.map((s) => ({ nome: s.rotulo, valor: s.quantidade, extra: `${fmtNum(s.percentual, 1)}%` })), {
      onTip: (i) => `<b>${esc(i.nome)}</b><br>${i.valor} chamados (${i.extra})`,
    });
    const bp = d.backlog_por_prioridade;
    el.insertAdjacentHTML("beforeend", `<p class="destaque-pico">Fila por prioridade: ${["critica", "alta", "media", "baixa"]
      .map((p) => `${prior(p)} <b>${bp[p]}</b>`).join(" · ")}</p>`);
  }

  function renderTipos(d) {
    const el = $("#ranking-tipos");
    el.classList.remove("carregando");
    Graficos.barras(el, d.ranking.map((t) => ({ ...t, nome: `${t.posicao}º ${t.tipo}`, valor: t.total, extra: `${fmtNum(t.participacao_pct, 0)}%` })), {
      onTip: (t) => `<b>${esc(t.tipo)}</b><br>${t.total} chamados (${fmtNum(t.participacao_pct, 1)}% do total)<br>
        Tempo médio: ${t.tempo_medio_resolucao_horas === null ? "—" : fmtNum(t.tempo_medio_resolucao_horas, 1) + " h"}<br>
        SLA cumprido: ${t.taxa_cumprimento_sla_pct === null ? "—" : fmtNum(t.taxa_cumprimento_sla_pct, 1) + "%"}<br>SLA base: ${t.sla_base_horas} h`,
    });
  }

  function renderRadar(d) {
    const el = $("#radar");
    el.classList.remove("carregando");
    const r = d.resumo;
    el.innerHTML = `
      <div class="resumo-radar">
        <div><b>${r.estourado}</b>✖ Estourado</div><div><b>${r.critico}</b>▲ Crítico</div>
        <div><b>${r.atencao}</b>● Atenção</div><div><b>${r.no_prazo}</b>✔ No prazo</div>
      </div>
      ${d.chamados.length ? `<ul class="radar-lista">${d.chamados.map((c) => `
        <li data-id="${c.id}">
          ${badgeNivel(c.nivel)}
          <div><div class="tit">#${c.id} ${esc(c.titulo)}</div>
            <div class="meta">${esc(c.tipo)} · ${prior(c.prioridade)} · ${esc(c.tecnico || "sem técnico")}</div></div>
          <div class="tempo">${c.horas_restantes < 0 ? `atrasado ${horas(-c.horas_restantes)}` : `resta ${horas(c.horas_restantes)}`}</div>
        </li>`).join("")}</ul>` : '<p class="vazio">✔ Nenhum chamado em risco. Fila saudável!</p>'}`;
    el.querySelectorAll("li[data-id]").forEach((li) => li.addEventListener("click", () => abrirChamado(+li.dataset.id)));
  }

  function renderTecnicos(lista) {
    const el = $("#tecnicos");
    el.classList.remove("carregando");
    if (!lista.length) { el.innerHTML = '<p class="vazio">Sem dados para os filtros escolhidos.</p>'; return; }
    el.innerHTML = `<div class="rolagem"><table class="tabela"><thead><tr>
      <th>Técnico</th><th class="num">Resolvidos</th><th class="num">Na fila</th><th class="num">Tempo médio</th><th class="num">SLA</th><th class="num">Satisf.</th>
      </tr></thead><tbody>${lista.map((t) => `<tr data-tecnico="${t.tecnico_id}" title="Filtrar por ${esc(t.nome)}">
      <td>${esc(t.nome)} <small class="texto-suave">${t.nivel}</small></td><td class="num">${t.resolvidos}</td><td class="num">${t.em_fila}</td>
      <td class="num">${t.tempo_medio_resolucao_horas === null ? "—" : fmtNum(t.tempo_medio_resolucao_horas, 1) + " h"}</td>
      <td class="num">${t.taxa_cumprimento_sla_pct === null ? "—" : fmtNum(t.taxa_cumprimento_sla_pct, 0) + "%"}</td>
      <td class="num">${t.satisfacao_media === null ? "—" : fmtNum(t.satisfacao_media, 1)}</td></tr>`).join("")}</tbody></table></div>`;
    el.querySelectorAll("tr[data-tecnico]").forEach((tr) => tr.addEventListener("click", () => {
      $("#f-tecnico").value = tr.dataset.tecnico;
      estado.pagina = 1;
      carregarTudo();
    }));
  }

  function renderLista(d) {
    const el = $("#lista");
    el.classList.remove("carregando");
    if (!d.dados.length) {
      el.innerHTML = '<p class="vazio">Nenhum chamado encontrado.</p>';
      $("#paginacao").innerHTML = "";
      return;
    }
    const seta = (c) => (estado.ordenar === c ? (estado.direcao === "asc" ? " ↑" : " ↓") : "");
    el.innerHTML = `<div class="rolagem"><table class="tabela"><thead><tr>
      <th data-ordem="id">Nº${seta("id")}</th><th>Título</th><th>Tipo</th><th>Setor</th><th>Técnico</th>
      <th data-ordem="prioridade">Prioridade${seta("prioridade")}</th><th data-ordem="status">Status${seta("status")}</th>
      <th data-ordem="aberto_em">Aberto em${seta("aberto_em")}</th><th data-ordem="prazo_sla">Prazo SLA${seta("prazo_sla")}</th><th>SLA</th>
      </tr></thead><tbody>${d.dados.map((c) => `<tr data-id="${c.id}">
        <td>#${c.id}</td><td>${esc(c.titulo)}</td><td>${esc(c.tipo)}</td><td>${esc(c.setor)}</td><td>${esc(c.tecnico || "—")}</td>
        <td>${prior(c.prioridade)}</td><td>${badgeStatus(c.status)}</td><td>${dataBR(c.aberto_em)}</td><td>${dataBR(c.prazo_sla)}</td>
        <td>${c.dentro_sla === null ? "—" : c.dentro_sla ? '<span class="badge n-no_prazo">✔ Dentro</span>' : '<span class="badge n-estourado">✖ Fora</span>'}</td>
      </tr>`).join("")}</tbody></table></div>`;
    el.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => abrirChamado(+tr.dataset.id)));
    el.querySelectorAll("th[data-ordem]").forEach((th) => th.addEventListener("click", () => {
      const c = th.dataset.ordem;
      estado.direcao = estado.ordenar === c && estado.direcao === "desc" ? "asc" : "desc";
      estado.ordenar = c;
      carregarLista();
    }));
    $("#paginacao").innerHTML = `<span>Mostrando ${(d.pagina - 1) * d.por_pagina + 1}–${Math.min(d.pagina * d.por_pagina, d.total)} de ${fmtNum(d.total)} chamados</span>
      <span class="btns"><button class="btn btn-sec" id="pg-ant" ${d.pagina <= 1 ? "disabled" : ""}>‹ Anterior</button>
      <span style="align-self:center">Página ${d.pagina} de ${d.total_paginas}</span>
      <button class="btn btn-sec" id="pg-prox" ${d.pagina >= d.total_paginas ? "disabled" : ""}>Próxima ›</button></span>`;
    $("#pg-ant").onclick = () => { estado.pagina--; carregarLista(); };
    $("#pg-prox").onclick = () => { estado.pagina++; carregarLista(); };
  }

  /* ------------------------------------------------------------ carregamento (RF06/RF07) */
  async function carregarLista() {
    const f = { ...filtrosAtuais(), pagina: estado.pagina, por_pagina: 10, ordenar: estado.ordenar, direcao: estado.direcao, busca: estado.busca };
    try {
      renderLista(await API.listar(f));
    } catch (e) {
      $("#lista").innerHTML = `<p class="vazio">⚠ ${esc(e.message)}</p>`;
    }
  }

  async function carregarTudo({ silencioso = false } = {}) {
    if (estado.carregando || !validarDatas()) return;
    estado.carregando = true;
    const f = filtrosAtuais();
    if (!silencioso) document.querySelectorAll(".corpo").forEach((c) => c.classList.add("carregando"));

    const tarefas = [
      [API.indicadores(f), renderKpis],
      [API.saude(f), (d) => { $("#saude").classList.remove("carregando"); Graficos.medidor($("#saude"), d); }],
      [API.periodo({ ...f, agrupamento: estado.agrupamento }), (d) => { $("#grafico-periodo").classList.remove("carregando"); Graficos.linhas($("#grafico-periodo"), d); estado.ultimaSerie = d; }],
      [API.situacao(f), renderSituacao],
      [API.rankingTipos({ ...f, limite: 8 }), renderTipos],
      // O radar mostra a fila ATUAL: ignora o período, mas respeita os demais filtros
      [API.slaRisco({ ...f, data_inicio: "", data_fim: "", limite: 15 }), renderRadar],
      [API.mapaCalor(f), (d) => { $("#mapa-calor").classList.remove("carregando"); Graficos.mapaCalor($("#mapa-calor"), d); }],
      [API.tecnicos(f), renderTecnicos],
    ];
    const resultados = await Promise.allSettled(tarefas.map(([p]) => p));
    let falhas = 0, ultimoErro = null;
    resultados.forEach((r, i) => {
      if (r.status === "fulfilled") {
        try { tarefas[i][1](r.value); } catch (err) { console.error(err); }
      } else { falhas++; ultimoErro = r.reason; }
    });
    await carregarLista();
    estado.carregando = false;

    if (falhas) {
      const msg = ultimoErro && ultimoErro.codigo === "PARAMETRO_INVALIDO" ? ultimoErro.message :
        `Não foi possível carregar ${falhas} de ${tarefas.length} blocos. ${ultimoErro ? ultimoErro.message : ""}`;
      mostrarErro(msg);
      if (ultimoErro && ultimoErro.status === 0) document.querySelectorAll(".corpo.carregando").forEach((c) => { c.classList.remove("carregando"); c.innerHTML = '<p class="vazio">⚠ Dados indisponíveis</p>'; });
    } else {
      limparErro();
    }
    $("#ultima-atualizacao").textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
  }

  function configurarAuto() {
    clearInterval(estado.timer);
    if ($("#auto-refresh").checked) {
      estado.timer = setInterval(() => { if (!document.hidden && !document.querySelector("dialog[open]")) carregarTudo({ silencioso: true }); }, INTERVALO_AUTO_MS);
    }
  }

  /* ------------------------------------------------------------ detalhe do chamado */
  async function abrirChamado(id) {
    const modal = $("#modal-chamado");
    $("#modal-conteudo").innerHTML = '<div class="corpo carregando"></div>';
    if (!modal.open) modal.showModal();
    try {
      const c = await API.obter(id);
      const proximos = TRANSICOES[c.status];
      const opcoesTec = estado.opcoes.tecnicos.map((t) => `<option value="${t.id}" ${t.id === c.tecnico_id ? "selected" : ""}>${esc(t.nome)}</option>`).join("");
      $("#modal-conteudo").innerHTML = `
        <header class="modal-topo"><div><small class="texto-suave">Chamado #${c.id}</small><h3>${esc(c.titulo)}</h3></div>
          <button class="fechar" data-fechar aria-label="Fechar">×</button></header>
        <div>${badgeStatus(c.status)} ${c.dentro_sla === null ? "" : c.dentro_sla ? badgeNivel("no_prazo") : badgeNivel("estourado")}</div>
        <p style="margin:0;color:var(--text-secondary)">${esc(c.descricao || "Sem descrição.")}</p>
        <div class="detalhes">
          <div>Tipo<b>${esc(c.tipo)}</b></div><div>Setor<b>${esc(c.setor)}</b></div><div>Prioridade<b>${prior(c.prioridade)}</b></div>
          <div>Técnico<b>${esc(c.tecnico || "Não atribuído")}</b></div><div>Aberto em<b>${dataBR(c.aberto_em)}</b></div><div>Prazo SLA<b>${dataBR(c.prazo_sla)}</b></div>
          <div>Resolvido em<b>${dataBR(c.resolvido_em)}</b></div><div>Tempo de resolução<b>${horas(c.horas_resolucao)}</b></div><div>Satisfação<b>${c.satisfacao ? "★".repeat(c.satisfacao) + "☆".repeat(5 - c.satisfacao) : "—"}</b></div>
        </div>
        <div><h4 style="margin:4px 0 8px">Considerações técnicas (${c.consideracoes_tecnicas.length})</h4>
          ${c.consideracoes_tecnicas.length ? `<ul class="linha-tempo">${c.consideracoes_tecnicas.map((x) => `
            <li><div class="quando">${dataBR(x.criado_em)} · ${esc(x.tecnico)}</div>${esc(x.texto)}</li>`).join("")}</ul>` : '<p class="texto-suave">Nenhuma consideração registrada.</p>'}
        </div>
        <div class="acoes-chamado">
          <form class="bloco" id="form-status">
            <h4>Atualizar status</h4>
            ${proximos.length ? `<select name="status">${proximos.map((s) => `<option value="${s}">${ROTULO_STATUS[s]}</option>`).join("")}</select>
            <select name="tecnico_id"><option value="">Manter técnico</option>${opcoesTec}</select>
            <select name="satisfacao" title="Avaliação do usuário (ao resolver)"><option value="">Satisfação (opcional)</option>${[5, 4, 3, 2, 1].map((n) => `<option>${n}</option>`).join("")}</select>
            <button class="btn">Salvar status</button>` : '<p class="texto-suave">Chamado cancelado — sem transições possíveis.</p>'}
          </form>
          <form class="bloco" id="form-consid">
            <h4>Nova consideração técnica</h4>
            <select name="tecnico_id" required>${opcoesTec}</select>
            <textarea name="texto" rows="3" placeholder="Diagnóstico, ação realizada, próximos passos…" required minlength="5" maxlength="1000"></textarea>
            <button class="btn">Registrar</button>
          </form>
        </div>
        <p class="erro-form" id="erro-chamado"></p>`;

      const fs = $("#form-status");
      if (proximos.length) {
        const sat = fs.querySelector("[name=satisfacao]");
        const sincronizar = () => { sat.disabled = fs.status.value !== "resolvido"; if (sat.disabled) sat.value = ""; };
        fs.status.addEventListener("change", sincronizar);
        sincronizar();
        fs.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          const corpo = { status: fs.status.value };
          if (fs.tecnico_id.value) corpo.tecnico_id = +fs.tecnico_id.value;
          if (sat.value) corpo.satisfacao = +sat.value;
          try {
            await API.mudarStatus(c.id, corpo);
            toast(`Chamado #${c.id} atualizado para "${ROTULO_STATUS[corpo.status]}".`);
            await abrirChamado(c.id);
            carregarTudo({ silencioso: true });
          } catch (e) { $("#erro-chamado").textContent = `⚠ ${e.message}`; }
        });
      }
      const fc = $("#form-consid");
      fc.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const texto = fc.texto.value.trim();
        if (texto.length < 5) { $("#erro-chamado").textContent = "⚠ A consideração deve ter pelo menos 5 caracteres."; return; }
        try {
          await API.addConsideracao(c.id, { tecnico_id: +fc.tecnico_id.value, texto });
          toast("Consideração técnica registrada.");
          await abrirChamado(c.id);
        } catch (e) { $("#erro-chamado").textContent = `⚠ ${e.message}${e.detalhes ? " — " + Object.values(e.detalhes).join(" ") : ""}`; }
      });
    } catch (e) {
      $("#modal-conteudo").innerHTML = `<header class="modal-topo"><h3>Erro</h3><button class="fechar" data-fechar>×</button></header><p>⚠ ${esc(e.message)}</p>`;
    }
  }

  /* ------------------------------------------------------------ novo chamado */
  function abrirNovo() {
    const f = $("#form-novo");
    f.reset();
    f.prioridade.value = "media";
    $("#erro-novo").textContent = "";
    $("#modal-novo").showModal();
    f.titulo.focus();
  }

  async function enviarNovo(ev) {
    ev.preventDefault();
    const f = ev.target;
    const corpo = {
      titulo: f.titulo.value.trim(),
      descricao: f.descricao.value.trim() || null,
      tipo_id: +f.tipo_id.value,
      setor_id: +f.setor_id.value,
      prioridade: f.prioridade.value,
    };
    if (f.tecnico_id.value) corpo.tecnico_id = +f.tecnico_id.value;
    if (corpo.titulo.length < 3) { $("#erro-novo").textContent = "⚠ O título deve ter pelo menos 3 caracteres."; return; }
    try {
      const c = await API.criar(corpo);
      $("#modal-novo").close();
      toast(`Chamado #${c.id} aberto com sucesso! Prazo de SLA: ${dataBR(c.prazo_sla)}`);
      carregarTudo({ silencioso: true });
    } catch (e) {
      $("#erro-novo").textContent = `⚠ ${e.message}${e.detalhes ? " — " + Object.values(e.detalhes).join(" ") : ""}`;
    }
  }

  /* ------------------------------------------------------------ exportar CSV (página filtrada completa) */
  async function exportarCsv() {
    try {
      const linhas = [];
      let pagina = 1, total = 1;
      while (pagina <= total && pagina <= 50) {
        const d = await API.listar({ ...filtrosAtuais(), busca: estado.busca, pagina, por_pagina: 100, ordenar: estado.ordenar, direcao: estado.direcao });
        linhas.push(...d.dados);
        total = d.total_paginas;
        pagina++;
      }
      const cab = ["id", "titulo", "tipo", "setor", "tecnico", "prioridade", "status", "aberto_em", "prazo_sla", "resolvido_em", "horas_resolucao", "dentro_sla", "satisfacao"];
      const cel = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const csv = "﻿" + [cab.join(";"), ...linhas.map((l) => cab.map((c) => cel(l[c])).join(";"))].join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
      a.download = `chamados_thindesk_${isoLocal(new Date())}.csv`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(`${linhas.length} chamados exportados.`);
    } catch (e) { toast(`Falha ao exportar: ${e.message}`); }
  }

  /* ------------------------------------------------------------ inicialização */
  async function iniciar() {
    aplicarPreset();
    try {
      estado.opcoes = await API.filtros();
    } catch (e) {
      mostrarErro(`${e.message} Verifique se o servidor está rodando (python run.py).`);
      document.querySelectorAll(".corpo").forEach((c) => { c.classList.remove("carregando"); c.innerHTML = '<p class="vazio">⚠ Dados indisponíveis</p>'; });
      return;
    }
    const o = estado.opcoes;
    preencherSelect($("#f-tipo"), o.tipos, (t) => t.id, (t) => t.nome);
    preencherSelect($("#f-tecnico"), o.tecnicos, (t) => t.id, (t) => `${t.nome} (${t.nivel})`);
    preencherSelect($("#f-setor"), o.setores, (s) => s.id, (s) => s.nome);
    preencherSelect($("#f-prioridade"), o.prioridades, (p) => p, (p) => ROTULO_PRIOR[p]);
    preencherSelect($("#f-status"), o.status, (s) => s.valor, (s) => s.rotulo);
    const fn = $("#form-novo");
    preencherSelect(fn.tipo_id, o.tipos, (t) => t.id, (t) => `${t.nome} (SLA ${t.sla_horas}h)`);
    preencherSelect(fn.setor_id, o.setores, (s) => s.id, (s) => s.nome);
    preencherSelect(fn.prioridade, o.prioridades, (p) => p, (p) => ROTULO_PRIOR[p]);
    fn.prioridade.value = "media";
    preencherSelect(fn.tecnico_id, o.tecnicos, (t) => t.id, (t) => t.nome);

    // Eventos
    $("#f-preset").addEventListener("change", () => { aplicarPreset(); estado.pagina = 1; carregarTudo(); });
    ["#f-inicio", "#f-fim"].forEach((s) => $(s).addEventListener("change", () => { $("#f-preset").value = "custom"; estado.pagina = 1; carregarTudo(); }));
    ["#f-tipo", "#f-tecnico", "#f-setor", "#f-prioridade", "#f-status"].forEach((s) => $(s).addEventListener("change", () => { estado.pagina = 1; carregarTudo(); }));
    $("#btn-limpar").addEventListener("click", () => {
      ["#f-tipo", "#f-tecnico", "#f-setor", "#f-prioridade", "#f-status"].forEach((s) => { $(s).value = ""; });
      $("#f-preset").value = "30"; aplicarPreset();
      $("#busca").value = ""; estado.busca = ""; estado.pagina = 1;
      carregarTudo();
    });
    $("#agrupamento").addEventListener("click", async (ev) => {
      const b = ev.target.closest("button");
      if (!b) return;
      document.querySelectorAll("#agrupamento button").forEach((x) => x.classList.toggle("ativo", x === b));
      estado.agrupamento = b.dataset.v;
      try {
        const d = await API.periodo({ ...filtrosAtuais(), agrupamento: estado.agrupamento });
        Graficos.linhas($("#grafico-periodo"), d);
        estado.ultimaSerie = d;
      } catch (e) { mostrarErro(e.message); }
    });
    let debounce;
    $("#busca").addEventListener("input", (ev) => {
      clearTimeout(debounce);
      debounce = setTimeout(() => { estado.busca = ev.target.value.trim(); estado.pagina = 1; carregarLista(); }, 350);
    });
    $("#btn-atualizar").addEventListener("click", () => carregarTudo());
    $("#btn-tentar").addEventListener("click", () => carregarTudo());
    $("#auto-refresh").addEventListener("change", configurarAuto);
    $("#btn-novo").addEventListener("click", abrirNovo);
    $("#btn-csv").addEventListener("click", exportarCsv);
    $("#form-novo").addEventListener("submit", enviarNovo);
    document.addEventListener("click", (ev) => { if (ev.target.closest("[data-fechar]")) ev.target.closest("dialog").close(); });
    document.querySelectorAll("dialog").forEach((d) => d.addEventListener("click", (ev) => { if (ev.target === d) d.close(); }));
    let redim;
    window.addEventListener("resize", () => { clearTimeout(redim); redim = setTimeout(() => { if (estado.ultimaSerie) Graficos.linhas($("#grafico-periodo"), estado.ultimaSerie); }, 200); });

    await carregarTudo();
    configurarAuto();
  }

  document.addEventListener("DOMContentLoaded", iniciar);
})();
