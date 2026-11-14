/* Gráficos em SVG/HTML puro (sem bibliotecas externas) — Pedro Henrique Campos */
const Graficos = (() => {
  const tip = () => document.getElementById("tooltip");
  const fmtNum = (n, casas = 0) => (n === null || n === undefined ? "—" :
    Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas }));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function mostrarTip(html, x, y) {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    const w = t.offsetWidth, h = t.offsetHeight;
    let left = x + 14, top = y - h - 10;
    if (left + w > window.innerWidth - 8) left = x - w - 14;
    if (top < 8) top = y + 16;
    t.style.left = `${left}px`;
    t.style.top = `${top}px`;
  }
  const esconderTip = () => { tip().hidden = true; };

  function escalaBonita(max) {
    if (max <= 0) return { max: 4, passo: 1 };
    const bruto = max / 4;
    const mag = 10 ** Math.floor(Math.log10(bruto));
    const passo = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((p) => p >= bruto);
    return { max: Math.ceil(max / passo) * passo, passo };
  }

  function rotuloPeriodo(p, agrupamento, curto = false) {
    if (agrupamento === "mes") {
      const [a, m] = p.split("-");
      return new Date(+a, +m - 1, 1).toLocaleDateString("pt-BR", { month: "short", year: curto ? "2-digit" : "numeric" }).replace(".", "");
    }
    const [a, m, d] = p.split("-");
    return agrupamento === "semana" ? `sem. ${d}/${m}` : `${d}/${m}`;
  }

  /* RF02 — Linhas: abertos × resolvidos, com crosshair + tooltip */
  function linhas(el, dados) {
    const serie = dados.serie;
    if (!serie.length) { el.innerHTML = '<p class="vazio">Sem dados no período.</p>'; return; }
    const W = Math.max(el.clientWidth, 320), H = 260;
    const m = { t: 16, r: 70, b: 28, l: 36 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const maxV = Math.max(...serie.map((s) => Math.max(s.abertos, s.resolvidos)));
    const { max, passo } = escalaBonita(maxV);
    const x = (i) => m.l + (serie.length === 1 ? iw / 2 : (i * iw) / (serie.length - 1));
    const y = (v) => m.t + ih - (v / max) * ih;
    const caminho = (campo) => serie.map((s, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(s[campo]).toFixed(1)}`).join("");

    let grade = "";
    for (let v = 0; v <= max; v += passo) {
      grade += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--grade)" />
                <text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${fmtNum(v)}</text>`;
    }
    const nTicks = Math.min(serie.length, Math.floor(iw / 70));
    const salto = Math.max(1, Math.ceil(serie.length / nTicks));
    let eixoX = "";
    serie.forEach((s, i) => {
      if (i % salto === 0) eixoX += `<text x="${x(i)}" y="${H - 8}" text-anchor="middle">${rotuloPeriodo(s.periodo, dados.agrupamento, true)}</text>`;
    });
    const ult = serie.length - 1;
    const pontos = serie.length <= 31 ? serie.map((s, i) => `
      <circle cx="${x(i)}" cy="${y(s.abertos)}" r="2.5" fill="var(--series-1)" />
      <circle cx="${x(i)}" cy="${y(s.resolvidos)}" r="2.5" fill="var(--series-2)" />`).join("") : "";

    // Rótulos diretos no fim das linhas (evita sobreposição)
    let yA = y(serie[ult].abertos), yR = y(serie[ult].resolvidos);
    const folga = 14 - Math.abs(yA - yR);
    if (folga > 0) { if (yA <= yR) { yA -= folga / 2; yR += folga / 2; } else { yA += folga / 2; yR -= folga / 2; } }

    el.innerHTML = `
      <div class="legenda"><span><i style="background:var(--series-1)"></i>Abertos (${fmtNum(dados.totais.abertos)})</span>
        <span><i style="background:var(--series-2)"></i>Resolvidos (${fmtNum(dados.totais.resolvidos)})</span></div>
      <svg width="100%" viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de chamados abertos e resolvidos por período">
        <g class="eixo">${grade}${eixoX}</g>
        <path d="${caminho("abertos")}" fill="none" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        <path d="${caminho("resolvidos")}" fill="none" stroke="var(--series-2)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
        ${pontos}
        <text x="${x(ult) + 8}" y="${yA + 4}" font-size="11" fill="var(--text-secondary)">Abertos</text>
        <text x="${x(ult) + 8}" y="${yR + 4}" font-size="11" fill="var(--text-secondary)">Resolvidos</text>
        <line class="mira" x1="0" x2="0" y1="${m.t}" y2="${m.t + ih}" stroke="var(--text-muted)" stroke-dasharray="3 3" visibility="hidden"/>
        <circle class="mira-a" r="5" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2" visibility="hidden"/>
        <circle class="mira-r" r="5" fill="var(--series-2)" stroke="var(--surface-1)" stroke-width="2" visibility="hidden"/>
        <rect class="area-hover" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
      </svg>`;

    const svg = el.querySelector("svg");
    const mira = svg.querySelector(".mira"), ma = svg.querySelector(".mira-a"), mr = svg.querySelector(".mira-r");
    const area = svg.querySelector(".area-hover");
    area.addEventListener("mousemove", (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(ult, Math.round(((px - m.l) / iw) * ult)));
      const s = serie[i];
      [mira, ma, mr].forEach((n) => n.setAttribute("visibility", "visible"));
      mira.setAttribute("x1", x(i)); mira.setAttribute("x2", x(i));
      ma.setAttribute("cx", x(i)); ma.setAttribute("cy", y(s.abertos));
      mr.setAttribute("cx", x(i)); mr.setAttribute("cy", y(s.resolvidos));
      mostrarTip(`<b>${rotuloPeriodo(s.periodo, dados.agrupamento)}</b>
        <div class="ln"><i style="background:var(--series-1)"></i>Abertos: <b>${s.abertos}</b></div>
        <div class="ln"><i style="background:var(--series-2)"></i>Resolvidos: <b>${s.resolvidos}</b></div>
        <div>SLA cumprido: ${s.taxa_sla_pct === null ? "—" : fmtNum(s.taxa_sla_pct, 1) + "%"}</div>
        <div>Tempo médio: ${s.tempo_medio_resolucao_horas === null ? "—" : fmtNum(s.tempo_medio_resolucao_horas, 1) + " h"}</div>`,
      ev.clientX, ev.clientY);
    });
    area.addEventListener("mouseleave", () => { [mira, ma, mr].forEach((n) => n.setAttribute("visibility", "hidden")); esconderTip(); });
  }

  /* Barras horizontais (status, tipos) */
  function barras(el, itens, { cor = "var(--series-1)", onTip } = {}) {
    if (!itens.length || itens.every((i) => i.valor === 0)) { el.innerHTML = '<p class="vazio">Sem dados para os filtros escolhidos.</p>'; return; }
    const max = Math.max(...itens.map((i) => i.valor), 1);
    el.innerHTML = `<div class="barras">${itens.map((i, idx) => `
      <div class="item" data-idx="${idx}">
        <span class="nome" title="${esc(i.nome)}">${esc(i.nome)}</span>
        <span class="trilho"><i style="width:${Math.max((i.valor / max) * 100, i.valor ? 1.5 : 0)}%;background:${cor}"></i></span>
        <span class="num"><b>${fmtNum(i.valor)}</b>${i.extra ? ` · ${esc(i.extra)}` : ""}</span>
      </div>`).join("")}</div>`;
    if (onTip) {
      el.querySelectorAll(".item").forEach((n) => {
        n.addEventListener("mousemove", (ev) => mostrarTip(onTip(itens[+n.dataset.idx]), ev.clientX, ev.clientY));
        n.addEventListener("mouseleave", esconderTip);
      });
    }
  }

  /* Medidor semicircular do Índice de Saúde */
  function medidor(el, saude) {
    const v = saude.indice;
    const cor = v >= 85 ? "var(--good)" : v >= 70 ? "var(--seq-400)" : v >= 50 ? "var(--warning)" : "var(--critical)";
    const icone = v >= 85 ? "✔" : v >= 70 ? "●" : v >= 50 ? "▲" : "✖";
    const R = 80, cx = 100, cy = 95, ang = Math.PI * (1 - v / 100);
    const px = cx + R * Math.cos(ang), py = cy - R * Math.sin(ang);
    const nomes = { sla: "Cumprimento de SLA", satisfacao: "Satisfação", backlog_sem_atraso: "Fila sem atraso" };
    el.innerHTML = `<div class="saude-wrap">
      <svg width="220" height="125" viewBox="0 0 200 115" role="img" aria-label="Índice de saúde ${v} de 100, ${saude.classificacao}">
        <path d="M20,95 A80,80 0 0 1 180,95" fill="none" stroke="var(--grade)" stroke-width="14" stroke-linecap="round"/>
        <path d="M20,95 A80,80 0 0 1 ${px.toFixed(1)},${py.toFixed(1)}" fill="none" stroke="${cor}" stroke-width="14" stroke-linecap="round"/>
        <text x="100" y="80" text-anchor="middle" font-size="34" font-weight="700" fill="var(--text-primary)">${fmtNum(v, 0)}</text>
        <text x="100" y="102" text-anchor="middle" font-size="13" fill="var(--text-secondary)">${icone} ${esc(saude.classificacao)}</text>
      </svg>
      <div class="saude-comp">${Object.entries(saude.componentes).map(([k, val]) => `
        <div class="linha"><span>${nomes[k]} <small>(${saude.pesos[k] * 100}%)</small></span>
          <span class="trilho"><i style="width:${val}%"></i></span><span style="text-align:right">${fmtNum(val, 0)}</span></div>`).join("")}
      </div>
      ${saude.alertas.length ? `<ul class="alertas">${saude.alertas.map((a) => `<li>▲ ${esc(a)}</li>`).join("")}</ul>` : ""}
    </div>`;
  }

  /* Mapa de calor dia × hora (escala sequencial de um só tom) */
  function mapaCalor(el, d) {
    if (!d.maximo) { el.innerHTML = '<p class="vazio">Sem dados para os filtros escolhidos.</p>'; return; }
    const rampa = ["#ecebe7", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
    const cor = (n) => (n === 0 ? rampa[0] : rampa[Math.min(7, 1 + Math.floor((n / d.maximo) * 6.999))]);
    let html = '<div class="calor"><span></span>';
    d.horas.forEach((h) => { html += `<span class="cab">${h % 3 === 0 ? h + "h" : ""}</span>`; });
    d.dias.forEach((dia, di) => {
      html += `<span class="dia">${dia}</span>`;
      d.matriz[di].forEach((n, h) => { html += `<span class="cel" data-d="${di}" data-h="${h}" style="background:${cor(n)}"></span>`; });
    });
    html += "</div>";
    html += `<div class="escala"><span>menos</span><span class="grad"></span><span>mais (${d.maximo})</span></div>`;
    if (d.pico) html += `<p class="destaque-pico">Pico de demanda: <b>${d.pico.dia}, ${d.pico.hora}h–${d.pico.hora + 1}h</b> (${d.pico.quantidade} chamados). Bom horário para reforçar a equipe.</p>`;
    el.innerHTML = html;
    el.querySelectorAll(".cel").forEach((c) => {
      c.addEventListener("mousemove", (ev) => {
        const di = +c.dataset.d, h = +c.dataset.h;
        mostrarTip(`<b>${d.dias[di]}, ${h}h–${h + 1}h</b><br>${d.matriz[di][h]} chamados abertos`, ev.clientX, ev.clientY);
      });
      c.addEventListener("mouseleave", esconderTip);
    });
  }

  return { linhas, barras, medidor, mapaCalor, fmtNum, esc, mostrarTip, esconderTip };
})();
