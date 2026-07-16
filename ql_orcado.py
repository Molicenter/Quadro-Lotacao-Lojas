# -*- coding: utf-8 -*-
"""
=====================================================================
📐 VISÃO QL ORÇADO (ORGANOGRAMA) - Molicenter
=====================================================================
Reproduz o organograma de funções da planilha Excel dentro do app:
cards por departamento/função, cabeçalho com venda e parâmetros,
e rodapé Total / Real / Diferença.

- Visão por loja individual ou agregada (Total Lojas / Total Rede)
- Valores orçados e parâmetros editáveis (perfis Admin/Analista e RH)
- 'Real' é calculado automaticamente do quadro: Ativos + Férias
  (mesma regra dos cards do topo do app)
- Regra herdada do Excel: funções com conta_no_total = false
  (ex.: Aprendiz) não entram no Total geral

Tabelas Supabase: ql_orcado, ql_parametros_loja
Integração no app.py: ver instruções no final do arquivo.
=====================================================================
"""

import unicodedata

import pandas as pd
import streamlit as st

LOJAS_PADRAO = [1, 2, 3, 4, 5, 6, 7, 8]

# Cores por departamento (mesma paleta da planilha)
CORES_DEPT = {
    "GERÊNCIA":       {"bg": "#0B3D63", "fg": "#FFFFFF"},
    "FRENTE CAIXA":   {"bg": "#14507F", "fg": "#FFFFFF"},
    "LOJA":           {"bg": "#2E86C1", "fg": "#FFFFFF"},
    "AÇOUGUE":        {"bg": "#C0392B", "fg": "#FFFFFF"},
    "HORTFRUTI":      {"bg": "#1E5631", "fg": "#FFFFFF"},
    "FRIOS":          {"bg": "#34495E", "fg": "#FFFFFF"},
    "PADARIA":        {"bg": "#F0B27A", "fg": "#22303C"},
    "CONFEITARIA":    {"bg": "#F0B27A", "fg": "#22303C"},
    "ROTISSERIA":     {"bg": "#F0B27A", "fg": "#22303C"},
    "DEPÓSITO":       {"bg": "#5D6D7E", "fg": "#FFFFFF"},
    "ADMINISTRATIVO": {"bg": "#566573", "fg": "#FFFFFF"},
}
COR_PADRAO = {"bg": "#0B3D63", "fg": "#FFFFFF"}


# =====================================================================
# 📥 CARGA DE DADOS
# =====================================================================
@st.cache_data(ttl=300)
def carregar_ql_orcado(_supabase):
    """Busca orçado e parâmetros no Supabase e devolve dois DataFrames."""
    resp_orc = (
        _supabase.table("ql_orcado")
        .select("*")
        .order("loja")
        .order("ordem_dept")
        .order("ordem_funcao")
        .execute()
    )
    resp_par = _supabase.table("ql_parametros_loja").select("*").execute()

    df_orc = pd.DataFrame(resp_orc.data) if resp_orc.data else pd.DataFrame(
        columns=["loja", "departamento", "funcao", "quantidade",
                 "conta_no_total", "ordem_dept", "ordem_funcao"]
    )
    df_par = pd.DataFrame(resp_par.data) if resp_par.data else pd.DataFrame(
        columns=["loja", "venda", "media_6_meses", "venda_por_funcionario",
                 "proposta_quant", "real_quadro", "abertura_seg_sab", "abertura_domingo"]
    )
    return df_orc, df_par


# =====================================================================
# 🔧 AUXILIARES
# =====================================================================
def _fmt_moeda(valor):
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return "-"
    txt = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {txt}"


def _fmt_int(valor):
    try:
        return f"{int(valor)}"
    except (TypeError, ValueError):
        return "-"


def _calcular_real(df_quadro):
    """Real = colaboradores Ativos + Férias no quadro atual (mesma regra
    dos cards do topo do app). Retorna None se o quadro não for informado."""
    if df_quadro is None or df_quadro.empty or "Situação" not in df_quadro.columns:
        return None
    sit = df_quadro["Situação"].astype(str).str.upper()
    mask = sit.str.contains("ATIVO", na=False) | sit.str.contains("FÉRIAS|FERIAS", na=False)
    return int(mask.sum())


