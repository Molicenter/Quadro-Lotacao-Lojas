import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA (Estilo Dashboard em tela cheia)
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

st.title("📊 Quadro de Lotação (QL) // Requisição")
st.markdown("---")

# 2. FUNÇÃO PARA CARREGAR E PREPARAR OS DADOS DO EXCEL
@st.cache_data
def carregar_dados():
    df = pd.read_excel("Banco QL.xlsx", sheet_name="Banco")
    
    # TRATAMENTO DO HORÁRIO DO SISTEMA (Coluna L - 'Descrição (Escala)')
    nome_coluna_horario = 'Descrição (Escala)'
    if nome_coluna_horario in df.columns:
        df['Horario_Sistema_Real'] = df[nome_coluna_horario].astype(str).str.replace('.0', '', regex=False).str.strip()
        df['Horario_Sistema_Real'] = df['Horario_Sistema_Real'].apply(lambda x: '-' if x in ['nan', 'None', ''] else x)
    else:
        df['Horario_Sistema_Real'] = "-"
        
    # CRIAÇÃO/VERIFICAÇÃO DAS 9 COLUNAS DE DIGITAÇÃO
    colunas_novas = [
        'Observação', 
        'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo', 
        'Status RH', 'Candidato', 'Data Admissão'
    ]
    
    for col in colunas_novas:
        if col not in df.columns:
            if col == 'Status RH' and 'Situação.1' in df.columns:
                df['Status RH'] = df['Situação.1'].fillna('-')
            else:
                df[col] = "-"
        else:
            df[col] = df[col].fillna("-").astype(str).str.replace('.0', '', regex=False)
            
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
                
                # Criando o DataFrame base com as colunas na ordem certa
                tabela_base = df_funcao[[
                    'Situação', 'Nome', 'Horario_Sistema_Real',
                    'Observação',
                    'Data Abertura', 'Responsável', 'Horário Contrato', 'Sexo', 'Motivo',
                    'Status RH', 'Candidato', 'Data Admissão'
                ]].copy()
                
                # 📊 DEFINIÇÃO CLARA DOS DOIS NÍVEIS DE CABEÇALHO
                colunas_multinivel = [
                    ('DONO: ANALISTA', 'Status'),
                    ('DONO: ANALISTA', 'Nome do Colaborador'),
                    ('DONO: ANALISTA', 'Horário Sistema'),
                    ('DONO: SUPERVISOR', 'Observação'),
                    ('DONO: GERENTE', 'Data Abertura'),
                    ('DONO: GERENTE', 'Responsável'),
                    ('DONO: GERENTE', 'Horário Contrato'),
                    ('DONO: GERENTE', 'Sexo'),
                    ('DONO: GERENTE', 'Motivo'),
                    ('DONO: RH', 'Status RH'),
                    ('DONO: RH', 'Candidato'),
                    ('DONO: RH', 'Data Admissão')
                ]
                
                tabela_base.columns = pd.MultiIndex.from_tuples(colunas_multinivel)
                
                # 🔥 O PULO DO GATO: Usamos o .style para forçar o Streamlit a renderizar os dois níveis de títulos na tela
                tabela_estilizada = tabela_base.style.set_table_styles([
                    {'selector': 'th.col_heading.level0', 'props': [('background-color', '#1f77b4'), ('color', 'white'), ('font-weight', 'bold'), ('text-align', 'center')]}
                ])
                
                # Exibe a tabela estruturada garantindo que o primeiro nível apareça
                st.dataframe(tabela_estilizada, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao estruturar o cabeçalho multinível. Detalhes: {e}")
