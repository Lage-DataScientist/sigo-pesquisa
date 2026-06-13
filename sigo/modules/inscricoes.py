"""
Módulo de Inscrições FM — integração com o portal SIGO

Fluxo de criação de uma inscrição FM:
  1. GestaoInscricoes.jsp        — escolha do tipo de formação
  2. CriarInscricaoModalidades.jsp — header da inscrição (data, escolaridade)
  3. SituacaoProfissional.jsp    — Tab 1: condição perante o trabalho
  4. OutrosDados.jsp             — Tab 2: protocolo + deficiências
  5. DiagnosticoFMEFA.jsp        — Tab 3: nível escolar de referência

Tipos de formação disponíveis (página de escolha):
  EFA, FM, OFP, CET, CAMAIS, JovensCA, PF
"""

from __future__ import annotations
from dataclasses import dataclass, field
from playwright.async_api import Page

# ── URLs ──────────────────────────────────────────────────────────────────────
URL_ESCOLHA_TIPO   = "https://www.sigo.pt/inscricoes/GestaoInscricoes.jsp"
URL_CRIAR_FM       = "https://www.sigo.pt/inscricoes/CriarInscricaoModalidades.jsp"
URL_SIT_PROF       = "https://www.sigo.pt/inscricoesEntidades/SituacaoProfissional.jsp"
URL_OUTROS_DADOS   = "https://www.sigo.pt/inscricoesEntidades/OutrosDados.jsp"
URL_DIAGNOSTICO    = "https://www.sigo.pt/inscricoesEntidades/DiagnosticoFMEFA.jsp"

# ── Seletores — Escolha do tipo de formação ───────────────────────────────────
SEL_TIPOS = {
    "EFA":      "#form1\\:linkEFA",      # Cursos de Educação e Formação de Adultos
    "FM":       "#form1\\:linkFM",       # Formação Modular Certificada
    "OFP":      "#form1\\:linkOFP",      # Outra Formação Profissional
    "CET":      "#form1\\:linkCET",      # Cursos de Especialização Tecnológica
    "CAMAIS":   "#form1\\:linkCAMAIS",   # Cursos de Aprendizagem +
    "CA":       "#form1\\:linkJovensCA", # Cursos de Aprendizagem
    "PF":       "#form1\\:linkPF",       # Percursos de Formação
    "voltar":   "#form1\\:ihVoltar",
}

# ── Seletores — Header da inscrição (CriarInscricaoModalidades.jsp) ───────────
SEL_HEADER = {
    "data":              "#form1\\:Pf_headerInfoInscricao\\:dtInscricao",       # aaaa/mm/dd
    "escolaridade":      "#form1\\:Pf_headerInfoInscricao\\:ddEscolaridade",    # select
    "limpar_acao":       "#form1\\:linkLimparAccao",
    "apagar_inscricao":  "#form1\\:linkApagarInscricao",
    "comprovativo":      "#form1\\:ihUploadEsc",
    "editar_formando":   "#form1\\:linkEditarFormando",
}

# ── Seletores — Tab Situação Profissional ─────────────────────────────────────
SEL_SIT_PROF = {
    "condicao_trabalho": "#form1\\:tabSet\\:tab1\\:ddSituacao",
    "gravar":            "#form1\\:tabSet\\:tab1\\:ihGravarSP",
    "voltar":            "#form1\\:tabSet\\:tab1\\:ihVoltar",
}

# Opções confirmadas (values do select)
CONDICAO_TRABALHO = {
    "E": "Empregado",
    "D": "Desempregado",
    "G": "Estagiário",
    "M": "Inativo",
    "R": "Reformado",
    "O": "Outra",
}

# ── Seletores — Tab Outros Dados ──────────────────────────────────────────────
SEL_OUTROS_DADOS = {
    "tab":              "#form1\\:tabSet\\:tab2",
    "protocolo_com":    "#form1\\:tabSet\\:tab2\\:ddProtocoloCom",
}

# Checkboxes de deficiências/incapacidades (índice 0-5 na tabela)
SEL_DEFICIENCIAS = {
    "audicao":                    "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:0\\:tableColumn6\\:checkbox1",
    "intelectuais":               "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:1\\:tableColumn6\\:checkbox1",
    "neuromusculoesqueleticas":   "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:2\\:tableColumn6\\:checkbox1",
    "outras_funcoes_mentais":     "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:3\\:tableColumn6\\:checkbox1",
    "visao":                      "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:4\\:tableColumn6\\:checkbox1",
    "voz_e_fala":                 "#form1\\:tabSet\\:tab2\\:table1\\:tableRowGroup1\\:5\\:tableColumn6\\:checkbox1",
}

