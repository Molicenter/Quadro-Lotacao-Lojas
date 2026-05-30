import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA (Estilo Dashboard em tela cheia)
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

# 2. FUNÇÃO PARA CARREGAR E PREPARAR OS DADOS DO EXCEL
@st.cache_data
def carregar_dados():
    df = pd.read_excel("Banco QL.xlsx", sheet_name="Banco")
    
    # TRATAMENTO DO HORÁRIO DO SISTEMA (Coluna L)
    nome_coluna_horario = 'Descrição (Escala)'
    if nome_coluna_horario in df.columns:
        df['Horario_Sistema_Real'] = df[nome_coluna_horario].astype(str).str.replace('.0', '', regex=False).str.strip()
        df['Horario_Sistema_Real'] = df['Horario_Sistema_Real'].apply(lambda x: '-' if x in ['nan', 'None', ''] else x)
    else:
        df['Horario_Sistema_Real'] = "-"
        
    # FORÇANDO TODAS AS 9 COLUNAS DE DIGITAÇÃO A FICAREM ZERADAS/LIMPAS
    colunas_novas = [
        'Observação', 
        'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo', 
        'Status RH', 'Candidato', 'Data Admissão'
    ]
    
    # Aqui garantimos que elas nasçam zeradas para digitação, ignorando qualquer herança do Excel original
    for col in colunas_novas:
        df[col] = "-"
            
    return df

try:
    df_bruto = carregar_dados()

    # 3. FILTRO DE LOJA
    lojas_disponiveis = sorted(df_bruto['Loja'].dropna().unique())
    loja_selecionada = st.selectbox(
        "Selecione a Loja para Análise:", 
        lojas_disponiveis, 
        format_func=lambda x: f"Loja {int(x):02d}"
    )

    df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()

    st.markdown(f"### 🏪 Quadro de Funcionários - Loja {int(loja_selecionada):02d}")

    # 4. INDICADORES DO TOPO
    df_loja['Situação_Upper'] = df_loja['Situação'].astype(str).str.upper()
    
    ativos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('ATIVO')])
    demitidos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('DEMITIDO')])
    ferias_afastados = len(df_loja[df_loja['Situação_Upper'].str.contains('FÉRIAS|AFASTAMENTO|AFASTADO')])

    col1, col2, col3 = st.columns(3)
    col1.metric("Funcionários Ativos", ativos_qtd)
    col2.metric("Demitidos", demitidos_qtd)
    col3.metric("Férias / Afastamentos", ferias_afastados)

    st.markdown("---")

    # 5. QUEBRA EM CLUSTERS (DEPARTAMENTO E FUNÇÃO)
    st.subheader("📋 Distribuição por Setor e Cargo")
    
    departamentos = sorted(df_loja['Dept'].dropna().unique())

    for dept in departamentos:
        with st.expander(f"🏢 DEPARTAMENTO: {dept}", expanded=True):
            df_dept = df_loja[df_loja['Dept'] == dept]
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                st.markdown(f"**🔹 Cargo: {funcao}**")
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                # Monta os dados na tabela HTML
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
    st.error(f"Erro ao gerar a tabela visual. Detalhes: {e}")
