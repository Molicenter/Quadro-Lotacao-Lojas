import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date

# 1. CONFIGURAÇÃO DA PÁGINA (Estilo Dashboard em tela cheia)
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

URL_API_SHEETS = "https://script.google.com/macros/s/AKfycbz_OA0O8zS-rMuuZEYu5rUeZow3lEZt-GcGYUWUbX4kiaRwDoQ9vZeoknsF5K-zFZvn/exec"

# Estilo global das tabelas em HTML
st.markdown("""
    <style>
    .tabela-container { width: 100%; overflow-x: auto; margin-bottom: 25px; }
    .ql-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; color: #ffffff; }
    .ql-table th, .ql-table td { border: 1px solid #444444; padding: 8px; text-align: left; }
    .ql-table tr:nth-child(even) { background-color: #1e1e1e; }
    .ql-table tr:nth-child(odd) { background-color: #121212; }
    </style>
""", unsafe_allow_html=True)

# DICIONÁRIO DE USUÁRIOS, SENHAS E PERMISSÕES (Matriz de Perfil)
USUARIOS_DB = {
    "analista@molicenter.com.br": {"senha": "moli1234", "perfil": "analista", "loja_fixa": None},
    "rh1@molicenter.com.br": {"senha": "moli1234", "perfil": "rh", "loja_fixa": None},
    "supervisorlojas@molicenter.com.br": {"senha": "moli1234", "perfil": "supervisor", "loja_fixa": None},
    "gerente1@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 1},
    "gerente2@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 2},
    "gerente3@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 3},
    "gerente4@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 4},
    "gerente5@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 5},
    "gerente6@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 6},
    "gerente7@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 7},
    "gerente8@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 8},
}

# GERENCIAMENTO DE ESTADO DO LOGIN (Session State)
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["perfil"] = ""
    st.session_state["loja_fixa"] = None

# INTERFACE DA TELA DE LOGIN
if not st.session_state["logado"]:
    st.title("🔐 Sistema Quadro de Lotação - Molicenter")
    st.markdown("---")
    
    col_login, _ = st.columns([1, 2])
    with col_login:
        user_input = st.text_input("E-mail corporativo:")
        pass_input = st.text_input("Senha de acesso:", type="password")
        
        if st.button("Entrar no Sistema", use_container_width=True):
            user_clean = user_input.strip().lower()
            if user_clean in USUARIOS_DB and USUARIOS_DB[user_clean]["senha"] == pass_input:
                st.session_state["logado"] = True
                st.session_state["usuario"] = user_clean
                st.session_state["perfil"] = USUARIOS_DB[user_clean]["perfil"]
                st.session_state["loja_fixa"] = USUARIOS_DB[user_clean]["loja_fixa"]
                st.success("Acesso concedido!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos. Tente novamente.")
    st.stop()

if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state["logado"] = False
    st.rerun()

# FUNÇÃO DE FORMATAÇÃO DE DATAS PARA EXIBIÇÃO NA TABELA
def formatar_data_br(valor):
    val_str = str(valor).strip()
    if val_str in ["nan", "None", "", "-", "0"]:
        return "-"
    try:
        # Tenta tratar formatos ISO vindo do Sheets (ex: 2026-05-30T12:00:00.000Z ou similar)
        if "T" in val_str:
            val_str = val_str.split("T")[0]
        dt = pd.to_datetime(val_str)
        return dt.strftime("%d/%m/%Y")
    except:
        return val_str

# 3. FUNÇÃO HÍBRIDA DE CARGA DE DADOS
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

    try:
        response = requests.get(URL_API_SHEETS, timeout=10)
        if response.status_code == 200:
            dados_sheets = response.json()
            for registro in dados_sheets:
                nome_func = registro.get('Nome')
                try:
                    loja_reg = int(float(str(registro.get('Loja', 0))))
                except:
                    loja_reg = 0
                
                idx_list = df[(df['Nome'] == nome_func) & (df['Loja'] == loja_reg)].index
                if len(idx_list) > 0:
                    idx = idx_list[0]
                    df.at[idx, 'Observação'] = registro.get('Observação', '-')
                    df.at[idx, 'Data Abertura'] = formatar_data_br(registro.get('Data Abertura', '-'))
                    df.at[idx, 'Responsável'] = registro.get('Responsável', '-')
                    df.at[idx, 'Horário Contrato'] = registro.get('Horário Contrato', '-')
                    df.at[idx, 'Sexo'] = registro.get('Sexo', '-')
                    df.at[idx, 'Motivo'] = registro.get('Motivo', '-')
                    df.at[idx, 'Status RH'] = registro.get('Status RH', '-')
                    df.at[idx, 'Candidato'] = registro.get('Candidato', '-')
                    df.at[idx, 'Data Admissão'] = formatar_data_br(registro.get('Data Admissão', '-'))
    except:
        pass

    return df