# =====================================================================
# 🔗 INTEGRAÇÃO COM OS EXPANDERS DE DEPARTAMENTO DO app.py
# (mostra Orçado x Real no título de cada departamento/cargo)
# =====================================================================
def _normalizar(txt):
    """Remove acentos, coloca em maiúsculas e normaliza espaços,
    para casar nomes do quadro com nomes do orçado."""
    txt = str(txt or "").strip().upper()
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return " ".join(txt.split())


# De-para: nome do departamento NO QUADRO -> destino NO ORÇADO.
# Valor string  = departamento inteiro do orçado.
# Valor tupla   = (departamento, função) específica do orçado
#                 (para deptos do quadro que no orçado são só uma função).
# ✏️ AJUSTE AQUI se surgir departamento novo sem correspondência.
DE_PARA_DEPT = {
    "FRENTE DE CAIXA": "FRENTE CAIXA",
    "ENTREGA":         ("FRENTE CAIXA", "ENTREGADOR"),
    "HORTIFRUTI":      "HORTFRUTI",
    "GERENCIA":        "GERENCIA",
    "LIMPEZA":         ("ADMINISTRATIVO", "LIMPEZA"),
    "PREVENCAO":       ("ADMINISTRATIVO", "PREVENCAO"),
    "CONTROLADORIA":   ("ADMINISTRATIVO", "CONTROLADORIA"),
}


@st.cache_data(ttl=300)
def carregar_mapas_orcado(_supabase, loja_selecionada):
    """Monta dicionários de consulta do orçado para a seleção atual:
    {dept_normalizado: qtd} e {(dept_norm, funcao_norm): qtd}."""
    df_orc, _ = carregar_ql_orcado(_supabase)
    if df_orc.empty:
        return {}, {}

    if isinstance(loja_selecionada, int):
        df_sel = df_orc[df_orc["loja"] == int(loja_selecionada)]
    else:  # Total Lojas / Total Rede -> orçado cadastrado (lojas 01 a 08)
        df_sel = df_orc[df_orc["loja"].isin(LOJAS_PADRAO)]

    if df_sel.empty:
        return {}, {}

    df_sel = df_sel.copy()
    df_sel["dept_n"] = df_sel["departamento"].map(_normalizar)
    df_sel["func_n"] = df_sel["funcao"].map(_normalizar)

    mapa_dept = df_sel.groupby("dept_n")["quantidade"].sum().to_dict()
    mapa_func = df_sel.groupby(["dept_n", "func_n"])["quantidade"].sum().to_dict()
    return mapa_dept, mapa_func


def _resolver_dept(dept_quadro):
    """Aplica o DE_PARA e devolve o destino normalizado (str ou tupla)."""
    chave = _normalizar(dept_quadro)
    destino = DE_PARA_DEPT.get(chave, chave)
    if isinstance(destino, tuple):
        return (_normalizar(destino[0]), _normalizar(destino[1]))
    return _normalizar(destino)


def obter_orcado_dept(mapa_dept, mapa_func, dept_quadro):
    """Qtd orçada do departamento do quadro (ou None se não mapeado)."""
    destino = _resolver_dept(dept_quadro)
    if isinstance(destino, tuple):
        return mapa_func.get(destino)
    return mapa_dept.get(destino)


def obter_orcado_funcao(mapa_func, dept_quadro, funcao_quadro):
    """Qtd orçada de uma função do quadro (ou None se não mapeada)."""
    destino = _resolver_dept(dept_quadro)
    if isinstance(destino, tuple):
        # Depto do quadro que corresponde a UMA função do orçado
        return mapa_func.get(destino)
    return mapa_func.get((destino, _normalizar(funcao_quadro)))


def badge_orcado(orcado, real):
    """Sufixo 'Orçado x Real x Vagas' para títulos de expander/cargo.
    Retorna string vazia quando não há orçado mapeado."""
    if orcado is None:
        return ""
    orcado, real = int(orcado), int(real)
    saldo = orcado - real
    if saldo > 0:
        status = f"🟢 {saldo} vaga" + ("s" if saldo > 1 else "")
    elif saldo == 0:
        status = "⚪ completo"
    else:
        status = f"🔴 {abs(saldo)} acima"
    return f" — 🎯 Orçado: {orcado} | Real: {real} | {status}"


