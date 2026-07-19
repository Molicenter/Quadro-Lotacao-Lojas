import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os
import time
import unicodedata
import plotly.graph_objects as go
from supabase import create_client, Client # <-- NOVA IMPORTAÇÃO
from ql_orcado import (  # <-- VISÃO QL ORÇADO (ORGANOGRAMA)
    renderizar_visao_ql_orcado,
    carregar_mapas_orcado,
    obter_orcado_dept,
    obter_orcado_funcao,
    badge_orcado,
)

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

# --- INICIALIZAÇÃO DO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# Função auxiliar para higienizar strings nulas vindas do Pandas/Supabase
def limpar_campo(valor, padrao="-"):
    if pd.isna(valor):
        return padrao
    v_str = str(valor).strip()
    if v_str.lower() in ["nan", "none", "null", "nat", "<na>", ""]:
        return padrao
    return v_str

# Funções para gerar os "Badges" (Pílulas) de Status
def obter_badge_status(status):
    status_upper = str(status).strip().upper()
    if "ATIVO" in status_upper:
        return f'<span class="badge badge-ativo">{status}</span>'
    elif "FÉRIAS" in status_upper or "FERIAS" in status_upper:
        return f'<span class="badge badge-ferias">{status}</span>'
    elif "AFASTAMENTO" in status_upper or "AFASTADO" in status_upper:
        return f'<span class="badge badge-afastado">{status}</span>'
    elif "DEMITIDO" in status_upper or status_upper in ["NAN", "NONE", ""]:
        return f'<span class="badge badge-demitido">Demitido</span>'
    return f'<span class="badge" style="background-color:#14507F; color:white;">{status}</span>'

def obter_badge_rh(status):
    status_str = str(status).strip()
    if status_str in ["nan", "None", "", "-", "null"]:
        return "-"
    return f'<span class="badge badge-rh">{status_str}</span>'

def formatar_data_br(valor):
    val_str = str(valor).strip()
    if val_str.lower() in ["nan", "none", "", "-", "0", "null"]:
        return "-"
    try:
        if "T" in val_str:
            val_str = val_str.split("T")[0]
            
        # O parâmetro dayfirst=True força o Pandas a ler o primeiro número como Dia (Padrão BR)
        dt = pd.to_datetime(val_str, dayfirst=True)
        
        return dt.strftime("%d/%m/%Y")
    except:
        return val_str

# =========================================================
# 🎓 RETENÇÃO DE ADMISSÕES NO QUADRO OPERACIONAL
# Depois de admitido, o lançamento continua no quadro por, no máximo,
# DIAS_RETENCAO_ADMISSAO dias. Passado esse prazo ele sai do quadro do
# dia a dia (sem ser apagado do banco): a admissão continua contando no
# Relatório de Efetividade e no card "Admitidos".
# =========================================================
DIAS_RETENCAO_ADMISSAO = 7

def _parse_data_admissao(valor):
    """Converte uma data (texto DD/MM/AAAA, ISO, com hora, ou datetime/Timestamp do Excel)
    em date. None se vazia/inválida. Usada para Data Admissão e Data Abertura no relatório."""
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.date()
    if isinstance(valor, date):
        return valor
    val = str(valor).strip()
    if val.lower() in ["", "-", "nan", "none", "null", "nat", "0"]:
        return None
    base = val.replace("T", " ").split(" ")[0]  # descarta a hora, se houver
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(base, fmt).date()
        except Exception:
            continue
    try:  # fallback robusto (dayfirst = padrão BR)
        dt = pd.to_datetime(val, dayfirst=True, errors="coerce")
        if pd.notna(dt):
            return dt.date()
    except Exception:
        pass
    return None

def _norm_nome(s):
    """Normaliza nome para comparação: sem acento, maiúsculo, espaços colapsados.
    Faz 'Lucas Custódio  da Silva' == 'LUCAS CUSTODIO DA SILVA'."""
    s = str(s or "").strip().upper()
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return " ".join(s.split())

def arquivar_admissoes_antigas(supabase):
    """Move para historico_ql e REMOVE do banco_ql os lançamentos cuja Data Admissão
    já passou de DIAS_RETENCAO_ADMISSAO dias. Assim o quadro operacional e o card
    'Admitidos' ficam só com admissões recentes, e o banco_ql não cresce
    indefinidamente. O histórico preserva tudo. Retorna a qtde arquivada."""
    try:
        resp = supabase.table("banco_ql").select("*").execute()
        registros = resp.data or []
    except Exception as e:
        print(f"[Arquivamento] Erro ao ler banco_ql: {e}")
        return 0

    limite = date.today() - timedelta(days=DIAS_RETENCAO_ADMISSAO)
    arquivados = 0
    for registro in registros:
        data_ad = _parse_data_admissao(registro.get("Data Admissão"))
        # mantém: sem admissão, admissão recente (<= 7 dias) ou admissão futura (previsão)
        if data_ad is None or data_ad >= limite:
            continue
        loja_reg = registro.get("Loja")
        nome_reg = registro.get("Nome")
        log = {
            "Loja": loja_reg, "Nome": nome_reg,
            "Dept": registro.get("Dept"), "Função": registro.get("Função"),
            "Situação": registro.get("Situação"),
            "Observação": (f"[ARQUIVADO AUTOMATICAMENTE - {DIAS_RETENCAO_ADMISSAO} dias "
                           f"apos admissao em {data_ad.strftime('%d/%m/%Y')}]"),
            "Data Abertura": registro.get("Data Abertura"),
            "Responsável": registro.get("Responsável"),
            "Horário Contrato": registro.get("Horário Contrato"),
            "Sexo": registro.get("Sexo"), "Motivo": registro.get("Motivo"),
            "Status RH": registro.get("Status RH"),
            "Candidato": registro.get("Candidato"),
            "Data Admissão": registro.get("Data Admissão"),
            "Usuario": "SISTEMA_ARQUIVAMENTO",
        }
        try:
            # 1º guarda no histórico, só então remove do banco principal
            supabase.table("historico_ql").insert(log).execute()
            supabase.table("banco_ql").delete().eq("Loja", loja_reg).eq("Nome", nome_reg).execute()
            arquivados += 1
        except Exception as e:
            print(f"[Arquivamento] Erro em {nome_reg}/{loja_reg}: {e}")

    if arquivados:
        print(f"[Arquivamento] {arquivados} lançamento(s) movido(s) para historico_ql.")
    return arquivados

def _ler_tabela_completa(supabase, tabela):
    """Lê TODAS as linhas de uma tabela do Supabase, paginando de 1000 em 1000
    (o Supabase limita cada requisição a 1000 linhas por padrão)."""
    todas = []
    passo = 1000
    inicio = 0
    while True:
        try:
            lote = supabase.table(tabela).select("*").range(inicio, inicio + passo - 1).execute().data or []
        except Exception as e:
            print(f"[Leitura] Erro ao ler {tabela} (range {inicio}): {e}")
            break
        todas.extend(lote)
        if len(lote) < passo:
            break
        inicio += passo
    return todas

