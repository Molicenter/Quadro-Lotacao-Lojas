import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date
import os
import time
import plotly.graph_objects as go

# =========================================================
# 🌐 RASTREAMENTO DE SESSÕES ATIVAS EM TEMPO REAL
# =========================================================
@st.cache_resource
def obter_rastreador_sessoes():
    return {}

# =========================================================
# 🛠️ 1. CONFIGURAÇÕES INICIAIS E FUNÇÕES AUXILIARES VISUAIS
# =========================================================

st.set_page_config(
    page_title="Molicenter - QL (Quadro de Lotação)", 
    page_icon="passaro_logo.png" if os.path.exists("passaro_logo.png") else "📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# NOVO: Funções para gerar os "Badges" (Pílulas) de Status
def obter_badge_status(status):
    status_upper = str(status).strip().upper()
    if "ATIVO" in status_upper:
        return f'<span class="badge badge-ativo">{status}</span>'
    elif "FÉRIAS" in status_upper or "FERIAS" in status_upper:
        return f'<span class="badge badge-ferias">{status}</span>'
    elif "AFASTAMENTO" in status_upper or "AFASTADO" in status_upper:
        return f'<span class="badge badge-afastado">{status}</span>'
    elif "DEMITIDO" in status_upper:
        return f'<span class="badge badge-demitido">{status}</span>'
    return f'<span class="badge" style="background-color:#475569; color:white;">{status}</span>'

def obter_badge_rh(status):
    status_str = str(status).strip()
    if status_str in ["nan", "None", "", "-"]:
        return status_str
    return f'<span class="badge badge-rh">{status_str}</span>'

def formatar_data_br(valor):
    val_str = str(valor).strip()
    if val_str in ["nan", "None", "", "-", "0"]:
        return "-"
    try:
        if "T" in val_str:
            val_str = val_str.split("T")[0]
        dt = pd.to_datetime(val_str)
        return dt.strftime("%d/%m/%Y")
    except:
        return val_str

URL_API_SHEETS = "https://script.google.com/macros/s/AKfycbz_OA0O8zS-rMuuZEYu5rUeZow3lEZt-GcGYUWUbX4kiaRwDoQ9vZeoknsF5K-zFZvn/exec"

# MATRIZ DE PERFIL E USUÁRIOS
USUARIOS_DB = {
    "analista@molicenter.com.br": {"senha": "moli0123", "perfil": "analista", "loja_fixa": None},
    "dp1@molicenter.com.br": {"senha": "dpmol123", "perfil": "rh", "loja_fixa": None},
    "rh1@molicenter.com.br": {"senha": "0413233031", "perfil": "rh", "loja_fixa": None},
    "rhloja01@molicenter.com.br": {"senha": "rhmoli123", "perfil": "rh", "loja_fixa": 1},
    "rhloja08@molicenter.com.br": {"senha": "rhmoli123", "perfil": "rh", "loja_fixa": 8},
    "supervisorlojas@molicenter.com.br": {"senha": "moli1234", "perfil": "supervisor", "loja_fixa": None},
    "gerente1@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 1},
    "gerente2@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 2},
    "gerente3@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 3},
    "gerente4@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 4},
    "gerente5@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 5},
    "gerente6@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 6},
    "gerente7@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 7},
    "gerente8@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 8},
    "gerente30@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 30},
}

OPCOES_SEXO = ["-", "Indiferente", "Masculino", "Feminino"]
MAPA_SEXO_SIGLA = {"-": "-", "Indiferente": "I", "Masculino": "M", "Feminino": "F"}
MAPA_SIGLA_SEXO = {"-": "-", "I": "Indiferente", "M": "Masculino", "F": "Feminino"}
OPCOES_MOTIVO = ["-", "Afastamento","Aumento QL", "Encerramento Contrato Exp.","Função Nova", "Mudança Setor", "Substituição", "Transferência"]
OPCOES_STATUS_RH = ["-", "Requisição atendida", "Aguardando resposta Candidato", "Cancelado", "Divulgação da vaga", "Documentação Admissão", "Entrevista Loja", "Entrevista RH", "Exame Admissional", "Não Validado pelo gerente", "Previsão de Início", "Triagem de Curriculuns", "Validado pelo gerente", "Desistencia Candidato"]

OPCOES_HORARIO = [
    "-", "ART 62 CLT", "SG-SB 05:00-10:00 11:15-13:35", "SG-SB 05:50-11:30 13:20-15:00", 
    "SG-SB 06:00-10:00 11:10-14:30", "SG-SB 06:00-10:00 12:00-15:20", "SG-SB 06:00-11:00 12:15-14:35", 
    "SG-SB 06:30-10:30 11:40-15:00", "SG-SB 06:30-11:00 13:00-15:50", "SG-SB 06:30-12:00 13:10-15:00", 
    "SG-SB 07:00-11:00 13:00-16:20", "SG-SB 07:00-11:30 13:00-15:50", "SG-SB 07:00-11:30 13:30-16:20", 
    "SG-SB 07:00-12:00 13:20-15:40", "SG-SB 07:00-12:00 14:00-16:20", "SG-SB 07:30-11:00 13:00-16:50", 
    "SG-SB 07:30-11:30 13:30-16:50", "SG-SB 07:30-12:00 13:30-16:20", "SG-SB 07:30-12:00 14:00-16:50", 
    "SG-SB 07:30-12:30 14:00-16:20", "SG-SB 07:30-13:00 15:00-16:50", "SG-SB 07:30-12:00 14:00-17:30","SG-SB 07:50-11:30 13:30-17:10", 
    "SG-SB 07:50-12:00 14:00-17:10", "SG-SB 08:00-11:30 13:30-17:20", "SG-SB 08:00-12:00 14:00-17:20", 
    "SG-SB 08:30-11:00 13:00-17:50", "SG-SB 08:30-12:00 14:00-17:50", "SG-SB 09:00-13:00 15:00-18:20", 
    "SG-SB 09:00-14:00 16:00-18:20", "SG-SB 09:30-13:00 15:00-18:50", "SG-SB 09:50-13:00 14:50-19:00", 
    "SG-SB 10:00-12:30 14:30-19:20", "SG-SB 10:00-13:00 15:00-19:20", "SG-SB 10:00-14:00 16:00-19:20", 
    "SG-SB 11:00-14:00 16:00-20:20", "SG-SB 11:00-14:30 16:00-19:50", "SG-SB 11:00-15:00 17:00-20:20", 
    "SG-SB 11:20-14:00 16:00-20:40", "SG-SB 11:30-13:30 15:30-20:50", "SG-SB 11:30-14:00 16:00-20:50", 
    "SG-SB 11:30-14:30 16:30-20:50", "SG-SB 11:30-15:30 17:30-20:50", "SG-SB 12:00-15:00 17:00-21:20", 
    "SG-SB 13:00-16:00 17:10-21:30", "SG-SB 13:00-17:00 18:10-21:30", "SG-SB 13:10-15:00 16:50-22:20", 
    "SG-SX 07:00-12:00 13:12-17:00", "SG-SX 07:30-12:00 13:12-17:30", "SG-SX 07:30-12:00 13:42-18:00", 
    "SG-SX 07:30-12:00 14:00-18:18", "SG-SX 08:00-12:00 13:12-18:00", "SG-SX 08:00-13:00 14:12-18:00", 
    "SG-SX 08:00-17:30 Sab 08:00-12", "SG-SX 5:00-15:00 SB 5:00-09:00", "SG-SX 7:00-17:00 SB 7:00-11:00", 
    "SG-SX 7:30-16:40 SB 7:30-11:30", "SG-SX 7:30-17:00 SB 08:00-12:0", "SG-SX 7:30-17:00 SB 7:30-11:30", 
    "SG-SX 7:30-17:30 SB 7:30-11:30", "SG-SX 8:00-18:00 SB 8:00-12:00", "SG-SX 8:30-18:00 SB 9:00-13:00"
]

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["perfil"] = ""
    st.session_state["loja_fixa"] = None

if "expander_global" not in st.session_state:
    st.session_state["expander_global"] = False

if "chk_alterados" not in st.session_state:
    st.session_state["chk_alterados"] = False

# =========================================================
# 🔐 2. INTERFACE DA TELA DE LOGIN
# =========================================================
if not st.session_state["logado"]:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    _, col_centro, _ = st.columns([1, 1.2, 1])
    
    with col_centro:
        with st.container(border=True):
            if os.path.exists("passaro_logo.png"):
                col_texto, col_logo = st.columns([0.8, 0.2], vertical_alignment="center")
                with col_texto:
                    st.markdown("<h2 style='margin: 0; padding: 0; line-height: 1;'>Molicenter QL</h2>", unsafe_allow_html=True)
                    st.markdown("<p style='color: #a0a0a0; font-size: 15px; margin: 0; padding-top: 4px;'>QL - Quadro de Lotação</p>", unsafe_allow_html=True)
                with col_logo:
                    st.image("passaro_logo.png", width=90)
            else:
                st.markdown("<h2 style='margin: 0; padding: 0; line-height: 1;'>Molicenter QL</h2>", unsafe_allow_html=True)
                st.markdown("<p style='color: #a0a0a0; font-size: 15px; margin: 0; padding-top: 4px;'>QL - Quadro de Lotação</p>", unsafe_allow_html=True)
            
            st.divider() 
            
            lista_usuarios = ["Selecione o usuário..."] + list(USUARIOS_DB.keys())
            user_input = st.selectbox("E-mail corporativo:", lista_usuarios)
            pass_input = st.text_input("Senha de acesso:", type="password", placeholder="••••••••")

            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Entrar no Sistema", use_container_width=True, type="primary"):
                if user_input == "Selecione o usuário...":
                    st.warning("Por favor, selecione um usuário válido na lista.")
                else:
                    user_clean = user_input.strip().lower()
                    if user_clean in USUARIOS_DB and USUARIOS_DB[user_clean]["senha"] == pass_input:
                        st.session_state["logado"] = True
                        st.session_state["usuario"] = user_clean
                        st.session_state["perfil"] = USUARIOS_DB[user_clean]["perfil"]
                        st.session_state["loja_fixa"] = USUARIOS_DB[user_clean]["loja_fixa"]
                        st.success("Acesso concedido!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos. Tente novamente.")
    st.stop()

# =========================================================
# 📊 3. CSS DO DASHBOARD INTERNO E CARDS
# =========================================================
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
    [data-testid="stApp"] { zoom: 1.0 !important; }
    [data-testid="stAppViewBlockContainer"] { padding-left: 1.2rem !important; padding-right: 1.2rem !important; padding-top: 0.5rem !important; max-width: 100% !important; }
    [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    
    /* ESTILOS DOS CARDS DE MÉTRICAS */
    .metric-container { display: flex; gap: 15px; margin-bottom: 25px; flex-wrap: wrap; }
    .metric-card {
        background-color: #1e293b; border-radius: 8px; padding: 15px 10px; flex: 1; min-width: 120px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        border: 1px solid #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-3px); border-color: #475569; }
    .metric-icon { font-size: 22px; margin-bottom: 8px; }
    .metric-value { font-size: 28px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
    .metric-label { font-size: 13px; color: #cbd5e1; font-weight: 500; }
    
    /* Cores das Métricas */
    .c-ativo { color: #10b981; }      /* Verde */
    .c-ferias { color: #3b82f6; }     /* Azul */
    .c-demitido { color: #ef4444; }   /* Vermelho */
    .c-afastado { color: #f59e0b; }   /* Laranja */
    .c-alterado { color: #8b5cf6; }   /* Roxo */

    /* ESTILOS DOS BADGES (PÍLULAS) NA TABELA PRINCIPAL */
    .badge {
        display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 11.5px;
        font-weight: 600; text-align: center; white-space: nowrap;
    }
    .badge-ativo { background-color: #f8fafc; color: #047857; border: 1px solid #10b981; }
    .badge-ferias { background-color: #fef3c7; color: #92400e; border: 1px solid #f59e0b; }
    .badge-afastado { background-color: #fff1f2; color: #be123c; border: 1px solid #fda4af; }
    .badge-demitido { background-color: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    .badge-rh { background-color: #f0f9ff; color: #0369a1; border: 1px solid #7dd3fc; }

    /* ESTILOS DE TABELA PRINCIPAL */
    .tabela-container { width: 100%; overflow-x: auto; margin-bottom: 15px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .ql-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 12px; color: #ffffff; border: none !important; }
    .ql-table th { padding: 8px 10px; font-size: 12px !important; font-weight: 600; }
    .ql-table td { border-bottom: 1px solid #334155; border-left: none; border-right: none; padding: 10px 8px; text-align: left; white-space: nowrap; vertical-align: middle; }
    .ql-table tr:nth-child(even) { background-color: #1e1e1e; }
    .ql-table tr:nth-child(odd) { background-color: #121212; }
    .ql-table tbody tr:hover { background-color: #334155 !important; transition: 0.2s; }
    .celula-loja { text-align: center !important; font-weight: bold !important; color: #38bdf8 !important; }
    
    /* === NOVO: ESTILOS EXCLUSIVOS DA TABELA DE RESUMO (RELATÓRIO) === */
    .tabela-resumo { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; color: #ffffff; }
    .tabela-resumo th { padding: 10px; background-color: #1e293b; border-bottom: 2px solid #475569; text-align: center !important; font-weight: 600; }
    .tabela-resumo td { padding: 10px; border-bottom: 1px solid #334155; text-align: center !important; vertical-align: middle; }
    .tabela-resumo tr:nth-child(even) { background-color: #1e1e1e; }
    .tabela-resumo tr:nth-child(odd) { background-color: #121212; }
    .tabela-resumo tbody tr:hover { background-color: #334155 !important; transition: 0.2s; }
    /* ================================================================ */
    
    div[data-testid="stExpander"] { margin-bottom: 6px !important; border: 1px solid #334155 !important; border-radius: 6px !important; background-color: transparent !important; }
    div[data-testid="stExpander"] summary { background-color: #1e293b !important; border-radius: 5px 5px 5px 5px !important; padding: 10px 15px !important; }
    div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary span, div[data-testid="stExpander"] summary label { color: #ffffff !important; font-weight: 600 !important; font-size: 13px !important; }
    div[data-testid="stExpander"] summary svg { color: #ffffff !important; fill: #ffffff !important; }
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] { background-color: transparent !important; padding-top: 5px !important; }
    </style>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state["logado"] = False
    st.rerun()

# =========================================================
# 📊 4. CARGA DE DADOS HÍBRIDA
# =========================================================
@st.cache_data(ttl="0d")
def carregar_dados_completos():
    df = pd.read_excel("Banco QL.xlsx", sheet_name="Banco")
    df['Loja'] = df['Loja'].fillna(0).astype(int)
    
    nome_coluna_horario = 'Descrição (Escala)'
    if nome_coluna_horario in df.columns:
        df['Horario_Sistema_Real'] = df[nome_coluna_horario].astype(str).str.replace('.0', '', regex=False).str.strip()
        df['Horario_Sistema_Real'] = df['Horario_Sistema_Real'].apply(lambda x: '-' if x in ['nan', 'None', ''] else x)
    else:
        df['Horario_Sistema_Real'] = "-"

    colunas_digitacao = ['Observação', 'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo', 'Status RH', 'Candidato', 'Data Admissão']
    for col in colunas_digitacao:
        df[col] = "-"
        
    df['Possui_Alteracao_Sheets'] = False

    try:
        response = requests.get(URL_API_SHEETS, timeout=10)
        if response.status_code == 200:
            dados_sheets = response.json()
            mapeados = set()

            for registro in dados_sheets:
                nome_func = registro.get('Nome')
                try:
                    loja_reg = int(float(str(registro.get('Loja', 0))))
                except:
                    loja_reg = 0
                
                idx_list = df[(df['Nome'] == nome_func) & (df['Loja'] == loja_reg)].index
                if len(idx_list) > 0:
                    idx = idx_list[0]
                    sigla_sexo = str(registro.get('Sexo', '-')).strip()
                    sexo_exibicao = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                    if 'Situação' in registro and str(registro.get('Situação')).strip() not in ["", "-"]:
                        df.at[idx, 'Situação'] = registro.get('Situação')
                    df.at[idx, 'Observação'] = registro.get('Observação', '-')
                    df.at[idx, 'Data Abertura'] = formatar_data_br(registro.get('Data Abertura', '-'))
                    df.at[idx, 'Responsável'] = registro.get('Responsável', '-')
                    df.at[idx, 'Horário Contrato'] = str(registro.get('Horário Contrato', '-'))
                    df.at[idx, 'Sexo'] = sexo_exibicao
                    df.at[idx, 'Motivo'] = registro.get('Motivo', '-')
                    df.at[idx, 'Status RH'] = registro.get('Status RH', '-')
                    df.at[idx, 'Candidato'] = registro.get('Candidato', '-')
                    df.at[idx, 'Data Admissão'] = formatar_data_br(registro.get('Data Admissão', '-'))
                    df.at[idx, 'Possui_Alteracao_Sheets'] = True
                    mapeados.add((nome_func, loja_reg))

            linhas_novas_manuais = []
            for registro in dados_sheets:
                nome_func = registro.get('Nome')
                try:
                    loja_reg = int(float(str(registro.get('Loja', 0))))
                except:
                    loja_reg = 0
                
                if (nome_func, loja_reg) not in mapeados:
                    data_ad_checar = formatar_data_br(registro.get('Data Admissão', '-'))
                    
                    sigla_sexo = str(registro.get('Sexo', '-')).strip()
                    sexo_exibicao = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                    
                    dept_final = registro.get('Dept') if registro.get('Dept') else 'HISTÓRICO / EX-COLABORADORES'
                    funcao_final = registro.get('Funco') if registro.get('Funco') else (registro.get('Função') if registro.get('Função') else 'Sem Vínculo Atual')
                    situacao_final = registro.get('Situaçao') if registro.get('Situaçao') else (registro.get('Situação') if registro.get('Situação') else 'Demitido')
                    
                    linha_manual = {
                        'Loja': loja_reg, 'Nome': nome_func, 'Situação': situacao_final, 
                        'Dept': dept_final, 'Função': funcao_final, 'Horario_Sistema_Real': '-',
                        'Observação': registro.get('Observação', '-'),
                        'Data Abertura': formatar_data_br(registro.get('Data Abertura', '-')),
                        'Responsável': registro.get('Responsável', '-'),
                        'Horário Contrato': str(registro.get('Horário Contrato', '-')),
                        'Sexo': sexo_exibicao, 'Motivo': registro.get('Motivo', '-'),
                        'Status RH': registro.get('Status RH', '-'),
                        'Candidato': registro.get('Candidato', '-'),
                        'Data Admissão': data_ad_checar, 'Possui_Alteracao_Sheets': True
                    }
                    linhas_novas_manuais.append(linha_manual)
            
            if len(linhas_novas_manuais) > 0:
                df_manuais = pd.DataFrame(linhas_novas_manuais)
                df = pd.concat([df, df_manuais], ignore_index=True)
    except:
        pass

    return df

try:
    df_bruto = carregar_dados_completos()

    sessoes_globais = obter_rastreador_sessoes()
    if st.session_state["logado"]:
        sessoes_globais[st.session_state["usuario"]] = datetime.now()

    perfil = st.session_state["perfil"]
    loja_fixa = st.session_state["loja_fixa"]

    col_main_logo, col_main_title = st.columns([0.15, 2.85], vertical_alignment="center")
    with col_main_logo:
        if os.path.exists("passaro_logo.png"):
            st.image("passaro_logo.png", width=65) 
    with col_main_title:
        st.markdown("<h2 style='margin: 0; padding: 0;'>Molicenter - QL (Quadro de Lotação)</h2>", unsafe_allow_html=True)
        
    st.sidebar.markdown(f"**Usuário:** `{st.session_state['usuario']}`")
    st.sidebar.markdown(f"**Nível:** `{perfil.upper()}`")
    st.markdown("<hr style='margin-top: 2px; margin-bottom: 8px;'>", unsafe_allow_html=True)

    if perfil == "analista":
        agora_painel = datetime.now()
        usuarios_online = [user for user, ultima_atividade in sessoes_globais.items() if (agora_painel - ultima_atividade).total_seconds() < 600]
        st.markdown(
            f"""
            <div style="background-color: #1e293b; padding: 12px; border-radius: 6px; border: 1px solid #334155; margin-bottom: 15px;">
                <span style="color: #38bdf8; font-weight: bold;">🟢 Usuários online no Sistema (Últimos 10 min):</span>
                <span style="color: #ffffff; margin-left: 8px;">{', '.join([f'<b>{u}</b>' for u in usuarios_online])}</span>
            </div>
            """, unsafe_allow_html=True)

    if loja_fixa is not None:
        loja_selecionada = loja_fixa
        st.info(f"🏪 Modo de Visualização Restrito: **Loja {loja_selecionada:02d}**")
        df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()
        modo_visao_global = False
    else:
        lojas_reais = sorted([int(l) for l in df_bruto['Loja'].unique() if int(l) > 0])
        opcoes_selecao = ["Total Lojas", "Total Rede"] + lojas_reais
        
        st.markdown("<div style='max-width: 300px;'>", unsafe_allow_html=True)
        loja_selecionada = st.selectbox("Selecione a Loja para Análise:", opcoes_selecao, format_func=lambda x: f"Loja {int(x):02d}" if isinstance(x, int) else str(x))
        st.markdown("</div>", unsafe_allow_html=True)

        if loja_selecionada == "Total Lojas":
            df_loja = df_bruto[df_bruto['Loja'].isin([1, 2, 3, 4, 5, 6, 7, 8])].copy()
            st.info("📊 Exibindo dados agregados das **Lojas 01 a 08**.")
            modo_visao_global = True
        elif loja_selecionada == "Total Rede":
            df_loja = df_bruto[df_bruto['Loja'] > 0].copy()
            st.info("🌐 Exibindo dados agregados de **Toda a Rede Molicenter**.")
            modo_visao_global = True
        else:
            df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()
            modo_visao_global = False

    # =========================================================
    # 🛠️ BARRA LATERAL (SIDEBAR) - FORMULÁRIO OPERACIONAL
    # =========================================================
    st.sidebar.header("📝 Alimentar Informações")
    
    if st.session_state["perfil"] == "gerente":
        st.sidebar.markdown("**Modo de Operação:** Editar Colaborador Existente")
        tipo_registro = "Editar Colaborador Existente"
    else:
        tipo_registro = st.sidebar.radio("Modo de Operação:", ["Editar Colaborador Existente", "Cadastrar Novo / Não Listado"])
    
    dados_func = None
    colaborador_final = ""
    dept_final = ""
    funcao_final = ""
    situacao_final = ""
    
    if tipo_registro == "Editar Colaborador Existente":
        funcionarios_loja = sorted(df_loja['Nome'].dropna().unique())
        colaborador_selecionado = st.sidebar.selectbox("Selecione o Colaborador:", funcionarios_loja)
        if colaborador_selecionado:
            dados_func = df_loja[df_loja['Nome'] == colaborador_selecionado].iloc[0]
            colaborador_final = colaborador_selecionado
            dept_final = str(dados_func['Dept'])
            funcao_final = str(dados_func['Função'])
            situacao_final = str(dados_func['Situação'])
    else:
        st.sidebar.markdown("---")
        colaborador_final = st.sidebar.text_input("Nome Completo do Colaborador:").strip().upper()
        
        depts_existentes = sorted(list(df_bruto['Dept'].dropna().unique()))
        if 'HISTÓRICO / EX-COLABORADORES' in depts_existentes:
            depts_existentes.remove('HISTÓRICO / EX-COLABORADORES')
        dept_final = st.sidebar.selectbox("Departamento:", depts_existentes)
        
        funcoes_existentes = sorted(list(df_bruto[df_bruto['Dept'] == dept_final]['Função'].dropna().unique()))
        if not funcoes_existentes:
            funcoes_existentes = sorted(list(df_bruto['Função'].dropna().unique()))
        funcao_final = st.sidebar.selectbox("Cargo/Função:", funcoes_existentes)
        
        situacao_final = st.sidebar.selectbox("Situação Inicial:", ["Ativos", "Demitido", "Afastamento", "Férias"])

    if colaborador_final:
        with st.sidebar.form("form_edicao_ql", border=True):
            st.markdown("### Atualizar Dados")
            st.markdown("🔸 **Supervisor**")
            val_obs_default = str(dados_func['Observação']) if (dados_func is not None and str(dados_func['Observação']) != "-") else ""
            if perfil in ["analista", "rh", "supervisor"]:
                nova_obs = st.text_area("Observação:", value=val_obs_default)
            else:
                st.text_input("Observação:", value=val_obs_default if val_obs_default else "-", disabled=True)
                nova_obs = val_obs_default if val_obs_default else "-"
            
            st.markdown("🔹 **Gerente**")
            if perfil in ["analista", "rh", "supervisor", "gerente"]:
                data_ab_atual = str(dados_func['Data Abertura']).strip() if dados_func is not None else "-"
                try:
                    data_ab_default = datetime.strptime(data_ab_atual, "%d/%m/%Y").date() if data_ab_atual != "-" else date.today()
                except:
                    data_ab_default = date.today()
                nova_data_ab_col = st.date_input("Data Abertura:", value=data_ab_default, format="DD/MM/YYYY")
                nova_data_abertura = nova_data_ab_col.strftime("%d/%m/%Y")
                
                val_resp_default = str(dados_func['Responsável']) if (dados_func is not None and str(dados_func['Responsável']) != "-") else ""
                novo_responsavel = st.text_input("Responsável:", value=val_resp_default)
                
                val_horario_default = str(dados_func['Horário Contrato']).strip() if dados_func is not None else "-"
                idx_horario = OPCOES_HORARIO.index(val_horario_default) if val_horario_default in OPCOES_HORARIO else 0
                novo_horario_contrato = st.selectbox("Horário Contrato:", OPCOES_HORARIO, index=idx_horario)
                
                sexo_exibido_atual = str(dados_func['Sexo']).strip() if dados_func is not None else "-"
                idx_sexo = OPCOES_SEXO.index(sexo_exibido_atual) if sexo_exibido_atual in OPCOES_SEXO else 0
                texto_sexo_selecionado = st.selectbox("Sexo:", OPCOES_SEXO, index=idx_sexo)
                novo_sexo = MAPA_SEXO_SIGLA.get(texto_sexo_selecionado, "-")
                
                motivo_atual = str(dados_func['Motivo']).strip() if dados_func is not None else "-"
                idx_motivo = OPCOES_MOTIVO.index(motivo_atual) if motivo_atual in OPCOES_MOTIVO else 0
                novo_motivo = st.selectbox("Motivo:", OPCOES_MOTIVO, index=idx_motivo)
            else:
                nova_data_abertura = st.text_input("Data Abertura:", value=str(dados_func['Data Abertura']) if dados_func is not None else "-", disabled=True)
                novo_responsavel = st.text_input("Responsável:", value=str(dados_func['Responsável']) if dados_func is not None else "-", disabled=True)
                novo_horario_contrato = st.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']) if dados_func is not None else "-", disabled=True)
                novo_sexo_exibido = st.text_input("Sexo:", value=str(dados_func['Sexo']) if dados_func is not None else "-", disabled=True)
                novo_sexo = MAPA_SEXO_SIGLA.get(novo_sexo_exibido, "-")
                novo_motivo = st.text_input("Motivo:", value=str(dados_func['Motivo']) if dados_func is not None else "-", disabled=True)
            
            st.markdown("🔺 **Recursos Humanos (RH)**")
            if perfil in ["analista", "rh"]:
                status_atual = str(dados_func['Status RH']).strip() if dados_func is not None else "-"
                idx_status = OPCOES_STATUS_RH.index(status_atual) if status_atual in OPCOES_STATUS_RH else 0
                novo_status_rh = st.selectbox("Status RH:", OPCOES_STATUS_RH, index=idx_status)
                
                val_cand_default = str(dados_func['Candidato']) if (dados_func is not None and str(dados_func['Candidato']) != "-") else ""
                novo_candidato = st.text_input("Candidato:", value=val_cand_default)
                
                data_ad_atual = str(dados_func['Data Admissão']).strip() if dados_func is not None else "-"
                tem_data_anterior = data_ad_atual != "-"
                
                definir_data = st.checkbox("Definir data de admissão", value=tem_data_anterior)
                
                if definir_data:
                    try:
                        data_ad_default = datetime.strptime(data_ad_atual, "%d/%m/%Y").date() if tem_data_anterior else date.today()
                    except:
                        data_ad_default = date.today()
                    nova_data_ad_col = st.date_input("Data Admissão:", value=data_ad_default, format="DD/MM/YYYY")
                    nova_data_admissao = nova_data_ad_col.strftime("%d/%m/%Y")
                else:
                    nova_data_admissao = "-"
            else:
                novo_status_rh = st.text_input("Status RH:", value=str(dados_func['Status RH']) if dados_func is not None else "-", disabled=True)
                novo_candidato = st.text_input("Candidato:", value=str(dados_func['Candidato']) if dados_func is not None else "-", disabled=True)
                nova_data_admissao = st.text_input("Data Admissão:", value=str(dados_func['Data Admissão']) if dados_func is not None else "-", disabled=True)
            
            submit_button = st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary")

        # ==============================================================
        # 🔒 VALIDAÇÃO DE CAMPOS (TRAVA DE SALVAMENTO PARA TODOS)
        # ==============================================================
        if submit_button:
            val_data = str(nova_data_abertura).strip()
            val_resp = str(novo_responsavel).strip()
            val_horario = str(novo_horario_contrato).strip()
            val_sexo = str(novo_sexo).strip()
            val_motivo = str(novo_motivo).strip()

            campos_validacao_gerente = {
                "Data Abertura": val_data,
                "Responsável": val_resp,
                "Horário Contrato": val_horario,
                "Sexo": val_sexo,
                "Motivo": val_motivo
            }
            
            campos_faltantes = [nome for nome, valor in campos_validacao_gerente.items() if valor in ["-", "", "None", "nan"]]

            if tipo_registro == "Cadastrar Novo / Não Listado" and not colaborador_final:
                st.sidebar.error("Erro: O nome do colaborador não pode ficar em branco.")
            elif len(campos_faltantes) > 0:
                st.sidebar.error(f"⚠️ Atenção! Preencha os campos obrigatórios do Gerente: **{', '.join(campos_faltantes)}**")
            else:
                with st.spinner("⏳ Processando e enviando para o Google Sheets (isso leva alguns segundos)..."):
                    loja_salvamento = int(dados_func['Loja']) if (dados_func is not None) else (int(loja_selecionada) if isinstance(loja_selecionada, int) else 1)
                    
                    payload = {
                        "Loja": loja_salvamento, "Nome": colaborador_final, "Dept": dept_final, "Funcao": funcao_final,
                        "Situaçao": situacao_final, "Observacao": nova_obs, "DataAbertura": nova_data_abertura,
                        "Responsavel": novo_responsavel, "HorarioContrato": str(novo_horario_contrato),
                        "Sexo": novo_sexo, "Motivo": novo_motivo, "StatusRH": novo_status_rh,
                        "Candidato": novo_candidato, "DataAdmissao": nova_data_admissao,
                        "Usuario": st.session_state["usuario"]
                    }
                    try:
                        headers = {'Content-Type': 'application/json'}
                        res = requests.post(URL_API_SHEETS, data=json.dumps(payload), headers=headers, timeout=10)
                        if res.status_code == 200:
                            st.sidebar.success("✅ Dados salvos com sucesso!")
                            st.cache_data.clear()
                            
                            time.sleep(3.5)
                            
                            st.rerun()
                        else:
                            st.sidebar.error("Erro ao comunicar com a API do Sheets.")
                    except Exception as e:
                        st.sidebar.error(f"Erro de conexão: {e}")

    # =========================================================
    # 🏪 5. INDICADORES E MATRIZ VISUAL CENTRAL
    # =========================================================
    texto_titulo = f"Loja {int(loja_selecionada):02d}" if isinstance(loja_selecionada, int) else str(loja_selecionada)
    st.markdown(f"### 🏪 Quadro de Funcionários - {texto_titulo}")

    df_loja['Situação_Upper'] = df_loja['Situação'].astype(str).str.upper()
    
    ativos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('ATIVO')])
    ferias_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('FÉRIAS|FERIAS')])
    demitidos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('DEMITIDO')])
    afastados_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('AFASTAMENTO|AFASTADO')])
    alterados_qtd = len(df_loja[df_loja['Possui_Alteracao_Sheets'] == True])

    html_cards = f"""
    <div class="metric-container">
        <div class="metric-card">
            <i class="fa-solid fa-users metric-icon c-ativo"></i>
            <div class="metric-value c-ativo">{ativos_qtd}</div>
            <div class="metric-label">Ativos</div>
        </div>
        <div class="metric-card">
            <i class="fa-solid fa-umbrella-beach metric-icon c-ferias"></i>
            <div class="metric-value c-ferias">{ferias_qtd}</div>
            <div class="metric-label">Férias</div>
        </div>
        <div class="metric-card">
            <i class="fa-solid fa-user-minus metric-icon c-demitido"></i>
            <div class="metric-value c-demitido">{demitidos_qtd}</div>
            <div class="metric-label">Demitidos</div>
        </div>
        <div class="metric-card">
            <i class="fa-solid fa-clock-rotate-left metric-icon c-afastado"></i>
            <div class="metric-value c-afastado">{afastados_qtd}</div>
            <div class="metric-label">Afastamentos</div>
        </div>
        <div class="metric-card">
            <i class="fa-solid fa-pen-to-square metric-icon c-alterado"></i>
            <div class="metric-value c-alterado">{alterados_qtd}</div>
            <div class="metric-label">Alterados</div>
        </div>
    </div>
    """
    st.markdown(html_cards, unsafe_allow_html=True)

    st.markdown("---")
    
    # === PAINEL DE CONTROLE E VISUALIZAÇÃO ===
    st.subheader("📋 Painel de Controle e Visualização")
    
    focar_colaborador = st.checkbox(f"🔍 Focar visualização apenas no colaborador: {colaborador_final}" if colaborador_final else "🔍 Focar colaborador selecionado", value=False)
    
    mostrar_relatorio = False
    if perfil in ["analista", "rh"]:
        mostrar_relatorio = st.checkbox("📊 Visualizar Relatório de Efetividade (Vagas Abertas vs Concluídas)", value=False)
    
    def sync_expandir():
        if st.session_state["chk_alterados"]:
            st.session_state["expander_global"] = True
        else:
            st.session_state["expander_global"] = False
            
    apenas_alterados = st.checkbox(
        "📝 Visualizar apenas registros alterados/inseridos (Geral)", 
        key="chk_alterados",
        on_change=sync_expandir
    )
    
    expandir_todos = st.checkbox(
        "📂 Expandir Todos os Departamentos", 
        key="expander_global"
    )

    if st.button("🔄 Atualizar Registros", type="primary"):
        st.cache_data.clear() 
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================
    # 📈 LÓGICA DO RELATÓRIO DE EFETIVIDADE (RENDERIZAÇÃO)
    # =========================================================
    if mostrar_relatorio:
        st.markdown("### 📅 Análise de Preenchimento por Período de Abertura")
        
        col_d1, col_d2, _ = st.columns([1, 1, 3])
        with col_d1:
            hoje = date.today()
            inicio_mes = date(hoje.year, hoje.month, 1)
            data_inicio_filtro = st.date_input("Data Início (Abertura):", value=inicio_mes, format="DD/MM/YYYY")
        with col_d2:
            data_fim_filtro = st.date_input("Data Fim (Abertura):", value=hoje, format="DD/MM/YYYY")

        if data_fim_filtro:
            df_analise = df_loja.copy()
            df_analise['DataAbertura_DT'] = pd.to_datetime(df_analise['Data Abertura'], format='%d/%m/%Y', errors='coerce')

            mascara_periodo = (df_analise['Possui_Alteracao_Sheets'] == True) & (
                (df_analise['DataAbertura_DT'].dt.date <= data_fim_filtro) | (df_analise['DataAbertura_DT'].isna())
            )
            df_abertas_periodo = df_analise[mascara_periodo].copy()

            if df_abertas_periodo.empty:
                st.info("Nenhuma vaga com alteração ou abertura encontrada até a data limite para esta(s) loja(s).")
            else:
                abertas_por_loja = df_abertas_periodo.groupby('Loja').size().reset_index(name='Abertas')
                
                def check_concluida(x):
                    val = str(x).strip().lower()
                    if val in ['-', '', 'nan', 'none', 'nat', '0', 'null']:
                        return 0
                    if len(val) >= 5:
                        return 1
                    return 0
                    
                df_abertas_periodo['Concluida'] = df_abertas_periodo['Data Admissão'].apply(check_concluida)
                concluidas_por_loja = df_abertas_periodo.groupby('Loja')['Concluida'].sum().reset_index(name='Concluídas')

                df_relatorio = pd.merge(abertas_por_loja, concluidas_por_loja, on='Loja', how='outer').fillna(0)
                df_relatorio['%'] = (df_relatorio['Concluídas'] / df_relatorio['Abertas'] * 100).fillna(0).round(0).astype(int)

                total_abertas = df_relatorio['Abertas'].sum()
                total_concluidas = df_relatorio['Concluídas'].sum()
                perc_total = int(round((total_concluidas / total_abertas * 100) if total_abertas > 0 else 0, 0))

                df_exibicao_rel = df_relatorio.copy()
                df_exibicao_rel['Loja'] = df_exibicao_rel['Loja'].apply(lambda x: f"Loja {int(x):02d}")
                
                lojas_x = df_exibicao_rel['Loja'].tolist() + ["Total"]
                abertas_y = df_exibicao_rel['Abertas'].tolist() + [total_abertas]
                concluidas_y = df_exibicao_rel['Concluídas'].tolist() + [total_concluidas]
                perc_y = df_exibicao_rel['%'].tolist() + [perc_total]

                fig = go.Figure()

                fig.add_trace(go.Bar(
                    x=lojas_x, y=abertas_y,
                    name='Abertas',
                    marker_color='#64748b',
                    marker_line_width=0, 
                    text=abertas_y,
                    textposition='outside', 
                    textfont=dict(color='#e2e8f0', size=13)
                ))

                fig.add_trace(go.Bar(
                    x=lojas_x, y=concluidas_y,
                    name='Concluídas',
                    marker_color='#0ea5e9',
                    marker_line_width=0,
                    text=concluidas_y,
                    textposition='outside',
                    textfont=dict(color='#e2e8f0', size=13)
                ))

                teto_grafico = max(abertas_y) if abertas_y else 1
                for i, loja in enumerate(lojas_x):
                    fig.add_annotation(
                        x=loja,
                        y=max(abertas_y[i], concluidas_y[i]) + (teto_grafico * 0.15), 
                        text=f"<b>{perc_y[i]}%</b>",
                        showarrow=False,
                        font=dict(color="#fbbf24" if perc_y[i] > 0 else "#475569", size=15) 
                    )

                fig.update_layout(
                    barmode='group',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e2e8f0', family="sans-serif"),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                        font=dict(size=14)
                    ),
                    margin=dict(t=50, b=0, l=0, r=0),
                    yaxis=dict(
                        showgrid=True, 
                        gridcolor='rgba(255,255,255,0.05)', 
                        showticklabels=False, 
                        zeroline=True,
                        zerolinecolor='rgba(255,255,255,0.1)',
                        range=[0, teto_grafico * 1.35] 
                    ),
                    xaxis=dict(
                        showgrid=False,
                        tickfont=dict(size=13, color='#cbd5e1')
                    ),
                    hovermode="x unified" 
                )

                html_resumo = "<div class='tabela-container'>\n<table class='tabela-resumo'>\n<thead>\n<tr>\n"
                html_resumo += "<th>Loja</th>\n<th>Abertas</th>\n<th>Concluídas</th>\n<th>%</th>\n"
                html_resumo += "</tr>\n</thead>\n<tbody>\n"
                
                for i in range(len(lojas_x)):
                    loja_atual = lojas_x[i]
                    abertas_atual = abertas_y[i]
                    concluida_atual = concluidas_y[i]
                    perc_atual = perc_y[i]
                        
                    if perc_atual >= 50:
                        estilo_perc = "color: #10b981; font-weight: bold; background-color: rgba(16, 185, 129, 0.1);"
                    else:
                        estilo_perc = "color: #ef4444; font-weight: bold; background-color: rgba(239, 68, 68, 0.1);"
                        
                    if loja_atual == "Total":
                        estilo_linha = "background-color: #334155; font-weight: bold;"
                    else:
                        estilo_linha = ""
                        
                    html_resumo += f"<tr style='{estilo_linha}'>\n"
                    html_resumo += f"<td>{loja_atual}</td>\n"
                    html_resumo += f"<td>{abertas_atual}</td>\n"
                    html_resumo += f"<td>{concluida_atual}</td>\n"
                    html_resumo += f"<td style='{estilo_perc}'>{perc_atual}%</td>\n"
                    html_resumo += "</tr>\n"
                
                html_resumo += "</tbody>\n</table>\n</div>"

                st.markdown("<br>", unsafe_allow_html=True)
                col_tab, col_graf = st.columns([1, 2.5])
                with col_tab:
                    st.markdown(html_resumo, unsafe_allow_html=True)
                with col_graf:
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("---") 

    # =========================================================================

    if apenas_alterados:
        df_exibicao = df_loja[df_loja['Possui_Alteracao_Sheets'] == True]
        st.info("💡 Exibindo estritamente colaboradores com digitação salva no Google Sheets.")
    else:
        df_exibicao = df_loja.copy()

    departamentos = sorted(df_exibicao['Dept'].dropna().unique())

    if not departamentos:
        st.warning("Nenhum registro encontrado com dados preenchidos nesta loja/visão.")

    for dept in departamentos:
        df_dept = df_exibicao[df_exibicao['Dept'] == dept]
        
        if focar_colaborador and colaborador_final:
            if colaborador_final not in df_dept['Nome'].values:
                continue
        
        total_funcionarios_dept = len(df_dept)
        expander_aberto = st.session_state["expander_global"]
        
        with st.expander(f"🏢 DEPARTAMENTO: {dept} ({total_funcionarios_dept})", expanded=expander_aberto):
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                if focar_colaborador and colaborador_final:
                    if colaborador_final not in df_funcao['Nome'].values:
                        continue
                
                st.markdown(f"**🔹 Cargo: {funcao}**")
                
                if modo_visao_global:
                    colunas_selecionadas = [
                        'Situação', 'Loja', 'Nome', 'Horario_Sistema_Real', 'Observação',
                        'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo',
                        'Status RH', 'Candidato', 'Data Admissão'
                    ]
                else:
                    colunas_selecionadas = [
                        'Situação', 'Nome', 'Horario_Sistema_Real', 'Observação',
                        'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo',
                        'Status RH', 'Candidato', 'Data Admissão'
                    ]

                if focar_colaborador and colaborador_final:
                    df_filtrado = df_funcao[df_funcao['Nome'] == colaborador_final][colunas_selecionadas]
                else:
                    df_filtrado = df_funcao[colunas_selecionadas]
                
                colspan_analista = 4 if modo_visao_global else 3
                
                html_tabela = f"""
<div class="tabela-container">
<table class="ql-table">
<thead>
<tr>
<th colspan="{colspan_analista}" style="background-color: #334155; color: white; text-align: center; font-weight: 600; padding: 8px;">📊 DONO: ANALISTA</th>
<th colspan="1" style="background-color: #d97706; color: white; text-align: center; font-weight: 600; padding: 8px;">📋 DONO: SUPERVISOR</th>
<th colspan="5" style="background-color: #047857; color: white; text-align: center; font-weight: 600; padding: 8px;">🏪 DONO: GERENTE</th>
<th colspan="3" style="background-color: #be123c; color: white; text-align: center; font-weight: 600; padding: 8px;">🤝 DONO: RH</th>
</tr>
<tr style="color: #e2e8f0; font-weight: 500;">
<th style="background-color: #1e293b; border-bottom: 2px solid #475569; text-align: center; padding: 8px;">Status</th>
"""
                
                if modo_visao_global:
                    html_tabela += '<th style="background-color: #1e293b; border-bottom: 2px solid #475569; text-align: center; padding: 8px;">Loja</th>\n'
                    
                cabecalhos = ["Nome do Colaborador", "Horário Sistema", "Observação", "Data Abertura", "Responsável", "Horário Contrato", "Sexo", "Motivo", "Status RH", "Candidato", "Data Admissão"]

                for cab in cabecalhos:
                    html_tabela += f'<th style="background-color: #1e293b; border-bottom: 2px solid #475569; text-align: center; padding: 8px;">{cab}</th>\n'
                
                html_tabela += """
</tr>
</thead>
<tbody>
"""
                
                for _, row in df_filtrado.iterrows():
                    html_tabela += "<tr>\n"
                    
                    badge_status = obter_badge_status(row['Situação'])
                    html_tabela += f"<td style='text-align: center;'>{badge_status}</td>\n"
                    
                    for col_nome in df_filtrado.columns[1:]:
                        val_original = row[col_nome]
                        
                        if col_nome == 'Loja':
                            try:
                                val_formatado = f"{int(float(str(val_original))):02d}"
                            except:
                                val_formatado = str(val_original)
                            html_tabela += f'<td class="celula-loja">{val_formatado}</td>\n'
                        
                        elif col_nome == 'Nome':
                            val_formatado = str(val_original).title()
                            html_tabela += f"<td>{val_formatado}</td>\n"
                            
                        elif col_nome == 'Status RH':
                            badge_rh = obter_badge_rh(val_original)
                            html_tabela += f"<td style='text-align: center;'>{badge_rh}</td>\n"
                            
                        else:
                            html_tabela += f"<td>{val_original}</td>\n"
                            
                    html_tabela += "</tr>\n"
                    
                html_tabela += """</tbody>
</table>
</div>
"""
                st.markdown(html_tabela, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro Geral no Sistema. Detalhes: {e}")