def _agregar(df_orc, df_par, lojas):
    """Soma quantidades e parâmetros das lojas informadas (visão Total)."""
    df_o = df_orc[df_orc["loja"].isin(lojas)].copy()
    if df_o.empty:
        return df_o, {}

    df_agg = (
        df_o.groupby(["departamento", "funcao"], as_index=False)
        .agg(quantidade=("quantidade", "sum"),
             conta_no_total=("conta_no_total", "min"),
             ordem_dept=("ordem_dept", "min"),
             ordem_funcao=("ordem_funcao", "min"))
        .sort_values(["ordem_dept", "ordem_funcao"])
    )

    df_p = df_par[df_par["loja"].isin(lojas)]
    params = {
        "venda": df_p["venda"].sum() if not df_p.empty else None,
        "media_6_meses": df_p["media_6_meses"].sum() if not df_p.empty else None,
        # Nas visões agregadas, exibimos a média simples do R$/funcionário
        "venda_por_funcionario": df_p["venda_por_funcionario"].mean() if not df_p.empty else None,
        "proposta_quant": df_p["proposta_quant"].sum() if not df_p.empty else None,
        "real_quadro": df_p["real_quadro"].sum() if not df_p.empty else None,
        "abertura_seg_sab": "08:00 as 21:00",
        "abertura_domingo": "08:00 as 20:00",
    }
    return df_agg, params


