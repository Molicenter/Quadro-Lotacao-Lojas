import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, date
import os

# =========================================================
# 🛠️ 1. CONFIGURAÇÕES INICIAIS E FUNÇÕES AUXILIARES VISUAIS
# =========================================================

st.set_page_config(
    page_title="Molicenter - QL (Quadro de Lotação)", 
    page_icon="passaro_logo.png" if os.path.exists("passaro_logo.png") else "📊",
    layout="wide"
)

def obter_classe_status(status):
    status_upper = str(status).strip().upper()
    if "ATIVO" in status_upper or "FÉRIAS" in status_upper or "FERIAS" in status_upper:
        return 'class="status-verde"'
    elif "AFASTAMENTO" in status_upper or "AFASTADO" in status_upper or "DEMITIDO" in status_upper:
        return 'class="status-vermelho"'
    return ""

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
    "gerente30@molicenter.com.br": {"senha": "moli1234", "perfil": "gerente", "loja_fixa": 30},
}

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

if "logado" not in st.session_state:
    st.session_state["logado"] = False
    st.session_state["usuario"] = ""
    st.session_state["perfil"] = ""
    st.session_state["loja_fixa"] = None

# =========================================================
# 🔐 2. INTERFACE DA TELA DE LOGIN
# =========================================================
if not st.session_state["logado"]:
    st.markdown("""
        <style>
        [data-testid="stColumn"] {
            max-width: 480px !important;
            margin: 0 auto !important;
        }
        h1 { font-size: 38px !important; font-weight: bold !important; }
        h5 { font-size: 18px !important; color: #aaaaaa !important; }
        
        .stTextInput label p { font-size: 16px !important; font-weight: bold !important; color: #ffffff !important; }
        .stTextInput input { font-size: 16px !important; padding: 12px 14px !important; height: 48px !important; }
        
        .stButton button { 
            font-size: 17px !important; 
            font-weight: bold !important; 
            height: 50px !important; 
            background-color: #244e73 !important;
            border: 1px solid #444444 !important;
        }
        </style>
        <br><br><br>
    """, unsafe_allow_html=True)
    
    _, col_centro, _ = st.columns([0.1, 9.8, 0.1])
    
    with col_centro:
        if os.path.exists("passaro_logo.png"):
            col_logo_vaga, col_texto_vaga = st.columns([0.35, 1], vertical_alignment="center")
            with col_logo_vaga:
                st.image("passaro_logo.png", width=95)
            with col_texto_vaga:
                st.markdown("<h1 style='margin: 0; padding-left: 0;'>Molicenter - QL</h1>", unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align: center;'>Molicenter - QL</h1>", unsafe_allow_html=True)
        
        st.markdown("<h5 style='text-align: center; margin-top: 5px;'>Quadro de Lotação</h5>", unsafe_allow_html=True)
        st.markdown("<hr style='margin-top: 10px; margin-bottom: 30px;'>", unsafe_allow_html=True)
        
        user_input = st.text_input("E-mail corporativo:")
        pass_input = st.text_input("Senha de acesso:", type="password")
        
        st.markdown("<br>", unsafe_allow_html=True)
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

# =========================================================
# 📊 3. CSS DO DASHBOARD INTERNO
# =========================================================
st.markdown("""
    <style>
    [data-testid="stApp"] {
        zoom: 1.0 !important;
    }
    
    .tabela-container { width: 100%; overflow-x: auto; margin-bottom: 15px; }
    .ql-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 11px; color: #ffffff; }
    
    .ql-table th { padding: 4px 6px; font-size: 11.5px !important; font-weight: bold; }
    .ql-table td { border: 1px solid #444444; padding: 3px 6px; text-align: left; white-space: nowrap; }
    
    .ql-table tr:nth-child(even) { background-color: #1e1e1e; }
    .ql-table tr:nth-child(odd) { background-color: #121212; }
    
    .status-verde { background-color: #15803d !important; color: white !important; font-weight: bold !important; text-align: center !important; }
    .status-vermelho { background-color: #b91c1c !important; color: white !important; font-weight: bold !important; text-align: center !important; }
    
    [data-testid="stAppViewBlockContainer"] { 
        padding-left: 1.2rem !important; 
        padding-right: 1.2rem !important; 
        padding-top: 1rem !important; 
        max-width: 100% !important;
    }
    
    div[data-testid="stExpander"] {
        margin-bottom: 6px !important;
        border: 1px solid #244e73 !important;
        border-radius: 6px !important;
        background-color: transparent !important;
    }
    
    div[data-testid="stExpander"] summary {
        background-color: #244e73 !important;
        border-radius: 5px 5px 5px 5px !important;
        padding: 10px 15px !important;
    }
    
    div[data-testid="stExpander"] summary p, 
    div[data-testid="stExpander"] summary span,
    div[data-testid="stExpander"] summary label {
        color: #ffffff !important;
        font-weight: bold !important;
        font-size: 12.5px !important;
    }
    
    div[data-testid="stExpander"] summary svg {
        color: #ffffff !important;
        fill: #ffffff !important;
    }
    
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] {
        background-color: transparent !important;
        padding-top: 5px !important;
    }
    </style>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state["logado"] = False
    st.rerun()

# =========================================================
# 📊 4. CARGA DE DADOS HÍBRIDA (COM CONDIÇÃO DE DATA ADMISSÃO)
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

            # Passo A: Pessoas que já constam no "banco ql.xlsx" (Sempre aparecem)
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

            # Passo B (CONDIÇÃO NOVA 🌟): Quem foi inserido manualmente pelo Sheets
            # Só sobe para a tabela se NÃO tiver uma "Data Admissão" preenchida!
            linhas_novas_manuais = []
            for registro in dados_sheets:
                nome_func = registro.get('Nome')
                try:
                    loja_reg = int(float(str(registro.get('Loja', 0))))
                except:
                    loja_reg = 0
                
                if (nome_func, loja_reg) not in mapeados:
                    # Formata a data de admissão vinda do sheets para verificar
                    data_ad_checar = formatar_data_br(registro.get('Data Admissão', '-'))
                    
                    # Se tiver qualquer data válida preenchida (diferente de "-"), ESSE REGISTRO MANUAL SOME 🌟
                    if data_ad_checar != "-":
                        continue
                        
                    sigla_sexo = str(registro.get('Sexo', '-')).strip()
                    sexo_exibicao = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                    
                    dept_final = registro.get('Dept') if registro.get('Dept') else 'HISTÓRICO / EX-COLABORADORES'
                    funcao_final = registro.get('Funco') if registro.get('Funco') else (registro.get('Função') if registro.get('Função') else 'Sem Vínculo Atual')
                    situacao_final = registro.get('Situaçao') if registro.get('Situaçao') else (registro.get('Situação') if registro.get('Situação') else 'Demitido')
                    
                    linha_manual = {
                        'Loja': loja_reg,
                        'Nome': nome_func, 
                        'Situação': situacao_final, 
                        'Dept': dept_final, 
                        'Função': funcao_final,
                        'Horario_Sistema_Real': '-',
                        'Observação': registro.get('Observação', '-'),
                        'Data Abertura': formatar_data_br(registro.get('Data Abertura', '-')),
                        'Responsável': registro.get('Responsável', '-'),
                        'Horário Contrato': str(registro.get('Horário Contrato', '-')),
                        'Sexo': sexo_exibicao,
                        'Motivo': registro.get('Motivo', '-'),
                        'Status RH': registro.get('Status RH', '-'),
                        'Candidato': registro.get('Candidato', '-'),
                        'Data Admissão': data_ad_checar,
                        'Possui_Alteracao_Sheets': True
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
        st.markdown("<div style='max-width: 300px;'>", unsafe_allow_html=True)
        loja_selecionada = st.selectbox("Selecione a Loja para Análise:", lojas_disponiveis, format_func=lambda x: f"Loja {int(x):02d}")
        st.markdown("</div>", unsafe_allow_html=True)

    df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()

    # =========================================================
    # 🛠️ BARRA LATERAL (SIDEBAR) - FORMULÁRIO OPERACIONAL
    # =========================================================
    st.sidebar.header("📝 Alimentar Informações")
    
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
        st.sidebar.markdown("---")
        
        # 🔸 SUPERVISOR
        st.sidebar.subheader("🔸 Supervisor")
        val_obs_default = str(dados_func['Observação']) if (dados_func is not None and str(dados_func['Observação']) != "-") else ""
        if perfil in ["analista", "rh", "supervisor"]:
            nova_obs = st.sidebar.text_area("Observação:", value=val_obs_default)
        else:
            st.sidebar.text_input("Observação:", value=val_obs_default if val_obs_default else "-", disabled=True)
            nova_obs = val_obs_default if val_obs_default else "-"
        
        # 🔹 GERENTE
        st.sidebar.subheader("🔹 Gerente")
        if perfil in ["analista", "rh", "supervisor", "gerente"]:
            data_ab_atual = str(dados_func['Data Abertura']).strip() if dados_func is not None else "-"
            try:
                data_ab_default = datetime.strptime(data_ab_atual, "%d/%m/%Y").date() if data_ab_atual != "-" else date.today()
            except:
                data_ab_default = date.today()
            nova_data_ab_col = st.sidebar.date_input("Data Abertura:", value=data_ab_default, format="DD/MM/YYYY")
            nova_data_abertura = nova_data_ab_col.strftime("%d/%m/%Y")
            
            val_resp_default = str(dados_func['Responsável']) if (dados_func is not None and str(dados_func['Responsável']) != "-") else ""
            novo_responsavel = st.sidebar.text_input("Responsável:", value=val_resp_default)
            
            val_horario_default = str(dados_func['Horário Contrato']) if (dados_func is not None and str(dados_func['Horário Contrato']) != "-") else ""
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=val_horario_default)
            
            sexo_exibido_atual = str(dados_func['Sexo']).strip() if dados_func is not None else "-"
            idx_sexo = OPCOES_SEXO.index(sexo_exibido_atual) if sexo_exibido_atual in OPCOES_SEXO else 0
            texto_sexo_selecionado = st.sidebar.selectbox("Sexo:", OPCOES_SEXO, index=idx_sexo)
            novo_sexo = MAPA_SEXO_SIGLA.get(texto_sexo_selecionado, "-")
            
            motivo_atual = str(dados_func['Motivo']).strip() if dados_func is not None else "-"
            idx_motivo = OPCOES_MOTIVO.index(motivo_atual) if motivo_atual in OPCOES_MOTIVO else 0
            novo_motivo = st.sidebar.selectbox("Motivo:", OPCOES_MOTIVO, index=idx_motivo)
        else:
            nova_data_abertura = st.sidebar.text_input("Data Abertura:", value=str(dados_func['Data Abertura']) if dados_func is not None else "-", disabled=True)
            novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']) if dados_func is not None else "-", disabled=True)
            novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']) if dados_func is not None else "-", disabled=True)
            novo_sexo_exibido = st.sidebar.text_input("Sexo:", value=str(dados_func['Sexo']) if dados_func is not None else "-", disabled=True)
            novo_sexo = MAPA_SEXO_SIGLA.get(novo_sexo_exibido, "-")
            novo_motivo = st.sidebar.text_input("Motivo:", value=str(dados_func['Motivo']) if dados_func is not None else "-", disabled=True)
        
        # 🔺 RH
        st.sidebar.subheader("🔺 Recursos Humanos (RH)")
        if perfil in ["analista", "rh"]:
            status_atual = str(dados_func['Status RH']).strip() if dados_func is not None else "-"
            idx_status = OPCOES_STATUS_RH.index(status_atual) if status_atual in OPCOES_STATUS_RH else 0
            novo_status_rh = st.sidebar.selectbox("Status RH:", OPCOES_STATUS_RH, index=idx_status)
            
            val_cand_default = str(dados_func['Candidato']) if (dados_func is not None and str(dados_func['Candidato']) != "-") else ""
            novo_candidato = st.sidebar.text_input("Candidato:", value=val_cand_default)
            
            data_ad_atual = str(dados_func['Data Admissão']).strip() if dados_func is not None else "-"
            tem_data_anterior = data_ad_atual != "-"
            
            definir_data = st.sidebar.checkbox("Definir data de admissão", value=tem_data_anterior)
            
            if definir_data:
                try:
                    data_ad_default = datetime.strptime(data_ad_atual, "%d/%m/%Y").date() if tem_data_anterior else date.today()
                except:
                    data_ad_default = date.today()
                nova_data_ad_col = st.sidebar.date_input("Data Admissão:", value=data_ad_default, format="DD/MM/YYYY")
                nova_data_admissao = nova_data_ad_col.strftime("%d/%m/%Y")
            else:
                nova_data_admissao = "-"
        else:
            novo_status_rh = st.sidebar.text_input("Status RH:", value=str(dados_func['Status RH']) if dados_func is not None else "-", disabled=True)
            novo_candidato = st.sidebar.text_input("Candidato:", value=str(dados_func['Candidato']) if dados_func is not None else "-", disabled=True)
            nova_data_admissao = st.sidebar.text_input("Data Admissão:", value=str(dados_func['Data Admissão']) if dados_func is not None else "-", disabled=True)
        
        if st.sidebar.button("💾 Salvar Alterações", use_container_width=True):
            if tipo_registro == "Cadastrar Novo / Não Listado" and not colaborador_final:
                st.sidebar.error("Erro: O nome do colaborador não pode ficar em branco.")
            else:
                payload = {
                    "Loja": int(loja_selecionada),
                    "Nome": colaborador_final,
                    "Dept": dept_final,
                    "Funcao": funcao_final,
                    "Situaçao": situacao_final,
                    "Observacao": nova_obs,
                    "DataAbertura": nova_data_abertura,
                    "Responsavel": novo_responsavel,
                    "HorarioContrato": str(novo_horario_contrato),
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
    # 🏪 5. INDICADORES E MATRIZ VISUAL CENTRAL
    # =========================================================
    
    col_titulo, col_filtro_sheets = st.columns([1.5, 1], vertical_alignment="center")
    with col_titulo:
        st.markdown(f"### 🏪 Quadro de Funcionários - Loja {int(loja_selecionada):02d}")
    with col_filtro_sheets:
        apenas_alterados = st.checkbox("📋 Visualizar apenas registros alterados/inseridos (Geral)", value=False)

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
    
    st.markdown("🔍 **Localizador Rápido**")
    focar_colaborador = st.checkbox(f"Focar visualização apenas no colaborador: {colaborador_final}" if colaborador_final else "Focar colaborador selecionado", value=False)
    
    if apenas_alterados:
        df_exibicao = df_loja[df_loja['Possui_Alteracao_Sheets'] == True]
        st.info("💡 Exibindo estritamente colaboradores com digitação salva no Google Sheets.")
    else:
        df_exibicao = df_loja.copy()

    departamentos = sorted(df_exibicao['Dept'].dropna().unique())

    if not departamentos:
        st.warning("Nenhum registro encontrado com dados preenchidos nesta loja.")

    for dept in departamentos:
        df_dept = df_exibicao[df_exibicao['Dept'] == dept]
        
        if focar_colaborador and colaborador_final:
            if colaborador_final not in df_dept['Nome'].values:
                continue
        
        # 🌟 LINHA ALTERADA: Agora os expanders iniciam recolhidos (False)
        expander_aberto = False 
        
        with st.expander(f"🏢 DEPARTAMENTO: {dept}", expanded=expander_aberto):
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                if focar_colaborador and colaborador_final:
                    if colaborador_final not in df_funcao['Nome'].values:
                        continue
                
                st.markdown(f"**🔹 Cargo: {funcao}**")
                
                if focar_colaborador and colaborador_final:
                    df_filtrado = df_funcao[df_funcao['Nome'] == colaborador_final][[
                        'Situação', 'Nome', 'Horario_Sistema_Real', 'Observação',
                        'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo',
                        'Status RH', 'Candidato', 'Data Admissão'
                    ]]
                else:
                    df_filtrado = df_funcao[[
                        'Situação', 'Nome', 'Horario_Sistema_Real', 'Observação',
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
                    classe_status = obter_classe_status(row['Situação'])
                    html_tabela += f"<td {classe_status}>{row['Situação']}</td>"
                    
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
