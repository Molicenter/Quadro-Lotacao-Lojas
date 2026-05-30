import streamlit as st
import pandas as pd

# Configuração da página para usar a tela inteira (Estilo Dashboard)
st.set_page_config(page_title="Molicenter - Quadro de Lotação", layout="wide")

st.title("📊 Quadro de Lotação (QL) // Requisição")
st.markdown("---")

# 1. FUNÇÃO PARA CARREGAR OS DADOS (Substitua depois pelo link do seu Sheets/CSV)
@st.cache_data
def carregar_dados():
    # Aqui estamos simulando a leitura da estrutura da sua segunda imagem
    # Quando subir o arquivo real, basta usar: pd.read_excel("Banco QL.xlsx") ou via Google Sheets
    try:
        df = pd.read_excel("Banco QL.xlsx")  # ou pd.read_csv
        return df
    except:
        # Dados fictícios apenas para o código rodar de primeira se não achar o arquivo
        dados_teste = {
            'Loja': [1, 1, 1, 1, 2, 2],
            'Dept': ['AÇOUGUE', 'AÇOUGUE', 'CONFEITARIA', 'DEPOSITO', 'AÇOUGUE', 'DEPOSITO'],
            'Função': ['AÇOUGUEIRO', 'DESOSSADOR', 'ENCARREGADO', 'CONFERENTE', 'AÇOUGUEIRO', 'AUXILIAR'],
            'Situação': ['Ativos', 'Férias', 'Ativos', 'Demitido', 'Ativos', 'Afastamento'],
            'Nome': ['SIDNEI PADILHA', 'DAIANE SANTOS', 'NATALY KAROLINE', 'ALEXSANDRO GONÇALVES', 'BRUNO SILVA', 'TIAGO BRITO'],
            'Escala': ['ART 62 CLT', '12:00-15:00', '08:00-17:00', '07:00-16:00', 'ART 62 CLT', '07:30-17:00']
        }
        return pd.DataFrame(dados_teste)

df_bruto = carregar_dados()

# 2. FILTRO DE LOJA (Conforme a primeira coluna da sua segunda imagem)
lojas_disponiveis = sorted(df_bruto['Loja'].unique())
loja_selecionada = st.selectbox("Selecione a Loja para Análise:", lojas_disponiveis, format_func=lambda x: f"Loja 0{x}" if x < 10 else f"Loja {x}")

# Filtrando a base pela loja escolhida
df_loja = df_bruto[df_bruto['Loja'] == loja_selecionada]

st.markdown(f"### 🏪 Visualizando: Loja {loja_selecionada}")

# 3. RESUMO DOS INDICADORES DE TOPO (Igual aos cartões azuis da sua planilha)
ativos_qtd = len(df_loja[df_loja['Situação'] == 'Ativos'])
demitidos_qtd = len(df_loja[df_loja['Situação'] == 'Demitido'])
afastados_qtd = len(df_loja[df_loja['Situação'].isin(['Afastamento', 'Afastado'])])

col1, col2, col3 = st.columns(3)
col1.metric("Funcionários Ativos", ativos_qtd)
col2.metric("Demitidos", demitidos_qtd)
col3.metric("Afastados / Férias", afastados_qtd)

st.markdown("---")

# 4. DIVISÃO EM CLUSTERS (DEPARTAMENTO E FUNÇÃO)
st.subheader("📋 Distribuição por Setor e Cargo")

# Pegar a lista de departamentos únicos daquela loja
departamentos = df_loja['Dept'].unique()

for dept in departamentos:
    with st.expander(f"🏢 DEPARTAMENTO: {dept}", expanded=True):
        df_dept = df_loja[df_loja['Dept'] == dept]
        
        # Listar as funções existentes dentro desse departamento
        funcoes = df_dept['Função'].unique()
        
        for funcao in funcoes:
            st.markdown(f"**🔹 Cargo: {funcao}**")
            df_funcao = df_dept[df_dept['Função'] == funcao]
            
            # Montando a tabela organizada com as informações críticas da primeira imagem
            tabela_exibicao = df_funcao[['Situação', 'Nome', 'Escala']].copy()
            tabela_exibicao.columns = ['Status', 'Nome do Colaborador', 'Horário / Escala']
            
            # Exibe a tabela formatada de forma limpa na tela
            st.dataframe(tabela_exibicao, use_container_width=True, hide_index=True)
