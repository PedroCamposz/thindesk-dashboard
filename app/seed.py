"""Geração de dados de exemplo realistas e determinísticos (mesma semente = mesmos dados)."""
import random
from datetime import datetime, timedelta

from .db import fmt
from .regras import FATOR_SLA, calcular_prazo_sla

SETORES = ["Financeiro", "RH", "Comercial", "Logística", "TI", "Diretoria", "Atendimento"]

TIPOS = [  # (nome, SLA base em horas, peso de ocorrência)
    ("Acesso e Senhas", 4, 22),
    ("Rede e Conectividade", 8, 15),
    ("Software e Instalação", 16, 16),
    ("Hardware", 24, 12),
    ("Impressoras", 12, 11),
    ("E-mail", 8, 9),
    ("Sistema ERP", 12, 10),
    ("Segurança da Informação", 6, 5),
]

TECNICOS = [  # (nome, nível, velocidade relativa: <1 = mais rápido)
    ("Ana Souza", "N2", 0.8),
    ("Bruno Lima", "N1", 1.1),
    ("Carla Mendes", "N3", 0.7),
    ("Diego Rocha", "N1", 1.25),
    ("Fernanda Alves", "N2", 0.9),
    ("Gustavo Nunes", "N1", 1.05),
]

TITULOS = {
    "Acesso e Senhas": ["Reset de senha do AD", "Usuário bloqueado no sistema", "Liberar acesso à pasta compartilhada",
                        "Criar login para novo colaborador", "Erro de autenticação no VPN"],
    "Rede e Conectividade": ["Sem internet na estação", "Wi-Fi caindo na sala de reunião", "Lentidão na rede",
                             "Ponto de rede sem sinal", "VPN não conecta"],
    "Software e Instalação": ["Instalar pacote Office", "Atualizar navegador", "Erro ao abrir planilha",
                              "Instalar leitor de PDF", "Licença do software expirada"],
    "Hardware": ["Notebook não liga", "Monitor piscando", "Teclado com teclas falhando",
                 "Troca de mouse", "Computador muito lento (upgrade de memória)"],
    "Impressoras": ["Impressora não imprime", "Papel atolado na multifuncional", "Toner acabando",
                    "Scanner não envia e-mail", "Instalar impressora na estação"],
    "E-mail": ["Caixa de e-mail cheia", "Não recebe e-mails externos", "Configurar e-mail no celular",
               "Assinatura de e-mail", "E-mail suspeito recebido"],
    "Sistema ERP": ["Erro ao emitir nota fiscal", "Relatório do ERP não carrega", "Permissão de módulo no ERP",
                    "Lentidão no fechamento de caixa", "Integração do ERP com banco falhou"],
    "Segurança da Informação": ["Possível phishing", "Antivírus desatualizado", "Bloqueio de site indevido",
                                "Dispositivo USB não autorizado", "Alerta de login suspeito"],
}

CONSIDERACOES = [
    "Diagnóstico inicial realizado remotamente; problema reproduzido.",
    "Verificados logs do sistema. Causa provável identificada.",
    "Aplicada correção e solicitado teste ao usuário.",
    "Necessário aguardar retorno do usuário para validar a solução.",
    "Escalado para nível superior por exigir acesso administrativo.",
    "Peça solicitada ao fornecedor; prazo de entrega informado ao usuário.",
    "Solução documentada na base de conhecimento para casos semelhantes.",
    "Problema recorrente no setor; recomendada ação preventiva.",
    "Usuário orientado sobre boas práticas para evitar reincidência.",
    "Teste final aprovado pelo usuário. Chamado pronto para encerramento.",
]

PRIORIDADES_PESOS = [("baixa", 30), ("media", 42), ("alta", 21), ("critica", 7)]


def _escolha_ponderada(rnd, itens):
    total = sum(p for _, p in itens)
    alvo = rnd.uniform(0, total)
    acc = 0
    for item, peso in itens:
        acc += peso
        if alvo <= acc:
            return item
    return itens[-1][0]


def _momento_abertura(rnd, referencia: datetime, dias: int) -> datetime:
    """Sorteia data/hora de abertura com mais chamados em dias úteis e horário comercial."""
    while True:
        dia = referencia.date() - timedelta(days=rnd.randint(0, dias - 1))
        if dia.weekday() >= 5 and rnd.random() < 0.85:  # fim de semana é raro
            continue
        hora = _escolha_ponderada(rnd, [(h, p) for h, p in
                                        {7: 3, 8: 8, 9: 14, 10: 15, 11: 11, 12: 5, 13: 7,
                                         14: 13, 15: 12, 16: 10, 17: 6, 18: 3, 19: 1}.items()])
        dt = datetime(dia.year, dia.month, dia.day, hora, rnd.randint(0, 59), rnd.randint(0, 59))
        if dt <= referencia:
            return dt