# =====================================================================
# 🎨 RENDERIZAÇÃO HTML DO ORGANOGRAMA
# =====================================================================
def _montar_html(df_view, params, titulo):
    total_geral = int(df_view.loc[df_view["conta_no_total"] == True, "quantidade"].sum())
    real = params.get("real_quadro")
    diferenca = (int(real) - total_geral) if real is not None and not pd.isna(real) else None

    # Diferença <= 0: dentro/abaixo do orçado (verde). > 0: acima (vermelho).
    if diferenca is None:
        cor_dif_bg, cor_dif_fg, txt_dif = "#F2F6FA", "#64748B", "-"
    elif diferenca <= 0:
        cor_dif_bg, cor_dif_fg, txt_dif = "#D1FAE5", "#047857", f"{diferenca}"
    else:
        cor_dif_bg, cor_dif_fg, txt_dif = "#FEE2E2", "#991B1B", f"+{diferenca}"

    css = """
    <style>
    .org-wrap { font-family: sans-serif; color:#22303C; }
    .org-titulo { background:#0B3D63; color:#fff; text-align:center; font-size:18px;
        font-weight:700; padding:10px; border-radius:6px; margin-bottom:12px; }
    .org-header { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:14px; }
    .org-kpi { flex:1; min-width:150px; border:1px solid #C4D4E0; border-radius:6px; overflow:hidden; }
    .org-kpi .k-lab { background:#14507F; color:#fff; font-size:11.5px; font-weight:600;
        text-align:center; padding:6px 8px; }
    .org-kpi .k-val { background:#fff; font-size:14px; font-weight:700;
        text-align:center; padding:8px 6px; }
    .org-depts { display:flex; flex-wrap:wrap; gap:10px; align-items:flex-start; }
    .org-col { flex:1; min-width:128px; max-width:190px; display:flex; flex-direction:column; gap:6px; }
    .org-dept-head { font-size:11.5px; font-weight:700; text-align:center; padding:7px 4px;
        border-radius:5px 5px 0 0; letter-spacing:0.3px; }
    .org-func { border:1px solid #D5E0EA; border-radius:5px; overflow:hidden; }
    .org-func .f-lab { font-size:11px; font-weight:600; text-align:center; padding:5px 4px; }
    .org-func .f-val { background:#fff; font-size:13px; font-weight:700; text-align:center; padding:5px; }
    .org-func .f-val.zero { color:#94A3B8; font-weight:500; }
    .org-total-dept { border:2px solid #0B3D63; border-radius:5px; overflow:hidden; margin-top:2px; }
    .org-total-dept .f-lab { background:#0B3D63; color:#fff; font-size:11px; font-weight:700;
        text-align:center; padding:5px; }
    .org-total-dept .f-val { background:#DCEBF7; font-size:14px; font-weight:800;
        text-align:center; padding:6px; }
    .org-rodape { display:flex; gap:12px; justify-content:center; margin-top:18px; }
    .org-big { min-width:150px; border-radius:6px; overflow:hidden; border:1px solid #C4D4E0; }
    .org-big .k-lab { background:#0B3D63; color:#fff; font-size:13px; font-weight:700;
        text-align:center; padding:8px; }
    .org-big .k-val { font-size:20px; font-weight:800; text-align:center; padding:10px; background:#fff; }
    .org-nota { font-size:11px; color:#64748B; text-align:center; margin-top:8px; }
    </style>
    """

    html = css + '<div class="org-wrap">'
    html += f'<div class="org-titulo">{titulo}</div>'

    # ------- Cabeçalho (KPIs) -------
    html += '<div class="org-header">'
    kpis = [
        ("Venda", _fmt_moeda(params.get("venda"))),
        ("Média 6 Meses", _fmt_moeda(params.get("media_6_meses"))),
        ("Venda R$ / Funcionário", _fmt_moeda(params.get("venda_por_funcionario"))),
        ("Proposta Quant", _fmt_int(params.get("proposta_quant"))),
        ("Seg a Sáb", params.get("abertura_seg_sab") or "-"),
        ("Domingos", params.get("abertura_domingo") or "-"),
    ]
    for lab, val in kpis:
        html += (f'<div class="org-kpi"><div class="k-lab">{lab}</div>'
                 f'<div class="k-val">{val}</div></div>')
    html += '</div>'

    # ------- Colunas por departamento -------
    html += '<div class="org-depts">'
    ordem_depts = (
        df_view.sort_values("ordem_dept")["departamento"].drop_duplicates().tolist()
    )
    for dept in ordem_depts:
        cor = CORES_DEPT.get(dept, COR_PADRAO)
        df_d = df_view[df_view["departamento"] == dept].sort_values("ordem_funcao")
        total_dept = int(df_d["quantidade"].sum())

        html += '<div class="org-col">'
        html += (f'<div class="org-dept-head" style="background:{cor["bg"]};'
                 f'color:{cor["fg"]};">{dept}</div>')
        for _, row in df_d.iterrows():
            qtd = int(row["quantidade"])
            marcador = "" if bool(row["conta_no_total"]) else " *"
            classe_val = "f-val zero" if qtd == 0 else "f-val"
            html += (f'<div class="org-func">'
                     f'<div class="f-lab" style="background:{cor["bg"]};color:{cor["fg"]};">'
                     f'{row["funcao"]}{marcador}</div>'
                     f'<div class="{classe_val}">{qtd}</div></div>')
        html += (f'<div class="org-total-dept"><div class="f-lab">Total</div>'
                 f'<div class="f-val">{total_dept}</div></div>')
        html += '</div>'
    html += '</div>'

    # ------- Rodapé: Total / Real / Diferença -------
    html += '<div class="org-rodape">'
    html += (f'<div class="org-big"><div class="k-lab">Total (Orçado)</div>'
             f'<div class="k-val">{total_geral}</div></div>')
    html += (f'<div class="org-big"><div class="k-lab">Real (Ativos + Férias)</div>'
             f'<div class="k-val">{_fmt_int(real)}</div></div>')
    html += (f'<div class="org-big"><div class="k-lab">Diferença</div>'
             f'<div class="k-val" style="background:{cor_dif_bg};color:{cor_dif_fg};">'
             f'{txt_dif}</div></div>')
    html += '</div>'
    html += ('<div class="org-nota">* Funções marcadas não entram no Total geral '
             '(ex.: Aprendiz), seguindo o critério da planilha. '
             'Real = Ativos + Férias do quadro atual.</div>')
    html += '</div>'
    return html


