"""
Geração do PDF "Quadro Completo" do QL (Quadro de Lotação).

Reaproveita a mesma separação por Departamento -> Função exibida na tela
(ver app.py), incluindo os badges "Orçado x Real x Vagas" quando disponíveis,
e gera um PDF paisagem pronto para impressão/arquivo.

Bibliotecas: reportlab (pura Python, sem dependências de sistema — funciona
sem ajustes no Streamlit Community Cloud).
"""

import re
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# =========================================================
# 🎨 PALETA (mesma identidade visual do app)
# =========================================================
AZUL_INSTITUCIONAL = colors.HexColor("#0B3D63")
MAGENTA = colors.HexColor("#E5007D")
VERDE_GERENTE = colors.HexColor("#047857")
VERMELHO_RH = colors.HexColor("#be123c")
AZUL_CLARO = colors.HexColor("#DCEBF7")
BORDA = colors.HexColor("#C4D4E0")
TEXTO_ESCURO = colors.HexColor("#22303C")
CINZA_TEXTO = colors.HexColor("#5B6B78")

CORES_STATUS = {
    "ATIVO": colors.HexColor("#DCFCE7"),
    "FÉRIAS": colors.HexColor("#DBEAFE"),
    "FERIAS": colors.HexColor("#DBEAFE"),
    "AFASTAMENTO": colors.HexColor("#FFEDD5"),
    "AFASTADO": colors.HexColor("#FFEDD5"),
    "DEMITIDO": colors.HexColor("#FEE2E2"),
}

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⬀-⯿←-⇿]+",
    flags=re.UNICODE,
)


def _sem_emoji(texto):
    return _EMOJI_RE.sub("", str(texto)).strip(" -—")


def _limpar_valor(valor):
    if valor is None:
        return "-"
    try:
        if pd.isna(valor):
            return "-"
    except (TypeError, ValueError):
        pass
    texto = str(valor).strip()
    if texto.lower() in ("nan", "none", "null", "nat", "<na>", ""):
        return "-"
    return texto


def _cor_status(situacao):
    s = str(situacao).strip().upper()
    for chave, cor in CORES_STATUS.items():
        if chave in s:
            return cor
    return colors.white


# Rótulos e larguras (mm) na mesma ordem usada na tela (colunas_selecionadas)
COLUNAS_INFO = {
    "Situação": ("Status", 20),
    "Loja": ("Loja", 11),
    "Nome": ("Nome do Colaborador", 32),
    "Horario_Sistema_Real": ("Horário Sistema", 15),
    "Data Abertura": ("Data Abertura", 15),
    "Responsável": ("Responsável", 20),
    "Horário Contrato": ("Horário Contrato", 15),
    "Sexo": ("Sexo", 8),
    "Motivo": ("Motivo", 23),
    "Observação": ("Observação", 36),
    "Status RH": ("Status RH", 18),
    "Candidato": ("Candidato", 20),
    "Data Admissão": ("Data Admissão", 16),
}


def _estilos():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Heading1"], fontSize=16,
            textColor=AZUL_INSTITUCIONAL, spaceAfter=2, fontName="Helvetica-Bold",
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", parent=base["Normal"], fontSize=9,
            textColor=CINZA_TEXTO, spaceAfter=2,
        ),
        "dept": ParagraphStyle(
            "dept", parent=base["Normal"], fontSize=11, leading=13,
            textColor=colors.white, fontName="Helvetica-Bold",
        ),
        "funcao": ParagraphStyle(
            "funcao", parent=base["Normal"], fontSize=9.5, leading=12,
            textColor=AZUL_INSTITUCIONAL, fontName="Helvetica-Bold",
            spaceBefore=7, spaceAfter=3, keepWithNext=True,
        ),
        "cab_grupo": ParagraphStyle(
            "cab_grupo", parent=base["Normal"], fontSize=7.3, leading=9,
            textColor=colors.white, alignment=TA_CENTER, fontName="Helvetica-Bold",
        ),
        "cab_col": ParagraphStyle(
            "cab_col", parent=base["Normal"], fontSize=6.6, leading=8,
            textColor=TEXTO_ESCURO, alignment=TA_CENTER, fontName="Helvetica-Bold",
        ),
        "celula": ParagraphStyle(
            "celula", parent=base["Normal"], fontSize=6.4, leading=7.6,
            textColor=TEXTO_ESCURO, alignment=TA_LEFT,
        ),
        "celula_c": ParagraphStyle(
            "celula_c", parent=base["Normal"], fontSize=6.4, leading=7.6,
            textColor=TEXTO_ESCURO, alignment=TA_CENTER,
        ),
        "resumo_num": ParagraphStyle(
            "resumo_num", parent=base["Normal"], fontSize=13, leading=15,
            textColor=AZUL_INSTITUCIONAL, alignment=TA_CENTER, fontName="Helvetica-Bold",
        ),
        "resumo_label": ParagraphStyle(
            "resumo_label", parent=base["Normal"], fontSize=7.5, leading=9,
            textColor=CINZA_TEXTO, alignment=TA_CENTER,
        ),
        "rodape": ParagraphStyle(
            "rodape", parent=base["Normal"], fontSize=7, textColor=CINZA_TEXTO,
        ),
    }