def _loja_int_val(v):
    """Converte um valor de Loja (texto/float) em int; 0 se inválido."""
    try:
        return int(float(str(v)))
    except Exception:
        return 0

# =========================================================================
# 🗂️ LEDGER DE ADMISSÕES (histórico acumulado do roster)
# O Banco QL.xlsx é uma FOTO do quadro atual: quem foi admitido e depois saiu
# some do arquivo. Este ledger acumula, a cada importação, todos os admitidos
# que aparecem no Excel — assim, mesmo que a pessoa saia depois, o registro
# de que ela foi admitida naquele período NÃO se perde.
# Tabela no Supabase: admissoes_registradas (crie com o DDL que passei no chat).
# =========================================================================
def capturar_admissoes_no_ledger(supabase, df_excel):
    """Acumula no admissoes_registradas os admitidos do roster atual (Banco QL.xlsx),
    inserindo só quem ainda não está lá (dedup por nome + data + loja). Retorna qtde nova."""
    col_adm = None
    for c in df_excel.columns:
        if _norm_nome(c) == 'ADMISSAO':
            col_adm = c
            break
    if col_adm is None:
        return 0

    existentes_rows = _ler_tabela_completa(supabase, "admissoes_registradas")
    if existentes_rows is None:
        return 0  # tabela ainda não existe -> ignora silenciosamente
    existentes = set()
    for r in existentes_rows:
        existentes.add((r.get('nome_norm'), str(r.get('data_admissao_date')), _loja_int_val(r.get('Loja'))))

    novos = []
    for _, linha in df_excel.iterrows():
        loja = _loja_int_val(linha.get('Loja'))
        if loja <= 0:
            continue
        d = _parse_data_admissao(linha.get(col_adm))
        if d is None:
            continue
        nome = str(linha.get('Nome', '')).strip()
        nn = _norm_nome(nome)
        if not nn:
            continue
        chave = (nn, d.isoformat(), loja)
        if chave in existentes:
            continue
        existentes.add(chave)
        novos.append({
            "Loja": loja, "Nome": nome, "nome_norm": nn,
            "Data Admissão": d.strftime('%d/%m/%Y'), "data_admissao_date": d.isoformat(),
            "Dept": str(linha.get('Dept', '')), "Funcao": str(linha.get('Função', '')),
            "Situacao": str(linha.get('Situação', '')),
        })

    inseridos = 0
    for i in range(0, len(novos), 500):
        try:
            supabase.table("admissoes_registradas").insert(novos[i:i + 500]).execute()
            inseridos += len(novos[i:i + 500])
        except Exception as e:
            print(f"[Ledger] Erro ao inserir lote: {e}")
            break
    if inseridos:
        print(f"[Ledger] {inseridos} admissão(ões) nova(s) registrada(s).")
    return inseridos

def combinar_banco_e_historico(supabase):
    """Une banco_ql (registros vivos) + historico_ql (log/arquivados) e deduplica por
    (Loja, Nome), mantendo a versão mais recente de cada requisição. Usado pelo
    Relatório de Efetividade para contar aberturas/admissões inclusive as já arquivadas."""
    hist = _ler_tabela_completa(supabase, "historico_ql")
    banco = _ler_tabela_completa(supabase, "banco_ql")

    # Descobre a coluna de ordem temporal disponível no histórico (pra pegar a versão mais nova)
    campo_ordem = None
    for cand in ("created_at", "criado_em", "id"):
        if any(cand in r for r in hist):
            campo_ordem = cand
            break

    def _ordem(r):
        v = r.get(campo_ordem) if campo_ordem else None
        if v is None:
            return ""
        s = str(v)
        return s.zfill(20) if s.isdigit() else s  # id numérico ordena como número

    hist_ordenado = sorted(hist, key=_ordem) if campo_ordem else hist

    def _chave(r):
        try:
            loja = int(float(str(r.get('Loja', 0))))
        except Exception:
            loja = 0
        return (loja, str(r.get('Nome', '')).strip().upper())

    combinado = {}
    for r in hist_ordenado:   # histórico do mais antigo -> mais novo
        combinado[_chave(r)] = r
    for r in banco:           # banco vivo prevalece sobre o histórico
        combinado[_chave(r)] = r
    return list(combinado.values()), hist, banco

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

# Perfis com edição TOTAL: podem alterar qualquer célula, salvar com campos em
# branco e zerar/reabrir linhas. "analista" atua como Administrador do sistema.
PERFIS_EDICAO_TOTAL = ["analista", "rh"]

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
    "SG-SB 11:30-14:30 16:30-20:50", "SG-SB 11:30-15:30 17:30-20:50", "SG-SB 12:00-15:00 17:00-21:20", "SG-SB 12:30-15:00 17:00-21:50"
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

