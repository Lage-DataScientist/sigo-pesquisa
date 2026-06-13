"""
Módulo de Formandos — integração com https://www.sigo.pt/alunos/GestaoAlunos.jsp

Funcionalidades:
  - pesquisar()       — pesquisa formandos por qualquer combinação de campos
  - adicionar()       — cria um novo formando
  - abrir()           — abre o registo de um formando existente (por Nº SIGO)
  - listar_todos()    — pesquisa sem filtros (requer pelo menos um critério no SIGO)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from playwright.async_api import Page

# ── URLs ──────────────────────────────────────────────────────────────────────
URL = "https://www.sigo.pt/alunos/GestaoAlunos.jsp"

# ── Template Excel de Importação de Formandos ────────────────────────────────
# Sheet "CFORM" — 30 colunas na ordem exacta do ficheiro Formandos_Template.xlsx
COLUNAS_TEMPLATE_EXCEL = [
    "Tipo Linha",                        # sempre "CFORM"
    "Nome",
    "Data Nascimento",                   # aaaa/mm/dd
    "Sexo",
    "Tipo Doc Identificação",            # A=Autor.Residência | M=Militar | C=Ident.Civil | P=Passaporte
    "Sub Tipo Doc Identificação",        # MNE | REF | FUE | RUE | CUE | TRS
    "Número Doc Identificacão",
    "check Digit Cartão Cidadão",
    "Data Validade Doc Identificação",   # aaaa/mm/dd
    "Doc Identificação Emitido Por",     # BI Militar: GNR|FAP|MAP|EXP; Residente: DRN|DRA|DRL|DRM|DRS|DRC
    "Doc Data Emissão",                  # aaaa/mm/dd
    "BI Militar Vitalício",
    "Nif",
    "Niss",
    "Código País Nacionalidade",         # ISO 2 letras: PT | XX=Outro | ...
    "Outro País Nacionalidade",
    "Código País Origem",                # ISO 2 letras
    "Código Distrito Naturalidade",      # 01=Aveiro | 02=Beja | 03=Braga | ... | 18=Viseu
    "Código Concelho Naturalidade",      # 2 dígitos dentro do distrito
    "Outro País Origem",
    "Outra Naturalidade",
    "Telefone",
    "Telefone 2",
    "email",
    "Número SIGO Encarregado Educação",
    "Habilitações Literárias EE",        # Bacharelato | Ensino Básico | Ensino Secundário | Licenciatura | Mestrado | Doutoramento
    "Morada-Cp4",                        # 4 dígitos do código postal
    "Morada-Cp3",                        # 3 dígitos do código postal
    "Morada-Endereço",
    "Morada-Localidade",
]

# Códigos de referência da sheet "Listas"
CODIGOS_TIPO_DOC = {"A": "Autorização de Residência", "M": "Militar", "C": "Identificação Civil", "P": "Passaporte"}
CODIGOS_SUBTIPO_DOC = {"MNE": "Cartão MNE", "REF": "Título de refugiado", "FUE": "Cartão familiar UE",
                       "RUE": "Cartão residente UE", "CUE": "Certificado registo UE", "TRS": "Título de residência"}
CODIGOS_EMITIDO_POR_MILITAR = {"GNR": "GNR", "FAP": "Força Aérea", "MAP": "Marinha", "EXP": "Exército"}
CODIGOS_EMITIDO_POR_RESIDENTE = {"DRN": "DR Norte SEF", "DRA": "DR Açores SEF", "DRL": "DR Lisboa/Alentejo SEF",
                                  "DRM": "DR Madeira SEF", "DRS": "DR Algarve SEF", "DRC": "DR Centro SEF"}
CODIGOS_HAB_EE = ["Bacharelato", "Ensino Básico", "Ensino Secundário", "Licenciatura", "Mestrado", "Doutoramento"]
CODIGOS_DISTRITOS = {
    "01": "Aveiro", "02": "Beja", "03": "Braga", "04": "Bragança", "05": "Castelo Branco",
    "06": "Coimbra", "07": "Évora", "08": "Faro", "09": "Guarda", "10": "Leiria",
    "11": "Lisboa", "12": "Portalegre", "13": "Porto", "14": "Santarém", "15": "Setúbal",
    "16": "Viana do Castelo", "17": "Vila Real", "18": "Viseu",
    "31": "Ilha da Madeira", "32": "Ilha de Porto Santo",
    "41": "Ilha de Santa Maria", "42": "Ilha de São Miguel", "43": "Ilha Terceira",
    "44": "Ilha da Graciosa", "45": "Ilha de São Jorge", "46": "Ilha do Pico",
    "47": "Ilha do Faial", "48": "Ilha das Flores", "49": "Ilha do Corvo",
}

# ── Seletores — Importação via Excel ─────────────────────────────────────────
SEL_IMPORTAR = {
    "btn_toggle":       "#Pf_tituloMsg\\:ihImportar",          # abre/fecha o painel
    "template_xls":    "#form_excel\\:DownloadTemplateFileXLS",  # descarrega modelo XLS
    "template_xlsx":   "#form_excel\\:DownloadTemplateFileXLSX", # descarrega modelo XLSX
    "file_upload":     "#form_excel\\:fileUploadExcel",          # input de ficheiro
    "btn_gravar":      "#form_excel\\:ihUpload",                 # submete o ficheiro
}
# Nota: usa o form "form_excel", separado do "form1" habitual

# ── Seletores — Pesquisa ─────────────────────────────────────────────────────
SEL_PESQ = {
    "n_sigo":         "#form1\\:tfSigo",
    "nome":           "#form1\\:tfNome",
    "n_identificacao":"#form1\\:tfNDocumento",
    "nif":            "#form1\\:tfNif",
    "data_nascimento":"#form1\\:dtNascimento",   # formato: aaaa/mm/dd
    "btn_pesquisar":  "#form1\\:btSubmit",
    "lnk_pesquisar":  "#form1\\:ihFiltrar",
    "lnk_adicionar":  "#form1\\:ihCriarAlunos",
    "lnk_enc_educa":  "#form1\\:ihCriarEncEduca",
}

# ── Seletores — Tabela de Resultados ─────────────────────────────────────────
SEL_TABELA = "#form1\\:table1"

COLUNAS_TABELA = {
    "n_sigo":         "form1:table1:tableRowGroup1:tableColumn9",
    "nif":            "form1:table1:tableRowGroup1:tableColumn6",
    "nome":           "form1:table1:tableRowGroup1:tableColumn2",
    "n_identificacao":"form1:table1:tableRowGroup1:tableColumn4",
    "data_nascimento":"form1:table1:tableRowGroup1:tableColumn5",
}

# ── Seletores — Formulário Adicionar/Editar Formando ─────────────────────────
SEL_FORM = {
    # Identificação pessoal
    "nome":                   "#form1\\:tfNome",
    "genero_feminino":        "#form1\\:rbGenero_0",
    "genero_masculino":       "#form1\\:rbGenero_1",
    "data_nascimento":        "#form1\\:dtNascimento",      # aaaa/mm/dd
    "nif":                    "#form1\\:tfNIF",
    "niss":                   "#form1\\:tfNISS",

    # Documento de identificação
    "tipo_doc":               "#form1\\:ddIndentificacao",
    "subtipo_doc":            "#form1\\:ddSubTipoIndentificacao",
    "pais_emissor":           "#form1\\:ddPais",
    "emitido_por":            "#form1\\:ddEmitidoPor",
    "n_identificacao":        "#form1\\:tfNindetificacao",
    "check_digit_cc":         "#form1\\:tfCheckDigitCC",
    "data_validade":          "#form1\\:dtValidade",        # aaaa/mm/dd

    # Naturalidade
    "nacionalidade":          "#form1\\:ddNacionalidade",
    "outra_nacionalidade":    "#form1\\:tfOutraNacionalidade",
    "pais_origem":            "#form1\\:ddPaisOrigem",
    "outro_pais_origem":      "#form1\\:tfOutroPaisOrigem",
    "distrito":               "#form1\\:ddDistrito",
    "concelho":               "#form1\\:ddConcelho",
    "naturalidade":           "#form1\\:tfNaturalidade",

    # Contactos
    "indicativo_tel1":        "#form1\\:ddIndicativo1Contacto",
    "indicativo_tel2":        "#form1\\:ddIndicativo2Contacto",
    "telefone1":              "#form1\\:tfTelefone1",
    "telefone2":              "#form1\\:tfTelefone2",
    "email":                  "#form1\\:tfMail",

    # Escolaridade (dropdown rápido)
    "escolaridade":           "#form1\\:ddEscolaridade",

    # Flags
    "confidencial":           "#form1\\:cbConfidencial",
    "inscricao_restrital":    "#form1\\:cbInscricaoRestrital",

    # Morada — campos read-only preenchidos pelo popup ihMorada
    # São <span> no DOM, não <input>; o popup escreve neles ao confirmar
    "pais":                   "#form1\\:stNomePais",
    "morada":                 "#form1\\:stMorada",
    "cp4":                    "#form1\\:stCp4",
    "cp3":                    "#form1\\:stCp3",
    "localidade":             "#form1\\:stDesigCp",
    "btn_morada_popup":       "#form1\\:ihMorada",   # abre popup de pesquisa por CP

    # Acções
    "btn_gravar":             "#form1\\:btGravar",
    "btn_apagar":             "#form1\\:ihApagar",
    "btn_voltar":             "#form1\\:ihVoltar",
    "btn_morada":             "#form1\\:ihMorada",
    "btn_escolaridade":       "#form1\\:ihUploadEsc",
    "btn_historico":          "#form1\\:ihHistorico",
    "btn_enc_educacao":       "#form1\\:linkAdicionarEncEducacao",
    "btn_rem_enc_educacao":   "#form1\\:linkRemoverEncEducacao",

    # Diálogo de confirmação (ex: "Tem a certeza que deseja apagar?")
    "dlg_sim":                "#form1\\:Pf_tituloMsg\\:ihOk",
    "dlg_nao":                "#form1\\:Pf_tituloMsg\\:ihCancel",
}

# ── Seletores — Painel Escolaridade (upload) ──────────────────────────────────
SEL_ESC = {
    # Formulário de registo/upload
    "escolaridade_obtida":    "#form1\\:Pf_alteraEscolaridadeFile\\:ddEscolaridadeObtida",
    "data_certificacao":      "#form1\\:Pf_alteraEscolaridadeFile\\:dtCert",
    "tipo_ficheiro":          "#form1\\:Pf_alteraEscolaridadeFile\\:ddTipoFicheiro",
    "outro_tipo":             "#form1\\:Pf_alteraEscolaridadeFile\\:tfOutroTipo",       # activo só quando tipo=OUT
    "pedido_em_curso":        "#form1\\:Pf_alteraEscolaridadeFile\\:cbPedidoEmCurso",   # oculto no modo criar
    "file_upload":            "#form1\\:Pf_alteraEscolaridadeFile\\:fileUpload",
    "conformidade":           "#form1\\:Pf_alteraEscolaridadeFile\\:cbConformidade",
    "observacoes":            "#form1\\:Pf_alteraEscolaridadeFile\\:tfObservs",
    "btn_gravar":             "#form1\\:Pf_alteraEscolaridadeFile\\:ihGravar",
    "btn_gravar_alt":         "#form1\\:Pf_alteraEscolaridadeFile\\:ihAtualizar",       # "Gravar Alteração" (só edição)
    "btn_cancelar":           "#form1\\:Pf_alteraEscolaridadeFile\\:ihClean",
    "btn_descarregar":        "#form1\\:Pf_alteraEscolaridadeFile\\:ihDescarregar",     # só quando doc já existe

    # Auditoria — só leitura, visíveis ao editar
    "audit_utilizador":       "#form1\\:Pf_alteraEscolaridadeFile\\:tfUserReg",
    "audit_entidade":         "#form1\\:Pf_alteraEscolaridadeFile\\:entUserReg",
    "audit_data_upload":      "#form1\\:Pf_alteraEscolaridadeFile\\:dtUpload",
}

# Tabela de escolaridades registadas (colunas confirmadas)
# Colunas 3-5 (Consultar, Detalhes, Apagar) só aparecem quando há registos
COLUNAS_TABELA_ESC = {
    0: ("tableColumn2",   "Escolaridade Registada"),
    1: ("tableColumn4",   "Dt. Certificação"),
    2: ("tableColumn5",   "Estado"),
    3: ("tableColumn15",  "Consultar documento"),   # link para ver o ficheiro
    4: ("tableColumnDet", "Detalhes"),              # abre painel de edição
    5: ("tableColumn16",  "Apagar"),                # apaga o registo
}

# ── Opções dos selects ────────────────────────────────────────────────────────
# Valores confirmados do portal (value do <option> → label visível)
OPCOES_ESCOLARIDADE = {
    "0":  "-> Selecione <-",
    "22": "Sem comprovativo",
    "21": "Sem escolaridade",
    "1":  "1º Ano",
    "2":  "2º Ano",
    "3":  "3º Ano",
    "4":  "4º Ano",
    "5":  "5º Ano",
    "6":  "6º Ano",
    "7":  "7º Ano",
    "8":  "8º Ano",
    "9":  "9º Ano",
    "10": "10º Ano",
    "11": "11º Ano",
    "12": "12º Ano",
    "25": "Pós-Secundário",
    "26": "Bacharelato",
    "30": "Licenciatura",
    "35": "Mestrado",
    "40": "Doutoramento",
}

OPCOES_TIPO_DOC = {
    "A": "Autorização de Residência",
    "C": "Identificação Civil (CC/BI)",
    "M": "Militar",
    "P": "Passaporte",
}

# Indicativo de telefone — o portal só tem Portugal
OPCOES_INDICATIVO = {
    "1": "Portugal (+351)",
}

# Concelhos por distrito — valores internos do portal (district_id -> [(conc_id, nome)])
# Obtidos via POST dinâmico a CriarAlunos.jsp para cada distrito
CONCELHOS_POR_DISTRITO = {
    "1":  [("249","Amares"),("250","Barcelos"),("251","Braga"),("252","Cabeceiras de Basto"),("253","Celorico de Basto"),("254","Esposende"),("255","Fafe"),("256","Guimarães"),("257","Póvoa de Lanhoso"),("258","Terras de Bouro"),("259","Vieira do Minho"),("260","Vila Nova de Famalicão"),("261","Vila Verde"),("262","Vizela")],
    "2":  [("263","Alfândega da Fé"),("264","Bragança"),("265","Carrazeda de Ansiães"),("266","Freixo de Espada à Cinta"),("267","Macedo de Cavaleiros"),("268","Miranda do Douro"),("269","Mirandela"),("270","Mogadouro"),("271","Torre de Moncorvo"),("272","Vila Flor"),("273","Vimioso"),("274","Vinhais")],
    "3":  [("275","Belmonte"),("276","Castelo Branco"),("277","Covilhã"),("278","Fundão"),("279","Idanha-a-Nova"),("280","Oleiros"),("281","Penamacor"),("282","Proença-a-Nova"),("283","Sertã"),("284","Vila de Rei"),("285","Vila Velha de Ródão")],
    "4":  [("286","Arganil"),("287","Cantanhede"),("288","Coimbra"),("289","Condeixa-a-Nova"),("290","Figueira da Foz"),("291","Góis"),("292","Lousã"),("293","Mira"),("294","Miranda do Corvo"),("295","Montemor-o-Velho"),("296","Oliveira do Hospital"),("297","Pampilhosa da Serra"),("298","Penacova"),("299","Penela"),("300","Soure"),("301","Tábua"),("302","Vila Nova de Poiares")],
    "5":  [("303","Alandroal"),("304","Arraiolos"),("305","Borba"),("306","Estremoz"),("307","Évora"),("308","Montemor-o-Novo"),("1","Mora"),("2","Mourão"),("3","Portel"),("4","Redondo"),("5","Reguengos de Monsaraz"),("6","Vendas Novas"),("7","Viana do Alentejo"),("8","Vila Viçosa")],
    "6":  [("9","Albufeira"),("10","Alcoutim"),("11","Aljezur"),("12","Castro Marim"),("13","Faro"),("14","Lagoa"),("15","Lagos"),("16","Loulé"),("17","Monchique"),("18","Olhão"),("19","Portimão"),("20","São Brás de Alportel"),("21","Silves"),("22","Tavira"),("23","Vila do Bispo"),("24","Vila Real de Santo António")],
    "7":  [("25","Aguiar da Beira"),("26","Almeida"),("27","Celorico da Beira"),("28","Figueira de Castelo Rodrigo"),("29","Fornos de Algodres"),("30","Gouveia"),("31","Guarda"),("32","Manteigas"),("33","Meda"),("34","Pinhel"),("35","Sabugal"),("36","Seia"),("37","Trancoso"),("38","Vila Nova de Foz Côa")],
    "8":  [("39","Alcobaça"),("40","Alvaiázere"),("41","Ansião"),("42","Batalha"),("43","Bombarral"),("44","Caldas da Rainha"),("45","Castanheira de Pêra"),("46","Figueiró dos Vinhos"),("47","Leiria"),("48","Marinha Grande"),("51","Nazaré"),("52","Óbidos"),("53","Pedrógão Grande"),("54","Peniche"),("55","Pombal"),("56","Porto de Mós")],
    "9":  [("57","Alenquer"),("71","Amadora"),("58","Arruda dos Vinhos"),("59","Azambuja"),("60","Cadaval"),("61","Cascais"),("62","Lisboa"),("63","Loures"),("64","Lourinhã"),("65","Mafra"),("72","Odivelas"),("66","Oeiras"),("67","Sintra"),("68","Sobral de Monte Agraço"),("69","Torres Vedras"),("70","Vila Franca de Xira")],
    "10": [("73","Alter do Chão"),("74","Arronches"),("75","Avis"),("76","Campo Maior"),("77","Castelo de Vide"),("78","Crato"),("79","Elvas"),("80","Fronteira"),("81","Gavião"),("82","Marvão"),("83","Monforte"),("84","Nisa"),("85","Ponte de Sor"),("86","Portalegre"),("87","Sousel")],
    "11": [("88","Amarante"),("89","Baião"),("90","Felgueiras"),("91","Gondomar"),("92","Lousada"),("93","Maia"),("94","Marco de Canaveses"),("95","Matosinhos"),("96","Paços de Ferreira"),("97","Paredes"),("98","Penafiel"),("99","Porto"),("100","Póvoa de Varzim"),("101","Santo Tirso"),("105","Trofa"),("102","Valongo"),("103","Vila do Conde"),("104","Vila Nova de Gaia")],
    "12": [("106","Abrantes"),("107","Alcanena"),("108","Almeirim"),("109","Alpiarça"),("110","Benavente"),("111","Cartaxo"),("112","Chamusca"),("113","Constância"),("114","Coruche"),("115","Entroncamento"),("116","Ferreira do Zêzere"),("117","Golegã"),("118","Mação"),("126","Ourém"),("119","Rio Maior"),("120","Salvaterra de Magos"),("121","Santarém"),("122","Sardoal"),("123","Tomar"),("124","Torres Novas"),("125","Vila Nova da Barquinha")],
    "13": [("127","Alcácer do Sal"),("128","Alcochete"),("129","Almada"),("130","Barreiro"),("131","Grândola"),("132","Moita"),("133","Montijo"),("134","Palmela"),("135","Santiago do Cacém"),("136","Seixal"),("137","Sesimbra"),("138","Setúbal"),("139","Sines")],
    "14": [("140","Arcos de Valdevez"),("141","Caminha"),("142","Melgaço"),("143","Monção"),("144","Paredes de Coura"),("145","Ponte da Barca"),("146","Ponte de Lima"),("147","Valença"),("148","Viana do Castelo"),("149","Vila Nova de Cerveira")],
    "15": [("150","Alijó"),("151","Boticas"),("152","Chaves"),("153","Mesão Frio"),("154","Mondim de Basto"),("155","Montalegre"),("156","Murça"),("157","Peso da Régua"),("158","Ribeira de Pena"),("159","Sabrosa"),("160","Santa Marta de Penaguião"),("161","Valpaços"),("162","Vila Pouca de Aguiar"),("163","Vila Real")],
    "16": [("164","Armamar"),("165","Carregal do Sal"),("166","Castro Daire"),("167","Cinfães"),("168","Lamego"),("169","Mangualde"),("170","Moimenta da Beira"),("171","Mortágua"),("172","Nelas"),("173","Oliveira de Frades"),("174","Penalva do Castelo"),("175","Penedono"),("176","Resende"),("177","Santa Comba Dão"),("178","São João da Pesqueira"),("179","São Pedro do Sul"),("180","Sátão"),("181","Sernancelhe"),("182","Tabuaço"),("183","Tarouca"),("184","Tondela"),("185","Vila Nova de Paiva"),("186","Viseu"),("187","Vouzela")],
    "17": [("188","Calheta (Madeira)"),("189","Câmara de Lobos"),("190","Funchal"),("191","Machico"),("192","Ponta do Sol"),("193","Porto Moniz"),("194","Ribeira Brava"),("195","Santa Cruz"),("196","Santana"),("197","São Vicente")],
    "18": [("198","Porto Santo")],
    "19": [("199","Vila do Porto")],
    "20": [("200","Lagoa (São Miguel)"),("201","Nordeste"),("202","Ponta Delgada"),("203","Povoação"),("204","Ribeira Grande"),("205","Vila Franca do Campo")],
    "21": [("206","Angra do Heroísmo"),("207","Praia da Vitória")],
    "22": [("208","Santa Cruz da Graciosa")],
    "23": [("209","Calheta (São Jorge)"),("210","Velas")],
    "24": [("211","Lajes do Pico"),("212","Madalena"),("213","São Roque do Pico")],
    "25": [("214","Horta")],
    "26": [("215","Lajes das Flores"),("216","Santa Cruz das Flores")],
    "27": [("217","Corvo")],
    "28": [("49","Águeda"),("50","Albergaria-a-Velha"),("218","Anadia"),("219","Arouca"),("220","Aveiro"),("221","Castelo de Paiva"),("222","Espinho"),("223","Estarreja"),("225","Ílhavo"),("226","Mealhada"),("227","Murtosa"),("228","Oliveira de Azeméis"),("229","Oliveira do Bairro"),("230","Ovar"),("224","Santa Maria da Feira"),("231","São João da Madeira"),("232","Sever do Vouga"),("233","Vagos"),("234","Vale de Cambra")],
    "29": [("235","Aljustrel"),("236","Almodôvar"),("237","Alvito"),("238","Barrancos"),("239","Beja"),("240","Castro Verde"),("241","Cuba"),("242","Ferreira do Alentejo"),("243","Mértola"),("244","Moura"),("245","Odemira"),("246","Ourique"),("247","Serpa"),("248","Vidigueira")],
    "30": [("309","Estrangeiro")],
}

# Valores confirmados do portal (value do <option> → label)
OPCOES_TIPO_FICHEIRO_ESC = {
    "0":   "-> Selecione <-",
    "DIP": "Diploma",
    "CDQ": "Certificado",
    "CFR": "Certidão de Frequência",
    "CEQ": "Certidão de Equivalência de Habilitações Estrangeiras",
    "OUT": "Outro documento",  # activa campo tfOutroTipo
}

# ── Dataclass de resultado de pesquisa ───────────────────────────────────────
@dataclass
class Formando:
    n_sigo:         str = ""
    nif:            str = ""
    nome:           str = ""
    n_identificacao:str = ""
    data_nascimento:str = ""


@dataclass
class Inscricao:
    tipo:               str = ""  # "E" = via entidade
    cod_sigo:           str = ""  # código SIGO da entidade
    entidade:           str = ""
    data:               str = ""  # aaaa/mm/dd
    escolaridade:       str = ""  # escolaridade de entrada
    estado_esc_cod:     str = ""  # código estado escolar  (col 5)
    estado_prof_cod:    str = ""  # código estado profissional (col 6)
    estado_esc_desc:    str = ""  # descrição estado escolar (col 7)
    estado_prof_desc:   str = ""  # descrição estado profissional + data (col 8)
    modalidade:         str = ""  # ex: FM = Formação Modular

# Códigos de estado — confirmados pelos dados reais do portal e pelo utilizador
ESTADOS_INSCRICAO = {
    "INS": "Inscrito",
    "CEP": "Certificado Parcial",
    "CER": "Certificado",
    "DES": "Desistência",
    "ENC": "Encaminhado",       # confirmado na imagem: "2020/09/25 Encaminhado (EFA)"
    # "ANU": "Anulado"          # por confirmar nos dados reais
    # "EXC": "Excluído"         # por confirmar nos dados reais
}

# Tipos de inscrição (coluna 0) — podem existir outros tipos ainda não observados
TIPOS_INSCRICAO = {
    "E":    "Entidade",
    "CQLF": "Centro Qualifica",  # encaminham formandos para EFA/RVCC — código SIGO pode ter 7 dígitos
}

def descricao_tipo(tipo: str) -> str:
    """Devolve a descrição do tipo de inscrição, ou o próprio código se desconhecido."""
    return TIPOS_INSCRICAO.get(tipo, tipo)


def descricao_estado(estado: str) -> str:
    """Devolve a descrição do estado de inscrição, ou o próprio código se desconhecido."""
    return ESTADOS_INSCRICAO.get(estado, estado)


# ── Funções públicas ──────────────────────────────────────────────────────────

async def navegar(page: Page) -> None:
    """Navega para a página de gestão de formandos."""
    if URL not in page.url:
        await page.goto(URL)
        await page.wait_for_load_state("networkidle")


async def pesquisar(
    page: Page,
    *,
    n_sigo: str = "",
    nome: str = "",
    n_identificacao: str = "",
    nif: str = "",
    data_nascimento: str = "",   # aaaa/mm/dd
) -> list[Formando]:
    """
    Pesquisa formandos. Pelo menos um campo deve ser preenchido.
    Devolve lista de Formando com os dados da tabela.

    Nota: o NIF português tem sempre 9 dígitos. NIFs com outro comprimento
    serão aceites pelo módulo mas o portal devolverá 0 resultados.
    """
    if not any([n_sigo, nome, n_identificacao, nif, data_nascimento]):
        raise ValueError("Pelo menos um campo de pesquisa deve ser preenchido.")

    await navegar(page)

    # Limpar todos os campos antes de preencher (evita pesquisas cruzadas)
    for sel in [SEL_PESQ["n_sigo"], SEL_PESQ["nome"],
                SEL_PESQ["n_identificacao"], SEL_PESQ["nif"],
                SEL_PESQ["data_nascimento"]]:
        await page.fill(sel, "")

    if n_sigo:
        await page.fill(SEL_PESQ["n_sigo"], n_sigo)
    if nome:
        await page.fill(SEL_PESQ["nome"], nome)
    if n_identificacao:
        await page.fill(SEL_PESQ["n_identificacao"], n_identificacao)
    if nif:
        await page.fill(SEL_PESQ["nif"], nif)
    if data_nascimento:
        await page.fill(SEL_PESQ["data_nascimento"], data_nascimento)

    # Usar o link ihFiltrar (hyperlink_submit JSF) — o btSubmit pode apanhar
    # o form errado quando a página tem múltiplos formulários activos
    await page.click(SEL_PESQ["lnk_pesquisar"])
    await page.wait_for_load_state("networkidle")

    return await _ler_tabela(page)


async def abrir(page: Page, n_sigo: str) -> bool:
    """
    Pesquisa pelo Nº SIGO e abre o registo do formando.
    Devolve True se encontrado, False caso contrário.
    """
    resultados = await pesquisar(page, n_sigo=n_sigo)
    if not resultados:
        return False
    # Clica no link do nome (primeira coluna clicável da linha)
    link = page.locator(f"#{SEL_TABELA.replace('#', '').replace('\\:', '\\\\:')} a").first
    await link.click()
    await page.wait_for_load_state("networkidle")
    return True


async def adicionar(page: Page, dados: dict) -> None:
    """
    Abre o formulário de novo formando e preenche os campos fornecidos em `dados`.

    Exemplo de dados:
        {
            "nome": "Maria Silva",
            "genero": "F",            # "F" ou "M"
            "nif": "123456789",
            "email": "maria@email.pt",
            "data_nascimento": "1990/05/15",
            "tipo_doc": "Identificação Civil (CC/BI)",
            "n_identificacao": "12345678",
            "escolaridade": "Licenciatura",
            "nacionalidade": "Portugal",
        }
    """
    await navegar(page)
    await page.click(SEL_PESQ["lnk_adicionar"])
    await page.wait_for_load_state("networkidle")
    await _preencher_form(page, dados)


# ── Seletores — Registo de Inscrições do Formando ────────────────────────────
SEL_INSCRICOES = {
    "tab_cnq":          "Modalidades do CNQ",
    "tab_outras":       "Outras Modalidades",
    "btn_nova":         "#form1\\:ihAdicionar",
    "btn_passaporte":   "#form1\\:ihConsultarCIC",
    "btn_voltar":       "#form1\\:btVoltar",
}


async def abrir_inscricoes(page: Page, n_sigo_formando: str) -> list[Inscricao]:
    """
    Pesquisa o formando pelo Nº SIGO e abre as suas inscrições.
    Devolve a lista de inscrições da tab activa (Modalidades do CNQ).
    """
    resultados = await pesquisar(page, n_sigo=n_sigo_formando)
    if not resultados:
        return []
    await page.evaluate(
        "document.querySelector('#form1\\\\:table1\\\\:tableRowGroup1\\\\:0\\\\:tableColumn7\\\\:ihInscricoes').click()"
    )
    await page.wait_for_load_state("networkidle")
    return await _ler_inscricoes(page)


async def _ler_inscricoes(page: Page) -> list[Inscricao]:
    """Lê as linhas de inscrição da tabela activa (12 colunas confirmadas).

    Nota: o código SIGO da entidade pode ter 4, 5 ou 7 dígitos (ex: 1035155 para CQLF).
    O tipo pode ser "E" (Entidade) ou "CQLF" (Qualificação/EFA).
    """
    raw = await page.evaluate("""
    Array.from(document.querySelectorAll('tr')).filter(tr => {
        const cells = tr.querySelectorAll('td');
        return cells.length >= 6 && cells[1]?.innerText.trim().match(/^\\d{4,7}$/);
    }).map(tr => {
        const c = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
        return {
            tipo:             c[0],
            cod_sigo:         c[1],
            entidade:         c[2],
            data:             c[3],
            escolaridade:     c[4],
            estado_esc_cod:   c[5],
            estado_prof_cod:  c[6],
            estado_esc_desc:  c[7],
            estado_prof_desc: c[8],
            modalidade:       c[9],
        };
    })
    """)
    return [Inscricao(**r) for r in raw]


async def abrir_passaporte_qualifica(page: Page) -> "Page":
    """
    Clica em 'Passaporte Qualifica' e devolve a página do popup.

    O botão abre uma janela popup — o Playwright intercepta-a via evento 'popup'.
    Deve ser chamado quando o registo de inscrições do formando está aberto.

    Uso:
        popup = await abrir_passaporte_qualifica(page)
        # trabalhar com o popup...
        await popup.close()
    """
    from playwright.async_api import Page as PlaywrightPage
    async with page.expect_popup() as popup_info:
        await page.click(SEL_INSCRICOES["btn_passaporte"])
    popup: PlaywrightPage = await popup_info.value
    await popup.wait_for_load_state("networkidle")
    return popup


async def gravar(page: Page) -> None:
    """Grava o formando actualmente aberto no formulário."""
    await page.click(SEL_FORM["btn_gravar"])
    await page.wait_for_load_state("networkidle")


async def voltar(page: Page) -> None:
    """Regressa à lista de formandos."""
    await page.click(SEL_FORM["btn_voltar"])
    await page.wait_for_load_state("networkidle")


async def importar_excel(page: Page, caminho_ficheiro: str) -> None:
    """
    Importa formandos a partir de um ficheiro Excel (.xls ou .xlsx).

    Fluxo:
      1. Abre o painel de importação (se fechado)
      2. Carrega o ficheiro
      3. Clica em Gravar

    Para descarregar o template antes de preencher, use:
        await page.click(SEL_IMPORTAR["template_xlsx"])

    Nota: o ficheiro deve seguir o formato do template oficial SIGO.
    """
    await navegar(page)
    # Abre o painel clicando em "Importar"
    await page.click(SEL_IMPORTAR["btn_toggle"])
    await page.wait_for_timeout(500)
    # Carrega o ficheiro no input
    await page.set_input_files(SEL_IMPORTAR["file_upload"], caminho_ficheiro)
    # Submete
    await page.click(SEL_IMPORTAR["btn_gravar"])
    await page.wait_for_load_state("networkidle")


# ── Funções internas ──────────────────────────────────────────────────────────

async def _ler_tabela(page: Page) -> list[Formando]:
    """Lê todas as linhas da tabela de resultados."""
    rows_js = """
    (() => {
        const rows = Array.from(document.querySelectorAll('#form1\\\\:table1 tbody tr'));
        return rows.map(r => {
            const cells = Array.from(r.querySelectorAll('td'));
            if (cells.length < 5) return null;
            return {
                n_sigo:          cells[0]?.innerText?.trim(),
                nif:             cells[1]?.innerText?.trim(),
                nome:            cells[2]?.innerText?.trim(),
                n_identificacao: cells[3]?.innerText?.trim(),
                data_nascimento: cells[4]?.innerText?.trim(),
            };
        }).filter(Boolean);
    })()
    """
    raw = await page.evaluate(rows_js)
    return [Formando(**r) for r in raw]


async def _preencher_form(page: Page, dados: dict) -> None:
    """Preenche o formulário de formando com o dicionário de dados."""
    mapa = {
        "nome":            (SEL_FORM["nome"],            "fill"),
        "nif":             (SEL_FORM["nif"],             "fill"),
        "niss":            (SEL_FORM["niss"],            "fill"),
        "n_identificacao": (SEL_FORM["n_identificacao"], "fill"),
        "check_digit_cc":  (SEL_FORM["check_digit_cc"],  "fill"),
        "data_nascimento": (SEL_FORM["data_nascimento"],  "fill"),
        "data_validade":   (SEL_FORM["data_validade"],   "fill"),
        "telefone1":       (SEL_FORM["telefone1"],       "fill"),
        "telefone2":       (SEL_FORM["telefone2"],       "fill"),
        "email":           (SEL_FORM["email"],           "fill"),
        "outra_nacionalidade":  (SEL_FORM["outra_nacionalidade"],  "fill"),
        "outro_pais_origem":    (SEL_FORM["outro_pais_origem"],    "fill"),
        "tipo_doc":        (SEL_FORM["tipo_doc"],        "select"),
        "subtipo_doc":     (SEL_FORM["subtipo_doc"],     "select"),
        "pais_emissor":    (SEL_FORM["pais_emissor"],    "select"),
        "emitido_por":     (SEL_FORM["emitido_por"],     "select"),
        "nacionalidade":   (SEL_FORM["nacionalidade"],   "select"),
        "pais_origem":     (SEL_FORM["pais_origem"],     "select"),
        "distrito":        (SEL_FORM["distrito"],        "select"),
        "concelho":        (SEL_FORM["concelho"],        "select"),
        "escolaridade":    (SEL_FORM["escolaridade"],    "select"),
    }

    for campo, valor in dados.items():
        if campo == "genero":
            sel = SEL_FORM["genero_feminino"] if valor.upper() == "F" else SEL_FORM["genero_masculino"]
            await page.check(sel)
            continue
        if campo == "confidencial":
            if valor:
                await page.check(SEL_FORM["confidencial"])
            continue
        if campo not in mapa:
            continue
        sel, acao = mapa[campo]
        if acao == "fill":
            await page.fill(sel, str(valor))
        elif acao == "select":
            await page.select_option(sel, label=str(valor))
