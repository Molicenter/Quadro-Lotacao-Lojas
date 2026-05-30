import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

st.title("📊 Quadro de Lotação (QL) // Requisição")
st.markdown("---")

# 2. FUNÇÃO PARA CARREGAR OS DADOS DO EXCEL
@st.cache_data
def carregar_dados():
    df = pd.read_excel("Banco QL.xlsx", sheet_name="Banco")
    
    # Vamos descobrir qual é o nome exato da coluna de horários no seu Excel.
    # Na imagem ela aparece como 'Escala'. Vamos forçar ela a virar texto limpo.
    coluna_horario = None
    for col in ['Escala', 'ESCALA', 'Horário', 'Horario']:
        if col in df.columns:
            coluna_horario = col
            break
            
    if coluna_horario:
        df['Horario_Tratado'] = df[coluna_horario].astype(str).str.replace('.0', '', regex=False).str.strip()
        df['Horario_Tratado'] = df['Horario_Tratado'].apply(lambda x: '-' if x in ['nan', 'None', ''] else x)
    else:
        # Se não achar a coluna por nome, cria uma coluna vazia temporária para não quebrar
        df['Horario_Tratado'] = "-"
        
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
                
                # Monta a tabela final usando a coluna de horário que localizamos e tratamos
                tabela_exibicao = df_funcao[['Situação', 'Nome', 'Horario_Tratado']].copy()
                tabela_exibicao.columns = ['Status', 'Nome do Colaborador', 'Horário Sistema']
                
                # Exibe a tabela sem o aviso de código legado do Streamlit
                st.dataframe(tabela_exibicao, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro ao processar as colunas do Excel. Detalhes: {e}")
