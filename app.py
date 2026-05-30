import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date
import os

# 1. CONFIGURAÇÃO DA PÁGINA (Com o novo título e o passarinho no ícone da aba)
st.set_page_config(
    page_title="Molicenter - QL (Quadro de Lotação)", 
    page_icon="passaro_logo.png" if os.path.exists("passaro_logo.png") else "📊",
    layout="wide"
)

URL_API_SHEETS = "https://script.google.com/macros/s/AKfycbz_OA0O8zS-rMuuZEYu5rUeZow3lEZt-GcGYUWUbX4kiaRwDoQ9vZeoknsF5K-zFZvn/exec"

# Estilo global das tabelas em HTML
st.markdown("""
    <style>
    .tabela-container { width: 100%; overflow-x: auto; margin-bottom: 25px; }
    .ql-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 14px; color: #ffffff; }
    .ql-table th, .ql-table td { border: 1px solid #444444; padding: 10px 14px; text-align: left; white-space: nowrap; }
    .ql-table tr:nth-child(even) { background-color: #1e1e1e; }
    .ql-table tr:nth-child(odd) { background-color: #121212; }
    
    /* Classes corrigidas para centralizar o texto junto com a cor condicional */
    .status-verde { background-color: #15803d !important; color: white !important; font-weight: bold !important; text-align: center !important; }
    .status-vermelho { background-color: #b91c1c !important; color: white !important; font-weight: bold !important; text-align: center !important; }
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

# LISTAS DE OPÇÕES PADRONIZADAS
OPCOES_SEXO = ["-", "Indiferente", "Masculino", "Feminino"]
MAPA_SEXO_SIGLA = {"-": "-", "Indiferente": "I", "Masculino": "M", "Feminino": "F"}
MAPA_SIGLA_SEXO = {"-": "-", "I": "Indiferente", "M": "Masculino", "F": "Feminino"}

OPCOES_MOTIVO = ["-", "Aumento QL", "Função Nova", "Mudança Setor", "Substituição", "Transferência"]

OPCOES_STATUS_RH = [
    "-", "Requisição atendida", "Aguardando resposta Candidato", "Cancelado", 
    "Divulgação da vaga", "Documentação Admissão", "Entrevista Loja", "Entrevista RH", 
    "Exame Admissional", "Não Validado pelo gerente", "Previsão de Início", 
    "Triagem de Curriculuns", "Validado pelo gerente", "Desistencia Candidato"
]

# GERENCIAMENTO DE ESTADO DO LOGIN
if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["perfil"] = ""
    st.session_state["loja_fixa"] = None

# INTERFACE DA TELA DE LOGIN
if not st.session_state["logado"]:
    col_logo_top, col_title_top = st.columns([0.4, 2.5], vertical_alignment="center")
    with col_logo_top:
        if os.path.exists("passaro_logo.png"):
            st.image("passaro_logo.png", width=110)
    with col_title_top:
        st.title("Molicenter - QL (Quadro de Lotação)")
    
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
                st.error("Usuários ou senha incorretos. Tente novamente.")
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
        if "T" in val_str:
            val_str = val_str.split("T")[0]
        dt = pd.to_datetime(val_str)
        return dt.strftime("%d/%m/%Y")
    except:
        return val_str

# FUNÇÃO AUXILIAR PARA RETORNAR A CLASSE CSS DO STATUS CENTRALIZADO
def obtener_classe_status(status):
    status_upper = str(status).strip().upper()
    if "ATIVO" in status_upper or "FÉRIAS" in status_upper or "FERIAS" in status_upper:
        return 'class="status-verde"'
    elif "AFASTAMENTO" in status_upper or "AFASTADO" in status_upper or "DEMITIDO" in status_upper:
        return 'class="status-vermelho"'
    return ""

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
                    
                    sigla_sexo = str(registro.get('Sexo', '-')).strip()
                    sexo_exibicao = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                    
                    df.at[idx, 'Observação'] = registro.get('Observação', '-')
                    df.at[idx, 'Data Abertura'] = formatar_data_br(registro.get('Data Abertura', '-'))
                    df.at[idx, 'Responsável'] = registro.get('Responsável', '-')
                    df.at[idx, 'Horário Contrato'] = registro.get('Horário Contrato', '-')
                    df.at[idx, 'Sexo'] = sexo_exibicao
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

    col_main_logo, col_main_title = st.columns([0.4, 2.5], vertical_alignment="center")
    with col_main_logo:
        if os.path.exists("passaro_logo.png"):
            st.image("passaro_logo.png", width=100)
    with col_main_title:
        st.title("Molicenter - QL (Quadro de Lotação)")
        
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
    # 🛠️ BARRA LATERAL (SIDEBAR) - FORMULÁRIO OPERACIONAL
    # =========================================================
    st.sidebar.header("📝 Alimentar Informações")
    funcionarios_loja = sorted(df_loja['Nome'].dropna().unique())
    colaborador_selecionado = st.sidebar.selectbox("Selecione o Colaborador:", funcionarios_loja)
    
    if colaborador_selecionado:
        dados_func = df_loja[df_loja['Nome'] == colaborador_selecionado].iloc[0]
        st.sidebar.markdown("---")
        
        st.sidebar.subheader("🔸 Supervisor")
        if perfil in ["analista", "rh", "supervisor"]:
            nova_obs = st.sidebar.text_area("Observação:", value=str(dados_func['Observação']) if str(dados_func['Observação']) != "-" else "")
        else:
            st.sidebar.text_input("Observação:", value=str(dados_func['Observação']), disabled=True)
            nova_obs = str(dados_func['Observação'])
        
        st.sidebar.subheader("🔹 Gerente")
        if perfil in ["analista", "rh", "supervisor", "gerente"]:
            data_ab_atual = str(dados_func['Data Abertura']).strip()
            try:
                data_ab_default = datetime.strptime(data_ab_atual, "%d/%m/%Y").date() if data_ab_atual != "-" else date.today()
            except:
                data_ab_default = date.today()
            nova_data_ab_col = st.sidebar.date_input("Data Abertura:", value=data_ab_default, format="DD/MM/YYYY")
            nova_data_abertura = nova_data_ab_col.strftime("%d/%m/%Y")
            
            novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']) if str(dados_func['Responsável']) != "-" else "")
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']) if str(dados_func['Horário Contrato']) != "-" else "")
            
            sexo_exibido_atual = str(dados_func['Sexo']).strip()
            idx_sexo = OPCOES_SEXO.index(sexo_exibido_atual) if sexo_exibido_atual in OPCOES_SEXO else 0
            texto_sexo_selecionado = st.sidebar.selectbox("Sexo:", OPCOES_SEXO, index=idx_sexo)
            novo_sexo = MAPA_SEXO_SIGLA.get(texto_sexo_selecionado, "-")
            
            motivo_atual = str(dados_func['Motivo']).strip()
            idx_motivo = OPCOES_MOTIVO.index(motivo_atual) if motivo_atual in OPCOES_MOTIVO else 0
            novo_motivo = st.sidebar.selectbox("Motivo:", OPCOES_MOTIVO, index=idx_motivo)
        else:
            nova_data_abertura = st.sidebar.text_input("Data Abertura:", value=str(dados_func['Data Abertura']), disabled=True)
            novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']), disabled=True)
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']), disabled=True)
            novo_sexo_exibido = st.sidebar.text_input("Sexo:", value=str(dados_func['Sexo']), disabled=True)
            novo_sexo = MAPA_SEXO_SIGLA.get(novo_sexo_exibido, "-")
            novo_motivo = st.sidebar.text_input("Motivo:", value=str(dados_func['Motivo']), disabled=True)
        
        st.sidebar.subheader("🔺 Recursos Humanos (RH)")
        if perfil in ["analista", "rh"]:
            status_atual = str(dados_func['Status RH']).strip()
            idx_status = OPCOES_STATUS_RH.index(status_atual) if status_atual in OPCOES_STATUS_RH else 0
            novo_status_rh = st.sidebar.selectbox("Status RH:", OPCOES_STATUS_RH, index=idx_status)
            
            novo_candidato = st.sidebar.text_input("Candidato:", value=str(dados_func['Candidato']) if str(dados_func['Candidato']) != "-" else "")
            
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
                                <th colspan="3" style="background-color: #1c3d5a; color: white; text-align: center; font-weight: bold; border-bottom: none;">DONO: ANALISTA</th>
                                <th colspan="1" style="background-color: #d97706; color: white; text-align: center; font-weight: bold; border-bottom: none;">DONO: SUPERVISOR</th>
                                <th colspan="5" style="background-color: #15803d; color: white; text-align: center; font-weight: bold; border-bottom: none;">DONO: GERENTE</th>
                                <th colspan="3" style="background-color: #b91c1c; color: white; text-align: center; font-weight: bold; border-bottom: none;">DONO: RH</th>
                            </tr>
                            <tr style="color: #ffffff; font-weight: bold;">
                                <th style="background-color: #244e73; border-top: none; text-align: center;">Status</th>
                                <th style="background-color: #244e73; border-top: none; text-align: center;">Nome do Colaborador</th>
                                <th style="background-color: #244e73; border-top: none; text-align: center;">Horário Sistema</th>
                                <th style="background-color: #b36205; border-top: none; text-align: center;">Observação</th>
                                <th style="background-color: #116631; border-top: none; text-align: center;">Data Abertura</th>
                                <th style="background-color: #116631; border-top: none; text-align: center;">Responsável</th>
                                <th style="background-color: #116631; border-top: none; text-align: center;">Horário Contrato</th>
                                <th style="background-color: #116631; border-top: none; text-align: center;">Sexo</th>
                                <th style="background-color: #116631; border-top: none; text-align: center;">Motivo</th>
                                <th style="background-color: #941616; border-top: none; text-align: center;">Status RH</th>
                                <th style="background-color: #941616; border-top: none; text-align: center;">Candidato</th>
                                <th style="background-color: #941616; border-top: none; text-align: center;">Data Admissão</th>
                            </tr>
                        </thead>
                        <tbody>
                """
                
                for _, row in df_filtrado.iterrows():
                    html_tabela += "<tr>"
                    
                    # Primeira célula (Status) com cor condicional e texto centralizado pelo CSS
                    classe_status = obter_classe_status(row['Situação'])
                    html_tabela += f"<td {classe_status}>{row['Situação']}</td>"
                    
                    # Demais colunas alinhadas normalmente em linha única
                    for col_nome in row.index[1:]:
                        html_tabela += f"<td>{row[col_nome]}</td>"
                        
                    html_tabela += "</tr>"
                    
                html_tabela += """
                        </tbody>
                    </table>
                </div>
                """
                st.markdown(html_tabela, unsafe_allow_html=True)

except Exception as e:
    st.error(f"Erro Geral no Sistema. Detalhes: {e}")