try:
    df_bruto = carregar_dados_completos()

    perfil = st.session_state["perfil"]
    loja_fixa = st.session_state["loja_fixa"]

    st.title("📊 Quadro de Lotação (QL) // Requisição")
    st.sidebar.markdown(f"**Usuário:** `{st.session_state['usuario']}`")
    st.sidebar.markdown(f"**Nível:** `{perfil.upper()}`")
    st.markdown("---")

    if loja_fixa is not None:
        loja_selecionada = loja_fixa
        st.info(f"🏪 Modo de Visualização Restrito: **Loja {loja_selecionada:02d}**")
    else:
        lojas_disponiveis = sorted([int(l) for l in df_bruto['Loja'].unique() if int(l) > 0])
        loja_selecionada = st.selectbox("Selecione a Loja para Análise:", lojas_disponiveis, format_func=lambda x: f"Loja {int(x):02d}")

    df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()

    # =========================================================
    # 🛠️ BARRA LATERAL (SIDEBAR) - FORMULÁRIO COM SELETORES DE DATA
    # =========================================================
    st.sidebar.header("📝 Alimentar Informações")
    funcionarios_loja = sorted(df_loja['Nome'].dropna().unique())
    colaborador_selecionado = st.sidebar.selectbox("Selecione o Colaborador:", funcionarios_loja)
    
    if colaborador_selecionado:
        dados_func = df_loja[df_loja['Nome'] == colaborador_selecionado].iloc[0]
        st.sidebar.markdown("---")
        
        # 🔸 BLOCO DO SUPERVISOR
        st.sidebar.subheader("🔸 Supervisor")
        if perfil in ["analista", "rh", "supervisor"]:
            nova_obs = st.sidebar.text_area("Observação:", value=str(dados_func['Observação']) if str(dados_func['Observação']) != "-" else "")
        else:
            st.sidebar.text_input("Observação:", value=str(dados_func['Observação']), disabled=True)
            nova_obs = str(dados_func['Observação'])
        
        # 🔹 BLOCO DO GERENTE
        st.sidebar.subheader("🔹 Gerente")
        if perfil in ["analista", "rh", "supervisor", "gerente"]:
            # Conversão inteligente para o calendário reconhecer a data atual ou carregar padrão
            data_ab_atual = str(dados_func['Data Abertura']).strip()
            try:
                data_ab_default = datetime.strptime(data_ab_atual, "%d/%m/%Y").date() if data_ab_atual != "-" else date.today()
            except:
                data_ab_default = date.today()
            
            # Seletor em formato de Calendário Oficial
            nova_data_ab_col = st.sidebar.date_input("Data Abertura:", value=data_ab_default, format="DD/MM/YYYY")
            nova_data_abertura = nova_data_ab_col.strftime("%d/%m/%Y")
            
            novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']) if str(dados_func['Responsável']) != "-" else "")
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']) if str(dados_func['Horário Contrato']) != "-" else "")
            
            sexo_atual = str(dados_func['Sexo']).strip().upper()
            sexo_index = 0
            if sexo_atual == "M": sexo_index = 1
            elif sexo_atual == "F": sexo_index = 2
            novo_sexo = st.sidebar.selectbox("Sexo:", ["-", "M", "F"], index=sexo_index)
            novo_motivo = st.sidebar.text_input("Motivo:", value=str(dados_func['Motivo']) if str(dados_func['Motivo']) != "-" else "")
        else:
            nova_data_abertura = st.sidebar.text_input("Data Abertura:", value=str(dados_func['Data Abertura']), disabled=True)
            novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']), disabled=True)
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']), disabled=True)
            novo_sexo = st.sidebar.text_input("Sexo:", value=str(dados_func['Sexo']), disabled=True)
            novo_motivo = st.sidebar.text_input("Motivo:", value=str(dados_func['Motivo']), disabled=True)
        
        # 🔺 BLOCO DO RH
        st.sidebar.subheader("🔺 Recursos Humanos (RH)")
        if perfil in ["analista", "rh"]:
            novo_status_rh = st.sidebar.text_input("Status RH:", value=str(dados_func['Status RH']) if str(dados_func['Status RH']) != "-" else "")
            novo_candidato = st.sidebar.text_input("Candidato:", value=str(dados_func['Candidato']) if str(dados_func['Candidato']) != "-" else "")
            
            # Calendário para o RH também!
            data_ad_atual = str(dados_func['Data Admissão']).strip()
            try:
                data_ad_default = datetime.strptime(data_ad_atual, "%d/%m/%Y").date() if data_ad_atual != "-" else date.today()
            except:
                data_ad_default = date.today()
            
            nova_data_ad_col = st.sidebar.date_input("Data Admissão:", value=data_ad_default, format="DD/MM/YYYY")
            nova_data_admissao = nova_data_ad_col.strftime("%d/%m/%Y")
        else:
            novo_status_rh = st.sidebar.text_input("Status RH:", value=str(dados_func['Status RH']), disabled=True)
            novo_candidato = st.sidebar.text_input("Candidato:", value=str(dados_func['Candidato']), disabled=True)
            nova_data_admissao = st.sidebar.text_input("Data Admissão:", value=str(dados_func['Data Admissão']), disabled=True)
        
        # BOTÃO SALVAR
        if st.sidebar.button("💾 Salvar Alterações", use_container_width=True):
            payload = {
                "Loja": int(loja_selecionada),
                "Nome": colaborador_selecionado,
                "Observacao": nova_obs,
                "DataAbertura": nova_data_abertura,
                "Responsavel": novo_responsavel,
                "HorarioContrato": novo_horario_contrato,
                "Sexo": novo_sexo,
                "Motivo": novo_motivo,
                "StatusRH": novo_status_rh,
                "Candidato": novo_candidato,
                "DataAdmissao": nova_data_admissao,
                "Usuario": st.session_state["usuario"]
            }
            
            try:
                headers = {'Content-Type': 'application/json'}
                res = requests.post(URL_API_SHEETS, data=json.dumps(payload), headers=headers, timeout=10)
                if res.status_code == 200:
                    st.sidebar.success("Dados salvos com sucesso!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.sidebar.error("Erro ao comunicar com a API do Sheets.")
            except Exception as e:
                st.sidebar.error(f"Erro de conexão: {e}")

    # =========================================================
    # 🏪 INDICADORES E PAINEL VISUAL (TELA PRINCIPAL)
    # =========================================================
    st.markdown(f"### 🏪 Quadro de Funcionários - Loja {int(loja_selecionada):02d}")

    df_loja['Situação_Upper'] = df_loja['Situação'].astype(str).str.upper()
    ativos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('ATIVO')])
    demitidos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('DEMITIDO')])
    ferias_afastados = len(df_loja[df_loja['Situação_Upper'].str.contains('FÉRIAS|AFASTAMENTO|AFASTADO')])

    col1, col2, col3 = st.columns(3)
    col1.metric("Funcionários Ativos", ativos_qtd)
    col2.metric("Demitidos", demitidos_qtd)
    col3.metric("Férias / Afastamentos", ferias_afastados)

    st.markdown("---")

    st.subheader("📋 Distribuição por Setor e Cargo")
    departamentos = sorted(df_loja['Dept'].dropna().unique())

    for dept in departamentos:
        with st.expander(f"🏢 DEPARTAMENTO: {dept}", expanded=True):
            df_dept = df_loja[df_loja['Dept'] == dept]
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                st.markdown(f"**🔹 Cargo: {funcao}**")
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                df_filtrado = df_funcao[[
                    'Situação', 'Nome', 'Horario_Sistema_Real',
                    'Observação',
                    'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo',
                    'Status RH', 'Candidato', 'Data Admissão'
                ]]
                
                html_tabela = f"""
                <div class="tabela-container">
                    <table class="ql-table">
                        <thead>
                            <tr>
                                <th colspan="3" style="background-color: #1c3d5a; color: white; text-align: center; font-weight: bold;">DONO: ANALISTA</th>
                                <th colspan="1" style="background-color: #d97706; color: white; text-align: center; font-weight: bold;">DONO: SUPERVISOR</th>
                                <th colspan="5" style="background-color: #15803d; color: white; text-align: center; font-weight: bold;">DONO: GERENTE</th>
                                <th colspan="3" style="background-color: #b91c1c; color: white; text-align: center; font-weight: bold;">DONO: RH</th>
                            </tr>
                            <tr style="background-color: #262626; color: #dddddd;">
                                <th>Status</th><th>Nome do Colaborador</th><th>Horário Sistema</th>
                                <th>Observação</th>
                                <th>Data Abertura</th><th>Responsável</th><th>Horário Contrato</th><th>Sexo</th><th>Motivo</th>
                                <th>Status RH</th><th>Candidato</th><th>Data Admissão</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                for _, row in df_filtrado.iterrows():
                    html_tabela += "<tr>"
                    for val in row:
                        html_tabela += f"<td>{val}</td>"
                    html_tabela += "</tr>"
                    
                html_tabela += """
                        </tbody>
                    </table>
                </div>
                """
                st.markdown(html_tabela, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro Geral no Sistema. Detalhes: {e}")
