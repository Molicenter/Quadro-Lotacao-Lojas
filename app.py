import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

# Estilo global das tabelas em HTML
st.markdown("""
    <style>
    .tabela-container {
        width: 100%;
        overflow-x: auto;
        margin-bottom: 25px;
    }
    .ql-table {
        width: 100%;
        border-collapse: collapse;
        font-family: sans-serif;
        font-size: 14px;
        color: #ffffff;
    }
    .ql-table th, .ql-table td {
        border: 1px solid #444444;
        padding: 8px;
        text-align: left;
    }
    .ql-table tr:nth-child(even) {
        background-color: #1e1e1e;
    }
    .ql-table tr:nth-child(odd) {
        background-color: #121212;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Quadro de Lotação (QL) // Requisição")
st.markdown("---")

# 2. CONEXÃO DIRETA COM O GOOGLE SHEETS
# (O Streamlit busca as credenciais em .streamlit/secrets.toml)
conn = st.connection("gsheets", type=GSheetsConnection)

def carregar_dados_sheets():
    # Carrega a aba "Banco" da sua planilha configurada
    df = conn.read(worksheet="Banco", ttl="0d")
    
    # Tratamento do Horário do Sistema
    nome_coluna_horario = 'Descrição (Escala)'
    if nome_coluna_horario in df.columns:
        df['Horario_Sistema_Real'] = df[nome_coluna_horario].astype(str).str.replace('.0', '', regex=False).str.strip()
        df['Horario_Sistema_Real'] = df['Horario_Sistema_Real'].apply(lambda x: '-' if x in ['nan', 'None', ''] else x)
    else:
        df['Horario_Sistema_Real'] = "-"
        
    # Garante que as colunas de digitação existam e estejam limpas se nulas
    colunas_digitacao = [
        'Observação', 'Data Abertura', 'Responsável', 'Horário Contrato', 
        'Sexo', 'Motivo', 'Status RH', 'Candidato', 'Data Admissão'
    ]
    for col in colunas_digitacao:
        if col not in df.columns:
            df[col] = "-"
        else:
            df[col] = df[col].fillna("-").astype(str).str.replace('.0', '', regex=False)
            
    return df

try:
    df_bruto = carregar_dados_sheets()

    # 3. FILTRO DE LOJA (NA TELA PRINCIPAL)
    lojas_disponiveis = sorted(df_bruto['Loja'].dropna().unique())
    loja_selecionada = st.selectbox(
        "Selecione a Loja para Análise:", 
        lojas_disponiveis, 
        format_func=lambda x: f"Loja {int(x):02d}"
    )

    df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()

    # =========================================================
    # 🛠️ BARRA LATERAL (SIDEBAR) - FORMULÁRIO DE DIGITAÇÃO
    # =========================================================
    st.sidebar.header("📝 Alimentar Informações")
    
    # Selecionar o funcionário da loja atual para editar
    funcionarios_loja = sorted(df_loja['Nome'].dropna().unique())
    colaborador_selecionado = st.sidebar.selectbox("Selecione o Colaborador:", funcionarios_loja)
    
    if colaborador_selecionado:
        # Puxa os dados atuais do funcionário selecionado para mostrar nos campos
        dados_func = df_loja[df_loja['Nome'] == colaborador_selecionado].iloc[0]
        
        st.sidebar.markdown("---")
        
        # Campos do Supervisor
        st.sidebar.subheader("🔸 Supervisor")
        nova_obs = st.sidebar.text_area("Observação:", value=str(dados_func['Observação']) if str(dados_func['Observação']) != "-" else "")
        
        # Campos do Gerente
        st.sidebar.subheader("🔹 Gerente")
        nova_data_abertura = st.sidebar.text_input("Data Abertura:", value=str(dados_func['Data Abertura']) if str(dados_func['Data Abertura']) != "-" else "")
        novo_responsavel = st.sidebar.text_input("Responsável:", value=str(dados_func['Responsável']) if str(dados_func['Responsável']) != "-" else "")
        novo_horario_contrato = st.sidebar.text_input("Horário Contrato:", value=str(dados_func['Horário Contrato']) if str(dados_func['Horário Contrato']) != "-" else "")
        novo_sexo = st.sidebar.selectbox("Sexo:", ["-", "M", "F"], index=["-", "M", "F"].index(str(dados_func['Sexo'])) if str(dados_func['Sexo']) in ["-", "M", "F"] else 0)
        novo_motivo = st.sidebar.text_input("Motivo:", value=str(dados_func['Motivo']) if str(dados_func['Motivo']) != "-" else "")
        
        # Campos do RH
        st.sidebar.subheader("🔺 Recursos Humanos (RH)")
        novo_status_rh = st.sidebar.text_input("Status RH:", value=str(dados_func['Status RH']) if str(dados_func['Status RH']) != "-" else "")
        novo_candidato = st.sidebar.text_input("Candidato:", value=str(dados_func['Candidato']) if str(dados_func['Candidato']) != "-" else "")
        nova_data_admissao = st.sidebar.text_input("Data Admissão:", value=str(dados_func['Data Admissão']) if str(dados_func['Data Admissão']) != "-" else "")
        
        # Botão para Salvar as alterações de volta no Google Sheets
        if st.sidebar.button("💾 Salvar Alterações", use_container_width=True):
            # Localiza a linha exata no DataFrame bruto pelo nome do funcionário
            idx = df_bruto[df_bruto['Nome'] == colaborador_selecionado].index[0]
            
            # Atualiza os valores com o que foi digitado
            df_bruto.at[idx, 'Observação'] = nova_obs if nova_obs.strip() != "" else "-"
            df_bruto.at[idx, 'Data Abertura'] = nova_data_abertura if nova_data_abertura.strip() != "" else "-"
            df_bruto.at[idx, 'Responsável'] = novo_responsavel if novo_responsavel.strip() != "" else "-"
            df_bruto.at[idx, 'Horário Contrato'] = novo_horario_contrato if novo_horario_contrato.strip() != "" else "-"
            df_bruto.at[idx, 'Sexo'] = novo_sexo
            df_bruto.at[idx, 'Motivo'] = novo_motivo if novo_motivo.strip() != "" else "-"
            df_bruto.at[idx, 'Status RH'] = novo_status_rh if novo_status_rh.strip() != "" else "-"
            df_bruto.at[idx, 'Candidato'] = novo_candidato if novo_candidato.strip() != "" else "-"
            df_bruto.at[idx, 'Data Admissão'] = nova_data_admissao if nova_data_admissao.strip() != "" else "-"
            
            # Remove a coluna calculada temporária antes de enviar pro Sheets
            if 'Horario_Sistema_Real' in df_bruto.columns:
                df_bruto = df_bruto.drop(columns=['Horario_Sistema_Real'])
                
            # Grava o DataFrame atualizado de volta no Google Sheets
            conn.update(worksheet="Banco", data=df_bruto)
            st.sidebar.success("Dados salvos com sucesso no Google Sheets!")
            
            # Limpa o cache para recarregar a tela principal atualizada
            st.cache_data.clear()
            st.rerun()

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
    st.error(f"Erro na conexão ou na estrutura visual. Detalhes: {e}")
