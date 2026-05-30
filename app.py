import streamlit as st
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA (Estilo Dashboard em tela cheia)
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

st.title("📊 Quadro de Lotação (QL) // Requisição")
st.markdown("---")

# 2. FUNÇÃO PARA CARREGAR OS DADOS DO EXCEL
@st.cache_data
def carregar_dados():
    # Carrega o arquivo Excel e foca especificamente na aba 'Banco'
    return pd.read_excel("Banco QL.xlsx", sheet_name="Banco")

try:
    df_bruto = carregar_dados()

    # 3. FILTRO DE LOJA (Conforme a coluna 'Loja' da sua base)
    lojas_disponiveis = sorted(df_bruto['Loja'].dropna().unique())
    loja_selecionada = st.selectbox(
        "Selecione a Loja para Análise:", 
        lojas_disponiveis, 
        format_func=lambda x: f"Loja {int(x):02d}"  # Formata como Loja 01, Loja 02...
    )

    # Filtrando a base pela loja escolhida
    df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada].copy()

    st.markdown(f"### 🏪 Quadro de Funcionários - Loja {int(loja_selecionada):02d}")

    # 4. INDICADORES DO TOPO (Gerais da Loja selecionada)
    # Padroniza a coluna Situação para maiúsculo para evitar erros de digitação
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
    
    # Ordena os departamentos (AÇOUGUE, CONFEITARIA, DEPOSITO...)
    departamentos = sorted(df_loja['Dept'].dropna().unique())

    for dept in departamentos:
        # Cria um bloco expansível para cada Departamento
        with st.expander(f"🏢 DEPARTAMENTO: {dept}", expanded=True):
            df_dept = df_loja[df_loja['Dept'] == dept]
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                st.markdown(f"**🔹 Cargo: {funcao}**")
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                # Monta a tabela com as colunas na ordem visual que você precisa
                tabela_exibicao = df_funcao[['Situação', 'Nome', 'Escala']].copy()
                tabela_exibicao.columns = ['Status', 'Nome do Colaborador', 'Horário Sistema']
                
                # Exibe a tabela cheia de funcionários para aquele cargo específico
                st.dataframe(tabela_exibicao, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Aguardando a leitura do arquivo Excel. Detalhes: {e}")
    st.info("Dica: Certifique-se de que o arquivo no GitHub se chama exatamente 'Banco QL.xlsx'.")