def popular(con, referencia: datetime, quantidade: int = 900, dias: int = 180, semente: int = 2026, fila: int = 28):
    """Gera `quantidade` chamados históricos + `fila` chamados ativos recentes (fila atual de atendimento)."""
    rnd = random.Random(semente)
    cur = con.cursor()
    cur.executemany("INSERT INTO setores (nome) VALUES (?)", [(s,) for s in SETORES])
    cur.executemany("INSERT INTO tipos_chamado (nome, sla_horas) VALUES (?, ?)", [(n, s) for n, s, _ in TIPOS])
    cur.executemany("INSERT INTO tecnicos (nome, nivel) VALUES (?, ?)", [(n, nv) for n, nv, _ in TECNICOS])

    pesos_tipo = [(i + 1, t[2]) for i, t in enumerate(TIPOS)]
    for n_chamado in range(quantidade + fila):
        na_fila = n_chamado >= quantidade
        tipo_id = _escolha_ponderada(rnd, pesos_tipo)
        nome_tipo, sla_horas, _ = TIPOS[tipo_id - 1]
        prioridade = _escolha_ponderada(rnd, PRIORIDADES_PESOS)
        setor_id = rnd.randint(1, len(SETORES))
        tecnico_id = rnd.randint(1, len(TECNICOS))
        if na_fila:  # chamado ainda em atendimento: aberto há uma fração (0,1 a 1,4x) da janela de SLA
            janela_h = sla_horas * FATOR_SLA[prioridade]
            aberto_em = (referencia - timedelta(hours=rnd.uniform(0.1, 1.4) * janela_h)).replace(microsecond=0)
        else:
            aberto_em = _momento_abertura(rnd, referencia, dias)
        prazo = calcular_prazo_sla(aberto_em, sla_horas, prioridade)
        idade_h = (referencia - aberto_em).total_seconds() / 3600

        # Tempo de resolução: proporcional ao SLA, à velocidade do técnico e com variação aleatória
        sla_efetivo = (prazo - aberto_em).total_seconds() / 3600
        duracao_h = max(0.2, rnd.lognormvariate(0, 0.6) * sla_efetivo * 0.6 * TECNICOS[tecnico_id - 1][2])

        resolvido_em, satisfacao = None, None
        if na_fila:
            status = _escolha_ponderada(rnd, [("aberto", 35), ("em_andamento", 45), ("aguardando", 20)])
            if status == "aberto" and rnd.random() < 0.5:
                tecnico_id = None
        elif rnd.random() < 0.04:
            status = "cancelado"
        else:
            status = "resolvido"
            resolvido_em = aberto_em + timedelta(hours=min(duracao_h, idade_h * 0.95))  # nunca no futuro
            dentro = resolvido_em <= prazo
            satisfacao = min(5, max(1, round(rnd.gauss(4.4 if dentro else 3.1, 0.7))))
            if rnd.random() < 0.15:
                satisfacao = None  # usuário não avaliou

        titulo = rnd.choice(TITULOS[nome_tipo])
        atualizado = resolvido_em or aberto_em
        cur.execute(
            """INSERT INTO chamados (titulo, descricao, tipo_id, setor_id, tecnico_id, prioridade, status,
                                     aberto_em, prazo_sla, resolvido_em, satisfacao, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (titulo, f"{titulo} - solicitado pelo setor {SETORES[setor_id - 1]}.", tipo_id, setor_id,
             tecnico_id, prioridade, status, fmt(aberto_em), fmt(prazo),
             fmt(resolvido_em) if resolvido_em else None, satisfacao, fmt(atualizado)),
        )
        chamado_id = cur.lastrowid

        if tecnico_id and status != "aberto":
            fim = resolvido_em or referencia
            n = 3 if status == "resolvido" else rnd.randint(1, 2)
            textos = rnd.sample(CONSIDERACOES[:-1], n - 1 if status == "resolvido" else n)
            if status == "resolvido":
                textos.append(CONSIDERACOES[-1])
            for i, texto in enumerate(textos):
                momento = aberto_em + (fim - aberto_em) * ((i + 1) / (len(textos) + 0.2))
                cur.execute("INSERT INTO consideracoes_tecnicas (chamado_id, tecnico_id, texto, criado_em) "
                            "VALUES (?,?,?,?)", (chamado_id, tecnico_id, texto, fmt(momento)))
    con.commit()