def _bloco_resumo(contadores, estilos):
    """Cards de resumo (Ativos/Férias/Demitidos/Afastados/Alterados/Admitidos)."""
    linha_num, linha_label = [], []
    for label, valor in contadores.items():
        linha_num.append(Paragraph(str(valor), estilos["resumo_num"]))
        linha_label.append(Paragraph(label, estilos["resumo_label"]))
    largura_col = (277 * mm) / max(len(contadores), 1)
    tabela = Table(
        [linha_num, linha_label],
        colWidths=[largura_col] * len(contadores),
    )
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F6FA")),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDA),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDA),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
                ("TOPPADDING", (0, 1), (-1, 1), 0),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
            ]
        )
    )
    return tabela


def _cabecalho_departamento(dept, total, info_orcado, estilos):
    texto = f"DEPARTAMENTO: {dept}  —  {total} colaborador(es)"
    info_limpa = _sem_emoji(info_orcado)
    if info_limpa:
        texto += f"   |   {info_limpa}"
    p = Paragraph(texto, estilos["dept"])
    tabela = Table([[p]], colWidths=[277 * mm])
    tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AZUL_INSTITUCIONAL),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tabela


def _tabela_funcao(df_filtrado, modo_visao_global, estilos):
    colunas = list(df_filtrado.columns)
    n_colunas = len(colunas)
    colspan_analista = 4 if modo_visao_global else 3
    colspan_gerente = 6
    colspan_rh = 3

    linha_grupo = (
        [Paragraph("DONO: ANALISTA", estilos["cab_grupo"])] + [""] * (colspan_analista - 1)
        + [Paragraph("DONO: GERENTE", estilos["cab_grupo"])] + [""] * (colspan_gerente - 1)
        + [Paragraph("DONO: RH", estilos["cab_grupo"])] + [""] * (colspan_rh - 1)
    )
    linha_cab = [
        Paragraph(COLUNAS_INFO.get(c, (c, 18))[0], estilos["cab_col"]) for c in colunas
    ]

    dados = [linha_grupo, linha_cab]
    cores_linha = []
    for _, row in df_filtrado.iterrows():
        linha = []
        for c in colunas:
            valor = _limpar_valor(row[c])
            if c == "Nome":
                valor = valor.title()
            elif c == "Loja":
                try:
                    valor = f"{int(float(valor)):02d}"
                except (TypeError, ValueError):
                    pass
            estilo_cel = estilos["celula_c"] if c in ("Situação", "Loja", "Status RH", "Sexo") else estilos["celula"]
            linha.append(Paragraph(valor, estilo_cel))
        dados.append(linha)
        cores_linha.append(_cor_status(row.get("Situação", "")))

    largura_colunas = [COLUNAS_INFO.get(c, (c, 18))[1] * mm for c in colunas]

    estilo = [
        ("SPAN", (0, 0), (colspan_analista - 1, 0)),
        ("SPAN", (colspan_analista, 0), (colspan_analista + colspan_gerente - 1, 0)),
        (
            "SPAN",
            (colspan_analista + colspan_gerente, 0),
            (colspan_analista + colspan_gerente + colspan_rh - 1, 0),
        ),
        ("BACKGROUND", (0, 0), (colspan_analista - 1, 0), AZUL_INSTITUCIONAL),
        (
            "BACKGROUND",
            (colspan_analista, 0),
            (colspan_analista + colspan_gerente - 1, 0),
            VERDE_GERENTE,
        ),
        (
            "BACKGROUND",
            (colspan_analista + colspan_gerente, 0),
            (n_colunas - 1, 0),
            VERMELHO_RH,
        ),
        ("BACKGROUND", (0, 1), (-1, 1), AZUL_CLARO),
        ("GRID", (0, 0), (-1, -1), 0.35, BORDA),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    for i, cor in enumerate(cores_linha, start=2):
        if cor != colors.white:
            estilo.append(("BACKGROUND", (0, i), (-1, i), cor))

    tabela = Table(dados, colWidths=largura_colunas, repeatRows=2)
    tabela.setStyle(TableStyle(estilo))
    return tabela


def gerar_pdf_quadro(
    texto_titulo,
    contadores,
    departamentos,
    modo_visao_global,
    subtitulo_filtro="TODOS",
    focar_colaborador=None,
):
    """Gera o PDF do quadro completo, agrupado por Departamento -> Função.

    Args:
        texto_titulo: título da loja/visão selecionada (ex.: "Loja 06", "Total Rede").
        contadores: dict {"Ativos": n, "Férias": n, ...} — mesmos cards do topo.
        departamentos: lista de dicts:
            {"dept": str, "total": int, "info_orcado": str,
             "funcoes": [{"funcao": str, "info_orcado": str, "df": DataFrame}, ...]}
            (mesma estrutura acumulada durante a renderização em tela)
        modo_visao_global: True quando a visão inclui a coluna "Loja" (Total Lojas/Rede).
        subtitulo_filtro: valor de st.session_state["filtro_cards"] no momento da geração.
        focar_colaborador: nome do colaborador, se o filtro "Focar colaborador" estiver ativo.

    Returns:
        bytes do PDF pronto para st.download_button.
    """
    estilos = _estilos()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        title=f"QL - {texto_titulo}",
    )

    agora_br = datetime.now() - timedelta(hours=3)  # Streamlit Cloud roda em UTC
    elementos = [
        Paragraph("Molicenter — Quadro de Lotação (QL)", estilos["titulo"]),
        Paragraph(
            f"{texto_titulo} &nbsp;·&nbsp; Gerado em {agora_br.strftime('%d/%m/%Y às %H:%M')} (horário de Brasília)",
            estilos["subtitulo"],
        ),
    ]

    filtros_ativos = []
    if subtitulo_filtro not in ("TODOS", None):
        rotulos_filtro = {
            "ATIVO": "Ativos", "FERIAS": "Férias", "DEMITIDO": "Demitidos",
            "AFASTADO": "Afastados", "ALTERADOS": "Alterados", "ADMITIDOS": "Admitidos",
        }
        filtros_ativos.append(f"Filtro de status: {rotulos_filtro.get(subtitulo_filtro, subtitulo_filtro)}")
    if focar_colaborador:
        filtros_ativos.append(f"Focado no colaborador: {focar_colaborador.title()}")
    if filtros_ativos:
        elementos.append(Paragraph(" | ".join(filtros_ativos), estilos["subtitulo"]))

    elementos.append(Spacer(1, 4 * mm))
    elementos.append(_bloco_resumo(contadores, estilos))
    elementos.append(Spacer(1, 6 * mm))

    if not departamentos:
        elementos.append(Paragraph("Nenhum registro encontrado para esta seleção.", estilos["subtitulo"]))

    for item in departamentos:
        elementos.append(_cabecalho_departamento(item["dept"], item["total"], item["info_orcado"], estilos))
        elementos.append(Spacer(1, 2 * mm))
        for info_funcao in item["funcoes"]:
            texto_funcao = f"Cargo: {info_funcao['funcao']}"
            info_limpa = _sem_emoji(info_funcao["info_orcado"])
            if info_limpa:
                texto_funcao += f"  —  {info_limpa}"
            elementos.append(Paragraph(texto_funcao, estilos["funcao"]))
            elementos.append(_tabela_funcao(info_funcao["df"], modo_visao_global, estilos))
        elementos.append(Spacer(1, 5 * mm))

    doc.build(elementos)
    return buffer.getvalue()