# ── Seletores — Tab Diagnóstico ───────────────────────────────────────────────
SEL_DIAGNOSTICO = {
    "tab":                    "#form1\\:tabSet\\:tab3",
    "nivel_escolar_ref":      "#form1\\:tabSet\\:tab3\\:ddNivelEscolarRef",
    "comp_tecnologica":       "#form1\\:tabSet\\:tab3\\:cbCompTecnologica",
}

# Opções confirmadas
NIVEL_ESCOLAR_REF = {
    "B": "Básico",
    "S": "Secundário",
    "5": "Pós Secundário",
}

# ── Tabs de navegação ─────────────────────────────────────────────────────────
TABS = {
    "situacao_profissional": "Situação Profissional",   # tab activo por defeito
    "outros_dados":          "#form1\\:tabSet\\:tab2",
    "diagnostico":           "#form1\\:tabSet\\:tab3",
    "historico":             "#form1\\:tabSet\\:tabHistoric",
}

# ── Dataclass ─────────────────────────────────────────────────────────────────
@dataclass
class DadosInscricaoFM:
    """Todos os dados necessários para criar uma inscrição FM."""
    # Header
    data:               str = ""   # aaaa/mm/dd
    escolaridade:       str = ""   # label do select (ex: "Licenciatura")

    # Tab Situação Profissional
    condicao_trabalho:  str = ""   # valor do select: E, D, G, M, R, O

    # Tab Outros Dados
    protocolo_com:      str = ""   # valor do select (id numérico)
    deficiencias:       list[str] = field(default_factory=list)
    # ex: ["audicao", "visao"] — usar chaves de SEL_DEFICIENCIAS

    # Tab Diagnóstico
    nivel_escolar_ref:  str = ""   # B, S, ou 5
    comp_tecnologica:   bool = False


# ── Funções públicas ──────────────────────────────────────────────────────────

async def nova_inscricao_fm(page: Page, dados: DadosInscricaoFM) -> None:
    """
    Cria uma nova inscrição FM para o formando cujo registo está aberto.
    Preenche todos os tabs e grava no final do Tab 1.
    """
    # 1. Escolher tipo FM
    await page.click(SEL_TIPOS["FM"])
    await page.wait_for_load_state("networkidle")

    # 2. Header — data e escolaridade
    if dados.data:
        await page.fill(SEL_HEADER["data"], dados.data)
    if dados.escolaridade:
        await page.select_option(SEL_HEADER["escolaridade"], label=dados.escolaridade)

    # 3. Tab Situação Profissional (activo por defeito)
    if dados.condicao_trabalho:
        await page.select_option(SEL_SIT_PROF["condicao_trabalho"], value=dados.condicao_trabalho)

    # 4. Tab Outros Dados
    await page.click(TABS["outros_dados"])
    await page.wait_for_load_state("networkidle")

    if dados.protocolo_com:
        await page.select_option(SEL_OUTROS_DADOS["protocolo_com"], value=dados.protocolo_com)

    for def_key in dados.deficiencias:
        sel = SEL_DEFICIENCIAS.get(def_key)
        if sel:
            await page.check(sel)

    # 5. Tab Diagnóstico
    await page.click(TABS["diagnostico"])
    await page.wait_for_load_state("networkidle")

    if dados.nivel_escolar_ref:
        await page.select_option(SEL_DIAGNOSTICO["nivel_escolar_ref"], value=dados.nivel_escolar_ref)
    if dados.comp_tecnologica:
        await page.check(SEL_DIAGNOSTICO["comp_tecnologica"])

    # 6. Gravar (volta ao Tab Situação Profissional para gravar)
    await page.click(TABS["situacao_profissional"])
    await page.wait_for_load_state("networkidle")
    await page.click(SEL_SIT_PROF["gravar"])
    await page.wait_for_load_state("networkidle")


async def voltar_inscricoes(page: Page) -> None:
    """Regressa ao registo de inscrições do formando."""
    await page.click(SEL_SIT_PROF["voltar"])
    await page.wait_for_load_state("networkidle")