# =====================================================================
# ✏️ MODO DE EDIÇÃO (Admin/Analista e RH)
# =====================================================================
def _renderizar_edicao(supabase, df_orc, df_par, loja_edicao, usuario):
    st.markdown(f"#### ✏️ Editar Valores Orçados — Loja {loja_edicao:02d}")

    df_loja = df_orc[df_orc["loja"] == loja_edicao].sort_values(
        ["ordem_dept", "ordem_funcao"]
    ).copy()
    if df_loja.empty:
        st.warning("Nenhum valor orçado cadastrado para esta loja. "
                   "Rode o script de seed no Supabase primeiro.")
        return

    # --- Parâmetros do cabeçalho ---
    par = df_par[df_par["loja"] == loja_edicao]
    par = par.iloc[0].to_dict() if not par.empty else {}

    c1, c2, c3 = st.columns(3)
    with c1:
        nova_venda = st.number_input(
            "Venda (R$):", min_value=0.0, step=1000.0, format="%.2f",
            value=float(par.get("venda") or 0.0))
        nova_proposta = st.number_input(
            "Proposta Quant:", min_value=0, step=1,
            value=int(par.get("proposta_quant") or 0))
    with c2:
        nova_media = st.number_input(
            "Média 6 Meses (R$):", min_value=0.0, step=1000.0, format="%.2f",
            value=float(par.get("media_6_meses") or 0.0))
        st.caption("ℹ️ O valor **Real** é calculado automaticamente "
                   "(Ativos + Férias do quadro) e não precisa ser digitado.")
    with c3:
        nova_venda_func = st.number_input(
            "Venda R$ / Funcionário:", min_value=0.0, step=500.0, format="%.2f",
            value=float(par.get("venda_por_funcionario") or 0.0))

    # --- Quantidades por função ---
    df_editor = df_loja[["departamento", "funcao", "quantidade", "conta_no_total"]].copy()
    df_editado = st.data_editor(
        df_editor,
        hide_index=True,
        use_container_width=True,
        disabled=["departamento", "funcao"],
        column_config={
            "departamento": st.column_config.TextColumn("Departamento"),
            "funcao": st.column_config.TextColumn("Função"),
            "quantidade": st.column_config.NumberColumn(
                "Qtd Orçada", min_value=0, step=1),
            "conta_no_total": st.column_config.CheckboxColumn(
                "Conta no Total?",
                help="Desmarcado = não entra no Total geral (ex.: Aprendiz)"),
        },
        key=f"editor_ql_orcado_{loja_edicao}",
    )

    if st.button("💾 Salvar Orçado da Loja", type="primary",
                 use_container_width=True, key=f"btn_salvar_orcado_{loja_edicao}"):
        with st.spinner("⏳ Gravando no Supabase..."):
            try:
                agora_por = {"atualizado_por": usuario}

                # 1. Upsert das quantidades por função
                registros = []
                base = df_loja.reset_index(drop=True)
                edit = df_editado.reset_index(drop=True)
                for i in range(len(edit)):
                    registros.append({
                        "loja": int(loja_edicao),
                        "departamento": str(base.at[i, "departamento"]),
                        "funcao": str(base.at[i, "funcao"]),
                        "quantidade": int(edit.at[i, "quantidade"]),
                        "conta_no_total": bool(edit.at[i, "conta_no_total"]),
                        "ordem_dept": int(base.at[i, "ordem_dept"]),
                        "ordem_funcao": int(base.at[i, "ordem_funcao"]),
                        **agora_por,
                    })
                supabase.table("ql_orcado").upsert(
                    registros, on_conflict="loja,departamento,funcao").execute()

                # 2. Upsert dos parâmetros da loja
                supabase.table("ql_parametros_loja").upsert({
                    "loja": int(loja_edicao),
                    "venda": float(nova_venda),
                    "media_6_meses": float(nova_media),
                    "venda_por_funcionario": float(nova_venda_func),
                    "proposta_quant": int(nova_proposta),
                    **agora_por,
                }, on_conflict="loja").execute()

                st.success("✅ Valores orçados salvos com sucesso!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar no Supabase: {e}")