if "filtro_cards" not in st.session_state:
    st.session_state["filtro_cards"] = "TODOS"

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
                    st.markdown("<p style='color: #64748B; font-size: 15px; margin: 0; padding-top: 4px;'>QL - Quadro de Lotação</p>", unsafe_allow_html=True)
                with col_logo:
                    st.image("passaro_logo.png", width=90)
            else:
                st.markdown("<h2 style='margin: 0; padding: 0; line-height: 1;'>Molicenter QL</h2>", unsafe_allow_html=True)
                st.markdown("<p style='color: #64748B; font-size: 15px; margin: 0; padding-top: 4px;'>QL - Quadro de Lotação</p>", unsafe_allow_html=True)
            
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
    .ql-table { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 12px; color: #22303C; border: none !important; }
    .ql-table th { padding: 8px 10px; font-size: 12px !important; font-weight: 600; }
    .ql-table td { border-bottom: 1px solid #D5E0EA; border-left: none; border-right: none; padding: 10px 8px; text-align: left; white-space: nowrap; vertical-align: middle; }
    .ql-table tr:nth-child(even) { background-color: #F2F6FA; }
    .ql-table tr:nth-child(odd) { background-color: #FFFFFF; }
    .ql-table tbody tr:hover { background-color: #DCEBF7 !important; transition: 0.2s; }
    .celula-loja { text-align: center !important; font-weight: bold !important; color: #0B3D63 !important; }
    
    /* === ESTILOS EXCLUSIVOS DA TABELA DE RESUMO (RELATÓRIO) === */
    .tabela-resumo { width: 100%; border-collapse: collapse; font-family: sans-serif; font-size: 13px; color: #22303C; }
    .tabela-resumo th { padding: 10px; background-color: #DCEBF7; color: #22303C; border-bottom: 2px solid #C4D4E0; text-align: center !important; font-weight: 600; }
    .tabela-resumo td { padding: 10px; border-bottom: 1px solid #D5E0EA; text-align: center !important; vertical-align: middle; }
    .tabela-resumo tr:nth-child(even) { background-color: #F2F6FA; }
    .tabela-resumo tr:nth-child(odd) { background-color: #FFFFFF; }
    .tabela-resumo tbody tr:hover { background-color: #DCEBF7 !important; transition: 0.2s; }
    /* ================================================================ */
    
    div[data-testid="stExpander"] { margin-bottom: 6px !important; border: 1px solid #D5E0EA !important; border-radius: 6px !important; background-color: transparent !important; }
    div[data-testid="stExpander"] summary { background-color: #0B3D63 !important; border-radius: 5px 5px 5px 5px !important; padding: 10px 15px !important; }
    div[data-testid="stExpander"] summary p, div[data-testid="stExpander"] summary span, div[data-testid="stExpander"] summary label { color: #ffffff !important; font-weight: 600 !important; font-size: 13px !important; }
    div[data-testid="stExpander"] summary svg { color: #ffffff !important; fill: #ffffff !important; }
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] { background-color: transparent !important; padding-top: 5px !important; }
    </style>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Sair do Sistema"):
    st.session_state["logado"] = False
    st.rerun()

# =========================================================
# 📊 4. CARGA DE DADOS HÍBRIDA (Excel local + Supabase)
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
    df['Existe_No_Excel'] = True  # tudo que vem do Banco QL.xlsx existe no Excel

    try:
        # --- SUPABASE: Buscar Dados ---
        resp = supabase.table("banco_ql").select("*").execute()
        dados_sheets = resp.data
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
                
                # PRIORIDADE: 1º Excel -> 2º Supabase -> 3º Demitido
                status_excel = str(df.at[idx, 'Situação']).strip()
                
                # Se o Excel estiver vazio ou inválido, puxa do Banco
                if status_excel.lower() in ["nan", "none", "null", "", "-"]:
                    sit_val = limpar_campo(registro.get('Situação'), "Demitido")
                    if sit_val == "-":
                        sit_val = "Demitido"
                    df.at[idx, 'Situação'] = sit_val
                # Se o Excel já tiver algo (ex: "Ativos"), ele ignora o banco e mantém o do Excel intacto.
                
                # Tratamento preventivo de strings textuais 'nan' nas colunas do banco
                df.at[idx, 'Observação'] = limpar_campo(registro.get('Observação'))
                df.at[idx, 'Data Abertura'] = formatar_data_br(registro.get('Data Abertura'))
                df.at[idx, 'Responsável'] = limpar_campo(registro.get('Responsável'))
                df.at[idx, 'Horário Contrato'] = limpar_campo(registro.get('Horário Contrato'))
                
                sigla_sexo = limpar_campo(registro.get('Sexo'))
                df.at[idx, 'Sexo'] = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                
                df.at[idx, 'Motivo'] = limpar_campo(registro.get('Motivo'))
                df.at[idx, 'Status RH'] = limpar_campo(registro.get('Status RH'))
                df.at[idx, 'Candidato'] = limpar_campo(registro.get('Candidato'))
                df.at[idx, 'Data Admissão'] = formatar_data_br(registro.get('Data Admissão'))
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
                data_ad_checar = formatar_data_br(registro.get('Data Admissão'))
                
                sigla_sexo = limpar_campo(registro.get('Sexo'))
                sexo_exibicao = MAPA_SIGLA_SEXO.get(sigla_sexo, sigla_sexo)
                
                dept_final = limpar_campo(registro.get('Dept'), 'HISTÓRICO / EX-COLABORADORES')
                if dept_final == "-": dept_final = 'HISTÓRICO / EX-COLABORADORES'
                
                funcao_final = limpar_campo(registro.get('Função'), 'Sem Vínculo Atual')
                if funcao_final == "-": funcao_final = 'Sem Vínculo Atual'
                
                situacao_final = limpar_campo(registro.get('Situação'), 'Demitido')
                if situacao_final == "-": situacao_final = 'Demitido'
                
                linha_manual = {
                    'Loja': loja_reg, 'Nome': nome_func, 'Situação': situacao_final, 
                    'Dept': dept_final, 'Função': funcao_final, 'Horario_Sistema_Real': '-',
                    'Observação': limpar_campo(registro.get('Observação')),
                    'Data Abertura': formatar_data_br(registro.get('Data Abertura')),
                    'Responsável': limpar_campo(registro.get('Responsável')),
                    'Horário Contrato': limpar_campo(registro.get('Horário Contrato')),
                    'Sexo': sexo_exibicao, 'Motivo': limpar_campo(registro.get('Motivo')),
                    'Status RH': limpar_campo(registro.get('Status RH')),
                    'Candidato': limpar_campo(registro.get('Candidato')),
                    'Data Admissão': data_ad_checar, 'Possui_Alteracao_Sheets': True,
                    'Existe_No_Excel': False
                }
                linhas_novas_manuais.append(linha_manual)
        
        if len(linhas_novas_manuais) > 0:
            df_manuais = pd.DataFrame(linhas_novas_manuais)
            df = pd.concat([df, df_manuais], ignore_index=True)
    except Exception as e:
        print(f"Erro Supabase Fetch: {e}")

    # --- Marcação de admitidos (não destrutiva) ---
    # Tem_Admissao   -> alguém já foi admitido nessa linha (Data Admissão preenchida)
    # Admitido_Arquivar -> admitido há mais de DIAS_RETENCAO_ADMISSAO dias
    if 'Existe_No_Excel' not in df.columns:
        df['Existe_No_Excel'] = True
    hoje_ref = date.today()
    limite_admissao = hoje_ref - timedelta(days=DIAS_RETENCAO_ADMISSAO)
    datas_ad = df['Data Admissão'].apply(_parse_data_admissao)
    df['Tem_Admissao'] = datas_ad.notna()
    # Arquivar: admitido há MAIS de DIAS_RETENCAO_ADMISSAO dias (sai do sistema)
    df['Admitido_Arquivar'] = datas_ad.apply(
        lambda d: (d is not None) and (d < limite_admissao)
    )
    # Recente: admitido dentro dos últimos DIAS_RETENCAO_ADMISSAO dias (aparece no card)
    df['Admitido_Recente'] = datas_ad.apply(
        lambda d: (d is not None) and (limite_admissao <= d <= hoje_ref)
    )

    return df

try:
    # Arquivamento automático: admissões com +7 dias vão pro histórico e saem do banco_ql.
    # Roda 1x por dia por sessão (após a 1ª execução do dia, não há mais o que arquivar).
    if st.session_state.get("arquivamento_data") != date.today():
        arquivar_admissoes_antigas(supabase)
        st.session_state["arquivamento_data"] = date.today()
        st.cache_data.clear()  # garante recarregar o quadro já sem os arquivados

    df_bruto = carregar_dados_completos()

    # Ledger de admissões: acumula os admitidos do roster atual (1x por dia por sessão),
    # pra não perder quem foi admitido e depois saiu do Banco QL.xlsx.
    if st.session_state.get("ledger_data") != date.today():
        capturar_admissoes_no_ledger(supabase, df_bruto)
        st.session_state["ledger_data"] = date.today()

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
            <div style="background-color: #DCEBF7; padding: 12px; border-radius: 6px; border: 1px solid #C4D4E0; margin-bottom: 15px;">
                <span style="color: #0B3D63; font-weight: bold;">🟢 Usuários online no Sistema (Últimos 10 min):</span>
                <span style="color: #22303C; margin-left: 8px;">{', '.join([f'<b>{u}</b>' for u in usuarios_online])}</span>
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
            dept_final = str(dados_func['Dept']).strip()
            funcao_final = str(dados_func['Função']).strip()
            
            # Sanitiza a situação para que valores em branco ou textuais sujos fiquem como Demitido por padrão
            sit_temp = str(dados_func['Situação']).strip()
            if sit_temp.lower() in ["nan", "none", "null", ""]:
                situacao_final = "Demitido"
            else:
                situacao_final = sit_temp
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
            
            # Função utilitária para capturar e limpar o valor padrão antes de injetar nos inputs do formulário lateral
            def obter_val_default(campo, v_padrao=""):
                if dados_func is None:
                    return v_padrao
                val = str(dados_func[campo]).strip()
                if val.lower() in ["nan", "none", "null", "-", ""]:
                    return v_padrao
                return val

            st.markdown("🔸 **Supervisor**")
            val_obs_default = obter_val_default('Observação', "")
            if perfil in ["analista", "rh", "supervisor"]:
                nova_obs = st.text_area("Observação:", value=val_obs_default)
            else:
                st.text_input("Observação:", value=val_obs_default if val_obs_default else "-", disabled=True)
                nova_obs = val_obs_default if val_obs_default else "-"
            
            st.markdown("🔹 **Gerente**")
            if perfil in ["analista", "rh", "supervisor", "gerente"]:
                data_ab_atual = obter_val_default('Data Abertura', "-")
                try:
                    data_ab_default = datetime.strptime(data_ab_atual, "%d/%m/%Y").date() if data_ab_atual != "-" else date.today()
                except:
                    data_ab_default = date.today()
                nova_data_ab_col = st.date_input("Data Abertura:", value=data_ab_default, format="DD/MM/YYYY")
                nova_data_abertura = nova_data_ab_col.strftime("%d/%m/%Y")
                
                val_resp_default = obter_val_default('Responsável', "")
                novo_responsavel = st.text_input("Responsável:", value=val_resp_default)
                
                val_horario_default = obter_val_default('Horário Contrato', "-")
                idx_horario = OPCOES_HORARIO.index(val_horario_default) if val_horario_default in OPCOES_HORARIO else 0
                novo_horario_contrato = st.selectbox("Horário Contrato:", OPCOES_HORARIO, index=idx_horario)
                
                sexo_exibido_atual = obter_val_default('Sexo', "-")
                idx_sexo = OPCOES_SEXO.index(sexo_exibido_atual) if sexo_exibido_atual in OPCOES_SEXO else 0
                texto_sexo_selecionado = st.selectbox("Sexo:", OPCOES_SEXO, index=idx_sexo)
                novo_sexo = MAPA_SEXO_SIGLA.get(texto_sexo_selecionado, "-")
                
                motivo_atual = obter_val_default('Motivo', "-")
                idx_motivo = OPCOES_MOTIVO.index(motivo_atual) if motivo_atual in OPCOES_MOTIVO else 0
                novo_motivo = st.selectbox("Motivo:", OPCOES_MOTIVO, index=idx_motivo)
            else:
                nova_data_abertura = st.text_input("Data Abertura:", value=obter_val_default('Data Abertura', "-"), disabled=True)
                novo_responsavel = st.text_input("Responsável:", value=obter_val_default('Responsável', "-"), disabled=True)
                novo_horario_contrato = st.text_input("Horário Contrato:", value=obter_val_default('Horário Contrato', "-"), disabled=True)
                novo_sexo_exibido = st.text_input("Sexo:", value=obter_val_default('Sexo', "-"), disabled=True)
                novo_sexo = MAPA_SEXO_SIGLA.get(novo_sexo_exibido, "-")
                novo_motivo = st.text_input("Motivo:", value=obter_val_default('Motivo', "-"), disabled=True)
            
            st.markdown("🔺 **Recursos Humanos (RH)**")
            if perfil in ["analista", "rh"]:
                status_atual = obter_val_default('Status RH', "-")
                idx_status = OPCOES_STATUS_RH.index(status_atual) if status_atual in OPCOES_STATUS_RH else 0
                novo_status_rh = st.selectbox("Status RH:", OPCOES_STATUS_RH, index=idx_status)
                
                val_cand_default = obter_val_default('Candidato', "")
                novo_candidato = st.text_input("Candidato:", value=val_cand_default)
                
                data_ad_atual = obter_val_default('Data Admissão', "-")
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
                novo_status_rh = st.text_input("Status RH:", value=obter_val_default('Status RH', "-"), disabled=True)
                novo_candidato = st.text_input("Candidato:", value=obter_val_default('Candidato', "-"), disabled=True)
                nova_data_admissao = st.text_input("Data Admissão:", value=obter_val_default('Data Admissão', "-"), disabled=True)
            
            submit_button = st.form_submit_button("💾 Salvar Alterações", use_container_width=True, type="primary")

            # 🧹 Ação exclusiva de Administrador (Analista) e RH:
            # zera toda a digitação e devolve a linha ao estado "em aberto".
            zerar_button = False
            if perfil in PERFIS_EDICAO_TOTAL:
                st.markdown(
                    "<div style='font-size:11px; color:#64748B; margin-top:6px; line-height:1.3;'>"
                    ""
                    ""
                    "</div>", unsafe_allow_html=True
                )
                zerar_button = st.form_submit_button(
                    "🧹 Zerar Linha / Deixar em Aberto", use_container_width=True
                )

        # ==============================================================
        # 🧹 AÇÃO: ZERAR LINHA / DEIXAR EM ABERTO (Admin/Analista e RH)
        # ==============================================================
        if zerar_button:
            if perfil not in PERFIS_EDICAO_TOTAL:
                st.sidebar.error("Apenas Administrador/Analista e RH podem zerar registros.")
            elif not colaborador_final:
                st.sidebar.error("Selecione um colaborador para zerar a linha.")
            else:
                with st.spinner("⏳ Removendo digitação e reabrindo a linha..."):
                    loja_salvamento = int(dados_func['Loja']) if (dados_func is not None) else (int(loja_selecionada) if isinstance(loja_selecionada, int) else 1)
                    try:
                        # Log de auditoria no histórico ANTES de remover
                        log_zerar = {
                            "Loja": loja_salvamento, "Nome": colaborador_final,
                            "Dept": dept_final, "Função": funcao_final, "Situação": situacao_final,
                            "Observação": f"[LINHA ZERADA / REABERTA por {st.session_state['usuario']}]",
                            "Data Abertura": "-", "Responsável": "-", "Horário Contrato": "-",
                            "Sexo": "-", "Motivo": "-", "Status RH": "-", "Candidato": "-",
                            "Data Admissão": "-", "Usuario": st.session_state["usuario"]
                        }
                        supabase.table("historico_ql").insert(log_zerar).execute()

                        # Remove o registro do banco principal -> a linha volta a ficar em aberto
                        supabase.table("banco_ql").delete().eq("Loja", loja_salvamento).eq("Nome", colaborador_final).execute()

                        st.sidebar.success("✅ Linha zerada! O registro voltou ao estado em aberto.")
                        st.cache_data.clear()
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Erro ao zerar registro: {e}")

        # ==============================================================
        # 🔒 VALIDAÇÃO DE CAMPOS E SALVAMENTO NO SUPABASE
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

            # Administrador/Analista e RH têm liberdade total: podem salvar com
            # campos do Gerente em branco (ex.: para reabrir/limpar uma linha).
            eh_perfil_total = perfil in PERFIS_EDICAO_TOTAL

            if tipo_registro == "Cadastrar Novo / Não Listado" and not colaborador_final:
                st.sidebar.error("Erro: O nome do colaborador não pode ficar em branco.")
            elif len(campos_faltantes) > 0 and not eh_perfil_total:
                st.sidebar.error(f"⚠️ Atenção! Preencha os campos obrigatórios do Gerente: **{', '.join(campos_faltantes)}**")
            else:
                if len(campos_faltantes) > 0 and eh_perfil_total:
                    st.sidebar.info(f"ℹ️ Salvando com campos do Gerente em branco: **{', '.join(campos_faltantes)}** (liberado para Admin/RH).")
                with st.spinner("⏳ Gravando no banco de dados (Supabase)..."):
                    loja_salvamento = int(dados_func['Loja']) if (dados_func is not None) else (int(loja_selecionada) if isinstance(loja_selecionada, int) else 1)
                    
                    payload = {
                        "Loja": loja_salvamento, 
                        "Nome": colaborador_final, 
                        "Dept": dept_final, 
                        "Função": funcao_final,
                        "Situação": situacao_final, 
                        "Observação": str(nova_obs).strip() if nova_obs else "-", 
                        "Data Abertura": nova_data_abertura,
                        "Responsável": str(novo_responsavel).strip() if novo_responsavel else "-", 
                        "Horário Contrato": str(novo_horario_contrato),
                        "Sexo": novo_sexo, 
                        "Motivo": novo_motivo, 
                        "Status RH": str(novo_status_rh).strip() if novo_status_rh else "-",
                        "Candidato": str(novo_candidato).strip() if novo_candidato else "-", 
                        "Data Admissão": nova_data_admissao,
                        "Usuario": st.session_state["usuario"]
                    }
                    
                    try:
                        # 1. Apaga o registro anterior se existir (garante o UPSERT perfeito)
                        supabase.table("banco_ql").delete().eq("Loja", loja_salvamento).eq("Nome", colaborador_final).execute()
                        
                        # 2. Insere a nova versão na tabela Banco
                        supabase.table("banco_ql").insert(payload).execute()
                        
                        # 3. Insere a mesma versão na tabela de Histórico (Log)
                        supabase.table("historico_ql").insert(payload).execute()
                        
                        st.sidebar.success("✅ Dados salvos com sucesso!")
                        st.cache_data.clear()
                        
                        time.sleep(2)
                        st.rerun()
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
    demitidos_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('DEMITIDO') | df_loja['Situação_Upper'].isin(['NAN', 'NONE', ''])])
    afastados_qtd = len(df_loja[df_loja['Situação_Upper'].str.contains('AFASTAMENTO|AFASTADO')])
    alterados_qtd = len(df_loja[df_loja['Possui_Alteracao_Sheets'] == True])
    admitidos_qtd = len(df_loja[df_loja['Admitido_Recente'] == True]) if 'Admitido_Recente' in df_loja.columns else 0

    def aplicar_filtro_card(status):
        if st.session_state["filtro_cards"] == status:
            st.session_state["filtro_cards"] = "TODOS"
        else:
            st.session_state["filtro_cards"] = status
            st.session_state["expander_global"] = True

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.button(f"🟢 {ativos_qtd} Ativos", on_click=aplicar_filtro_card, args=("ATIVO",), use_container_width=True)
    with c2:
        st.button(f"🔵 {ferias_qtd} Férias", on_click=aplicar_filtro_card, args=("FERIAS",), use_container_width=True)
    with c3:
        st.button(f"🔴 {demitidos_qtd} Demitidos", on_click=aplicar_filtro_card, args=("DEMITIDO",), use_container_width=True)
    with c4:
        st.button(f"🟠 {afastados_qtd} Afastados", on_click=aplicar_filtro_card, args=("AFASTADO",), use_container_width=True)
    with c5:
        st.button(f"🟣 {alterados_qtd} Alterados", on_click=aplicar_filtro_card, args=("ALTERADOS",), use_container_width=True)
    with c6:
        st.button(f"🎓 {admitidos_qtd} Admitidos", on_click=aplicar_filtro_card, args=("ADMITIDOS",), use_container_width=True)

    st.markdown("---")
    
    # === PAINEL DE CONTROLE E VISUALIZAÇÃO ===
    st.subheader("📋 Painel de Controle e Visualização")
    
    focar_colaborador = st.checkbox(f"🔍 Focar visualização apenas no colaborador: {colaborador_final}" if colaborador_final else "🔍 Focar colaborador selecionado", value=False)
    
    mostrar_relatorio = False
    if perfil in ["analista", "rh"]:
        mostrar_relatorio = st.checkbox("📊 Visualizar Relatório de Efetividade (Vagas Abertas vs Concluídas)", value=False)

    mostrar_ql_orcado = st.checkbox("📐 Visualizar QL Orçado (Organograma de Funções)", value=False)
    
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
        _agora_br = datetime.now() - timedelta(hours=3)  # Streamlit Cloud roda em UTC; Brasília = UTC-3
        st.caption(f"Relatório gerado em {_agora_br.strftime('%d/%m/%Y às %H:%M')}")
        
        col_d1, col_d2, col_d3 = st.columns([1, 1, 3])
        with col_d1:
            hoje = date.today()
            inicio_mes = date(hoje.year, hoje.month, 1)
            data_inicio_filtro = st.date_input("Data Início (Abertura):", value=inicio_mes, format="DD/MM/YYYY")
        with col_d2:
            data_fim_filtro = st.date_input("Data Fim (Abertura):", value=hoje, format="DD/MM/YYYY")
        with col_d3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            incluir_saidos = st.toggle(
                "Incluir admitidos que já saíram (histórico acumulado)",
                value=False,
                help="Desligado: conta só quem permaneceu no roster (foto atual). "
                     "Ligado: usa o ledger acumulado, incluindo quem foi admitido no período e depois saiu."
            )

        if data_fim_filtro:
            # Fonte combinada: banco oficial (banco_ql) + histórico (historico_ql),
            # deduplicado por (Loja, Nome). Conta também aberturas/admissões já arquivadas.
            registros_rel, _hist_bruto, _banco_bruto = combinar_banco_e_historico(supabase)

            # Escopo de lojas conforme a seleção do topo
            if isinstance(loja_selecionada, int):
                lojas_escopo = [loja_selecionada]
            elif loja_selecionada == "Total Lojas":
                lojas_escopo = [1, 2, 3, 4, 5, 6, 7, 8]
            else:  # "Total Rede" -> todas as lojas > 0
                lojas_escopo = None

            def _loja_int(r):
                try:
                    return int(float(str(r.get('Loja', 0))))
                except Exception:
                    return 0

            def _no_escopo(loja):
                return loja > 0 and (lojas_escopo is None or loja in lojas_escopo)

            linhas_rel = []
            datas_ad_invalidas = 0
            for r in registros_rel:
                loja = _loja_int(r)
                if not _no_escopo(loja):
                    continue

                d_ab = _parse_data_admissao(r.get('Data Abertura'))
                raw_ad = r.get('Data Admissão')
                d_ad = _parse_data_admissao(raw_ad)
                if d_ad is None and str(raw_ad).strip().lower() not in ["", "-", "nan", "none", "null", "nat", "0"]:
                    datas_ad_invalidas += 1

                tem_admissao = d_ad is not None
                # Concluída = admitida dentro do período (>= início e <= fim)
                is_concluida = tem_admissao and (data_inicio_filtro <= d_ad <= data_fim_filtro)
                # Aberta = estava aberta durante o período:
                #   - foi aberta até a data fim, E
                #   - não foi fechada (admitida) ANTES do início do período
                #   (admissões futuras/depois do fim contam como aberta; admitidas em período anterior, não)
                tem_requisicao = (d_ab is not None) or tem_admissao
                aberta_ate_fim = tem_requisicao and ((d_ab is None) or (d_ab <= data_fim_filtro))
                nao_fechada_antes = (not tem_admissao) or (d_ad >= data_inicio_filtro)
                is_aberta = (aberta_ate_fim and nao_fechada_antes) or is_concluida

                linhas_rel.append({
                    'Loja': loja,
                    'Nome': str(r.get('Nome', '')).title(),
                    'Data Abertura': r.get('Data Abertura'),
                    'Data Admissão': raw_ad,
                    'is_aberta': is_aberta,
                    'is_concluida': is_concluida,
                })

            df_rel = pd.DataFrame(linhas_rel)

            # --- CONCLUÍDAS = pessoas DISTINTAS admitidas no período ---
            # Fonte base = roster atual (Banco QL.xlsx, coluna "Admissão") = quem PERMANECEU.
            # Fonte acumulada = ledger admissoes_registradas = todos já admitidos no período
            # (inclui quem saiu depois). O toggle "incluir_saidos" escolhe qual usar na contagem.
            roster_por_loja = {}              # loja -> set nomes (permaneceram no roster)
            info_pessoa = {}                  # (loja, nome_norm) -> {Nome Admitido, Data Admissão}

            col_adm_excel = None
            for c in df_bruto.columns:
                if _norm_nome(c) == 'ADMISSAO':
                    col_adm_excel = c
                    break
            if col_adm_excel is not None:
                for _, linha in df_bruto.iterrows():
                    loja = _loja_int(linha)
                    if not _no_escopo(loja):
                        continue
                    d_ad = _parse_data_admissao(linha.get(col_adm_excel))
                    if d_ad is None or not (data_inicio_filtro <= d_ad <= data_fim_filtro):
                        continue
                    nome_norm = _norm_nome(linha.get('Nome', ''))
                    if not nome_norm:
                        continue
                    roster_por_loja.setdefault(loja, set()).add(nome_norm)
                    info_pessoa.setdefault((loja, nome_norm), {
                        'Nome Admitido': str(linha.get('Nome', '')).title(),
                        'Data Admissão': d_ad.strftime('%d/%m/%Y'),
                    })

            # Ledger acumulado (admissoes_registradas): inclui quem já saiu do roster
            ledger_por_loja = {}
            for r in (_ler_tabela_completa(supabase, "admissoes_registradas") or []):
                loja = _loja_int_val(r.get('Loja'))
                if not _no_escopo(loja):
                    continue
                d_ad = _parse_data_admissao(r.get('data_admissao_date') or r.get('Data Admissão'))
                if d_ad is None or not (data_inicio_filtro <= d_ad <= data_fim_filtro):
                    continue
                nn = r.get('nome_norm') or _norm_nome(r.get('Nome', ''))
                if not nn:
                    continue
                ledger_por_loja.setdefault(loja, set()).add(nn)
                info_pessoa.setdefault((loja, nn), {
                    'Nome Admitido': str(r.get('Nome', '')).title(),
                    'Data Admissão': d_ad.strftime('%d/%m/%Y'),
                })

            # Quem foi admitido no período mas JÁ SAIU do roster (está no ledger, não no roster)
            saidos_por_loja = {}
            for loja, nomes in ledger_por_loja.items():
                dif = nomes - roster_por_loja.get(loja, set())
                if dif:
                    saidos_por_loja[loja] = dif

            # Conjunto CONTADO conforme o toggle
            if incluir_saidos:
                pessoas_por_loja = {}
                for loja in set(list(roster_por_loja) + list(ledger_por_loja)):
                    pessoas_por_loja[loja] = roster_por_loja.get(loja, set()) | ledger_por_loja.get(loja, set())
            else:
                pessoas_por_loja = {loja: set(s) for loja, s in roster_por_loja.items()}

            # Tabela de diagnóstico das pessoas contadas (marca quem já saiu)
            conc_registros = {}
            for loja, nomes in pessoas_por_loja.items():
                for nn in nomes:
                    base = info_pessoa.get((loja, nn), {'Nome Admitido': nn.title(), 'Data Admissão': '-'})
                    saiu = nn in saidos_por_loja.get(loja, set())
                    conc_registros[(loja, nn)] = {
                        'Loja': loja, 'Nome Admitido': base['Nome Admitido'],
                        'Data Admissão': base['Data Admissão'],
                        'Situação': '🔴 Já saiu' if saiu else '🟢 No roster',
                    }

            # Lista dos que já saíram (sinalização), independente do toggle
            saidos_registros = []
            for loja, nomes in saidos_por_loja.items():
                for nn in nomes:
                    base = info_pessoa.get((loja, nn), {'Nome Admitido': nn.title(), 'Data Admissão': '-'})
                    saidos_registros.append({
                        'Loja': loja, 'Nome Admitido': base['Nome Admitido'],
                        'Data Admissão': base['Data Admissão'],
                    })

            # Auditoria: admissões do QL (Candidato) que NÃO estão no roster NEM no ledger
            todos_conhecidos = {}
            for loja in set(list(roster_por_loja) + list(ledger_por_loja)):
                todos_conhecidos[loja] = roster_por_loja.get(loja, set()) | ledger_por_loja.get(loja, set())
            ql_fora_roster = {}
            for r in list(_hist_bruto) + list(_banco_bruto):
                loja = _loja_int(r)
                if not _no_escopo(loja):
                    continue
                d_ad = _parse_data_admissao(r.get('Data Admissão'))
                if d_ad is None or not (data_inicio_filtro <= d_ad <= data_fim_filtro):
                    continue
                cand = str(r.get('Candidato', '')).strip()
                if cand.upper() in ['', '-', 'NAN', 'NONE', 'NULL', 'NAT']:
                    continue
                nome_norm = _norm_nome(cand)
                if nome_norm in todos_conhecidos.get(loja, set()):
                    continue
                chave = (loja, nome_norm)
                if chave not in ql_fora_roster:
                    ql_fora_roster[chave] = {
                        'Loja': loja, 'Candidato (só no QL)': str(cand).title(),
                        'Data Admissão': d_ad.strftime('%d/%m/%Y'),
                        'Vaga (Nome)': str(r.get('Nome', '')).title(),
                    }

            df_conc_diag = pd.DataFrame(list(conc_registros.values()))
            df_ql_fora = pd.DataFrame(list(ql_fora_roster.values()))
            df_saidos = pd.DataFrame(saidos_registros)

            tem_concluidas = any(len(s) > 0 for s in pessoas_por_loja.values())
            if df_rel.empty or (not df_rel['is_aberta'].any() and not tem_concluidas):
                st.info("Nenhuma abertura ou admissão encontrada no período selecionado para esta(s) loja(s).")
            else:
                abertas_por_loja = (
                    df_rel[df_rel['is_aberta']].groupby('Loja').size().reset_index(name='Abertas')
                )
                if pessoas_por_loja:
                    concluidas_por_loja = pd.DataFrame(
                        [{'Loja': loja, 'Concluídas': len(s)} for loja, s in pessoas_por_loja.items()]
                    )
                else:
                    concluidas_por_loja = pd.DataFrame(columns=['Loja', 'Concluídas'])

                df_relatorio = pd.merge(abertas_por_loja, concluidas_por_loja, on='Loja', how='outer').fillna(0)
                df_relatorio['Abertas'] = df_relatorio['Abertas'].astype(int)
                df_relatorio['Concluídas'] = df_relatorio['Concluídas'].astype(int)
                df_relatorio = df_relatorio.sort_values('Loja').reset_index(drop=True)
                df_relatorio['%'] = df_relatorio.apply(
                    lambda r: int(round(r['Concluídas'] / r['Abertas'] * 100)) if r['Abertas'] > 0 else 0,
                    axis=1
                )

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
                    marker_color='#90A4B8',
                    marker_line_width=0, 
                    text=abertas_y,
                    textposition='outside', 
                    textfont=dict(color='#22303C', size=13)
                ))

                fig.add_trace(go.Bar(
                    x=lojas_x, y=concluidas_y,
                    name='Concluídas',
                    marker_color='#0093E9',
                    marker_line_width=0,
                    text=concluidas_y,
                    textposition='outside',
                    textfont=dict(color='#22303C', size=13)
                ))

                teto_grafico = max(abertas_y) if abertas_y else 1
                for i, loja in enumerate(lojas_x):
                    fig.add_annotation(
                        x=loja,
                        y=max(abertas_y[i], concluidas_y[i]) + (teto_grafico * 0.15), 
                        text=f"<b>{perc_y[i]}%</b>",
                        showarrow=False,
                        font=dict(color="#E5007D" if perc_y[i] > 0 else "#90A4B8", size=15) 
                    )

                fig.update_layout(
                    barmode='group',
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#22303C', family="sans-serif"),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                        font=dict(size=14)
                    ),
                    margin=dict(t=50, b=0, l=0, r=0),
                    yaxis=dict(
                        showgrid=True, 
                        gridcolor='rgba(0,0,0,0.06)', 
                        showticklabels=False, 
                        zeroline=True,
                        zerolinecolor='rgba(0,0,0,0.1)',
                        range=[0, teto_grafico * 1.35] 
                    ),
                    xaxis=dict(
                        showgrid=False,
                        tickfont=dict(size=13, color='#22303C')
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
                        estilo_linha = "background-color: #DCEBF7; font-weight: bold;"
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

                # 🔍 Painel de diagnóstico (ajuda a reconciliar os números)
                with st.expander("🔍 Diagnóstico da contagem (conferência)"):
                    n_banco = len(_banco_bruto)
                    n_hist = len(_hist_bruto)
                    n_conc_contadas = int(total_concluidas)
                    n_ql_fora = len(df_ql_fora) if not df_ql_fora.empty else 0
                    n_saidos = len(df_saidos) if not df_saidos.empty else 0
                    modo = "histórico acumulado (inclui quem já saiu)" if incluir_saidos else "roster atual (só quem permaneceu)"
                    st.markdown(
                        f"- Modo de contagem: **{modo}**  \n"
                        f"- **Concluídas** no período: `{n_conc_contadas}`  \n"
                        f"- Admitidos no período que **já saíram** do roster: `{n_saidos}` "
                        f"({'incluídos' if incluir_saidos else 'NÃO incluídos'} na conta atual)  \n"
                        f"- Linhas lidas do banco_ql: `{n_banco}` | historico_ql: `{n_hist}`"
                    )
                    if col_adm_excel is None:
                        st.warning(
                            "Não encontrei a coluna **Admissão** no `Banco QL.xlsx` — a contagem ficou zerada. "
                            "Me diga o nome exato da coluna que eu ajusto."
                        )

                    st.markdown("**Pessoas contadas como admitidas no período:**")
                    if not df_conc_diag.empty:
                        df_conc = df_conc_diag[['Loja', 'Nome Admitido', 'Data Admissão', 'Situação']].sort_values(['Loja', 'Nome Admitido'])
                    else:
                        df_conc = df_conc_diag
                    st.dataframe(df_conc, use_container_width=True, hide_index=True)

                    if n_saidos:
                        st.markdown(
                            f"**👋 {n_saidos} admitido(s) no período que já saíram do roster** "
                            f"(preservados no histórico acumulado — some no botão acima pra incluir/excluir):"
                        )
                        st.dataframe(
                            df_saidos[['Loja', 'Nome Admitido', 'Data Admissão']].sort_values(['Loja', 'Nome Admitido']),
                            use_container_width=True, hide_index=True
                        )

                    if n_ql_fora:
                        st.markdown(
                            f"**⚠️ {n_ql_fora} admissão(ões) lançada(s) no QL que NÃO estão no roster nem no histórico "
                            f"(NÃO contadas — como o Cristiano Afonso):**"
                        )
                        st.caption(
                            "Confira: se alguma dessas é uma admissão real que faltou no roster, o certo é "
                            "acertar no Senior/`Banco QL.xlsx`. Se é lançamento errado, vale corrigir no QL."
                        )
                        st.dataframe(
                            df_ql_fora[['Loja', 'Candidato (só no QL)', 'Data Admissão', 'Vaga (Nome)']].sort_values(['Loja', 'Candidato (só no QL)']),
                            use_container_width=True, hide_index=True
                        )
        
        st.markdown("---") 

    # =========================================================
    # 📐 VISÃO QL ORÇADO (ORGANOGRAMA) - módulo ql_orcado.py
    # =========================================================
    if mostrar_ql_orcado:
        renderizar_visao_ql_orcado(
            supabase,
            loja_selecionada,
            pode_editar=(perfil in PERFIS_EDICAO_TOTAL),
            usuario=st.session_state["usuario"],
            df_quadro=df_loja,
        )
        st.markdown("---")

    # =========================================================================
    # Lógica combinada: Quadro de Admitidos + Checkbox de alterados + Filtro dos Botões
    if st.session_state["filtro_cards"] == "ADMITIDOS":
        # 🎓 QUADRO DE ADMITIDOS: só admissões dos últimos DIAS_RETENCAO_ADMISSAO dias.
        df_exibicao = df_loja[df_loja['Admitido_Recente'] == True].copy()
        st.info(f"🎓 **Quadro de Admitidos** — colaboradores admitidos nos últimos {DIAS_RETENCAO_ADMISSAO} dias. "
                f"Depois desse prazo, o lançamento é arquivado no histórico (historico_ql) e sai do sistema.")
    elif apenas_alterados or st.session_state["filtro_cards"] == "ALTERADOS":
        df_exibicao = df_loja[df_loja['Possui_Alteracao_Sheets'] == True].copy()
        st.info("💡 Exibindo estritamente colaboradores com digitação salva no Supabase.")
    else:
        # Quadro operacional do dia a dia: admissões antigas saem daqui.
        # Os dados NÃO são apagados — continuam no Relatório de Efetividade e no card "Admitidos".
        df_exibicao = df_loja.copy()

        # 1) Admitido há mais de X dias e SEM registro no Excel -> some do quadro
        #    (permanece salvo no banco/histórico e visível no card Admitidos).
        manuais_arquivar = (df_exibicao['Admitido_Arquivar'] == True) & (df_exibicao['Existe_No_Excel'] == False)
        df_exibicao = df_exibicao[~manuais_arquivar]

        # 2) Admitido há mais de X dias e COM registro no Excel -> nome continua no quadro,
        #    mas as colunas de requisição são limpas (o lançamento "some", o colaborador fica).
        excel_arquivar = df_exibicao['Admitido_Arquivar'] == True
        colunas_requisicao = [
            'Observação', 'Data Abertura', 'Responsável', 'Horário Contrato',
            'Sexo', 'Motivo', 'Status RH', 'Candidato', 'Data Admissão'
        ]
        for c in colunas_requisicao:
            df_exibicao.loc[excel_arquivar, c] = "-"
        df_exibicao.loc[excel_arquivar, 'Possui_Alteracao_Sheets'] = False

    # Filtra o dataframe principal se algum botão de status for clicado
    filtro_atual = st.session_state["filtro_cards"]
    if filtro_atual not in ["TODOS", "ALTERADOS", "ADMITIDOS"]:
        if filtro_atual == "ATIVO":
            df_exibicao = df_exibicao[df_exibicao['Situação_Upper'].str.contains('ATIVO')]
        elif filtro_atual == "FERIAS":
            df_exibicao = df_exibicao[df_exibicao['Situação_Upper'].str.contains('FÉRIAS|FERIAS')]
        elif filtro_atual == "DEMITIDO":
            df_exibicao = df_exibicao[df_exibicao['Situação_Upper'].str.contains('DEMITIDO') | df_exibicao['Situação_Upper'].isin(['NAN', 'NONE', ''])]
        elif filtro_atual == "AFASTADO":
            df_exibicao = df_exibicao[df_exibicao['Situação_Upper'].str.contains('AFASTAMENTO|AFASTADO')]
        
        st.warning(f"🔍 Tabela filtrada pelo status: **{filtro_atual}**. Clique no botão novamente para remover o filtro.")

    # 🎯 Orçado x Real nos títulos dos departamentos/cargos
    try:
        mapa_orcado_dept, mapa_orcado_func = carregar_mapas_orcado(supabase, loja_selecionada)
    except Exception:
        mapa_orcado_dept, mapa_orcado_func = {}, {}
    df_real_base = df_loja[df_loja['Situação_Upper'].str.contains('ATIVO|FÉRIAS|FERIAS', na=False)]

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

        real_dept = len(df_real_base[df_real_base['Dept'] == dept])
        info_orcado_dept = badge_orcado(
            obter_orcado_dept(mapa_orcado_dept, mapa_orcado_func, dept), real_dept)

        with st.expander(f"🏢 DEPARTAMENTO: {dept} ({total_funcionarios_dept}){info_orcado_dept}", expanded=expander_aberto):
            funcoes = sorted(df_dept['Função'].dropna().unique())
            
            for funcao in funcoes:
                df_funcao = df_dept[df_dept['Função'] == funcao]
                
                if focar_colaborador and colaborador_final:
                    if colaborador_final not in df_funcao['Nome'].values:
                        continue
                
                real_func = len(df_real_base[(df_real_base['Dept'] == dept) & (df_real_base['Função'] == funcao)])
                info_orcado_func = badge_orcado(
                    obter_orcado_funcao(mapa_orcado_func, dept, funcao), real_func)
                st.markdown(f"**🔹 Cargo: {funcao}**{info_orcado_func}")
                
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
<th colspan="{colspan_analista}" style="background-color: #0B3D63; color: white; text-align: center; font-weight: 600; padding: 8px;">📊 DONO: ANALISTA</th>
<th colspan="1" style="background-color: #E5007D; color: white; text-align: center; font-weight: 600; padding: 8px;">📋 DONO: SUPERVISOR</th>
<th colspan="5" style="background-color: #047857; color: white; text-align: center; font-weight: 600; padding: 8px;">🏪 DONO: GERENTE</th>
<th colspan="3" style="background-color: #be123c; color: white; text-align: center; font-weight: 600; padding: 8px;">🤝 DONO: RH</th>
</tr>
<tr style="color: #22303C; font-weight: 500;">
<th style="background-color: #DCEBF7; color: #22303C; border-bottom: 2px solid #C4D4E0; text-align: center; padding: 8px;">Status</th>
"""
                
                if modo_visao_global:
                    html_tabela += '<th style="background-color: #DCEBF7; color: #22303C; border-bottom: 2px solid #C4D4E0; text-align: center; padding: 8px;">Loja</th>\n'
                    
                cabecalhos = ["Nome do Colaborador", "Horário Sistema", "Observação", "Data Abertura", "Responsável", "Horário Contrato", "Sexo", "Motivo", "Status RH", "Candidato", "Data Admissão"]

                for cab in cabecalhos:
                    html_tabela += f'<th style="background-color: #DCEBF7; color: #22303C; border-bottom: 2px solid #C4D4E0; text-align: center; padding: 8px;">{cab}</th>\n'
                
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
