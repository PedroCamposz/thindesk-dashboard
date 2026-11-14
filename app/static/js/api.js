/* Cliente da API Thindesk (RF06 — Integração com a API) — Pedro Henrique Campos */
const API = (() => {
  const BASE = "/api/v1";
  const TIMEOUT_MS = 10000;

  class ErroApi extends Error {
    constructor(status, codigo, mensagem, detalhes) {
      super(mensagem);
      Object.assign(this, { status, codigo, detalhes });
    }
  }

  function montarQuery(params = {}) {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") q.append(k, v);
    });
    const s = q.toString();
    return s ? `?${s}` : "";
  }

  async function requisitar(caminho, { metodo = "GET", params, corpo, tentativas = 2 } = {}) {
    for (let tentativa = 1; tentativa <= tentativas; tentativa++) {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
      try {
        const resp = await fetch(BASE + caminho + montarQuery(params), {
          method: metodo,
          headers: corpo ? { "Content-Type": "application/json" } : {},
          body: corpo ? JSON.stringify(corpo) : undefined,
          signal: ctrl.signal,
        });
        const json = await resp.json().catch(() => null);
        if (!resp.ok) {
          const e = json && json.erro ? json.erro : {};
          throw new ErroApi(resp.status, e.codigo || "ERRO_HTTP", e.mensagem || `Erro HTTP ${resp.status}`, e.detalhes);
        }
        return json.dados;
      } catch (err) {
        // Erros de negócio (4xx) não são repetidos; falhas de rede/timeout/5xx tentam de novo
        const repetir = !(err instanceof ErroApi && err.status < 500) && tentativa < tentativas;
        if (!repetir) {
          if (err.name === "AbortError") throw new ErroApi(0, "TIMEOUT", "A API demorou demais para responder.");
          if (err instanceof ErroApi) throw err;
          throw new ErroApi(0, "SEM_CONEXAO", "Não foi possível conectar à API.");
        }
        await new Promise((r) => setTimeout(r, 400 * tentativa));
      } finally {
        clearTimeout(timer);
      }
    }
  }

  return {
    ErroApi,
    health: () => requisitar("/health", { tentativas: 1 }),
    filtros: () => requisitar("/filtros"),
    indicadores: (f) => requisitar("/indicadores", { params: f }),
    periodo: (f) => requisitar("/chamados/periodo", { params: f }),
    situacao: (f) => requisitar("/chamados/situacao", { params: f }),
    rankingTipos: (f) => requisitar("/tipos/ranking", { params: f }),
    tecnicos: (f) => requisitar("/tecnicos/desempenho", { params: f }),
    saude: (f) => requisitar("/insights/saude", { params: f }),
    mapaCalor: (f) => requisitar("/insights/mapa-calor", { params: f }),
    slaRisco: (f) => requisitar("/insights/sla-risco", { params: f }),
    listar: (f) => requisitar("/chamados", { params: f }),
    obter: (id) => requisitar(`/chamados/${id}`),
    criar: (dados) => requisitar("/chamados", { metodo: "POST", corpo: dados, tentativas: 1 }),
    mudarStatus: (id, dados) => requisitar(`/chamados/${id}/status`, { metodo: "PATCH", corpo: dados, tentativas: 1 }),
    addConsideracao: (id, dados) => requisitar(`/chamados/${id}/consideracoes`, { metodo: "POST", corpo: dados, tentativas: 1 }),
  };
})();