# =====================================================================
# 🚪 FUNÇÃO PRINCIPAL (chamada pelo app.py)
# =====================================================================
def renderizar_visao_ql_orcado(supabase, loja_selecionada, pode_editar=False, usuario="", df_quadro=None):
    """
    Renderiza a visão QL Orçado (organograma).

    Parâmetros:
        supabase          -> client Supabase já inicializado no app.py
        loja_selecionada  -> int (loja específica) ou "Total Lojas"/"Total Rede"
        pode_editar       -> True para perfis com edição (analista/rh)
        usuario           -> e-mail do usuário logado (auditoria)
        df_quadro         -> DataFrame do quadro já filtrado pela seleção
                             (df_loja do app.py); usado para calcular o Real
                             automaticamente (Ativos + Férias)
    """
    try:
        df_orc, df_par = carregar_ql_orcado(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar dados do QL Orçado no Supabase: {e}")
        return

    if df_orc.empty:
        st.warning("⚠️ Tabela `ql_orcado` vazia ou inexistente. "
                   "Execute o script `seed_ql_orcado.sql` no Supabase.")
        return

    modo_total = not isinstance(loja_selecionada, int)

    if modo_total:
        lojas = sorted([l for l in df_orc["loja"].unique() if l in LOJAS_PADRAO])
        df_view, params = _agregar(df_orc, df_par, lojas)
        titulo = "QL Orçado — Total Lojas (01 a 08)"
    else:
        loja = int(loja_selecionada)
        df_view = df_orc[df_orc["loja"] == loja].sort_values(
            ["ordem_dept", "ordem_funcao"]).copy()
        par = df_par[df_par["loja"] == loja]
        params = par.iloc[0].to_dict() if not par.empty else {}
        titulo = f"QL Orçado — Loja {loja:02d}"

    if df_view.empty:
        st.info("Nenhum valor orçado cadastrado para esta seleção.")
        return

    # Real calculado ao vivo do quadro (Ativos + Férias). Se o app não
    # passar o df_quadro, mantém o valor gravado no banco como fallback.
    real_calculado = _calcular_real(df_quadro)
    if real_calculado is not None:
        params["real_quadro"] = real_calculado

    st.markdown(_montar_html(df_view, params, titulo), unsafe_allow_html=True)

    # ------- Edição (somente perfis liberados) -------
    if pode_editar:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("✏️ Editar Valores Orçados (Admin/RH)", expanded=False):
            if modo_total:
                lojas_disponiveis = sorted(df_orc["loja"].unique().tolist())
                loja_edicao = st.selectbox(
                    "Selecione a loja para editar:",
                    lojas_disponiveis,
                    format_func=lambda x: f"Loja {int(x):02d}",
                    key="sel_loja_edicao_orcado",
                )
            else:
                loja_edicao = int(loja_selecionada)
            _renderizar_edicao(supabase, df_orc, df_par, int(loja_edicao), usuario)


# =====================================================================
# 📌 INSTRUÇÕES DE INTEGRAÇÃO NO app.py
# =====================================================================
# 1) No topo do app.py, junto aos outros imports:
#
#       from ql_orcado import renderizar_visao_ql_orcado
#
# 2) Na seção "📋 Painel de Controle e Visualização", junto aos outros
#    checkboxes (mostrar_relatorio, apenas_alterados etc.):
#
#       mostrar_ql_orcado = st.checkbox(
#           "📐 Visualizar QL Orçado (Organograma de Funções)", value=False)
#
# 3) Logo após o bloco do Relatório de Efetividade (antes da lógica
#    dos expanders de departamentos):
#
#       if mostrar_ql_orcado:
#           renderizar_visao_ql_orcado(
#               supabase,
#               loja_selecionada,
#               pode_editar=(perfil in PERFIS_EDICAO_TOTAL),
#               usuario=st.session_state["usuario"],
#               df_quadro=df_loja,
#           )
#           st.markdown("---")
#
# Como o gerente já entra com loja_fixa, ele enxergará automaticamente
# apenas o organograma da própria loja, somente leitura. Analista/RH
# navegam por todas as lojas + Total e podem editar.
# =====================================================================
