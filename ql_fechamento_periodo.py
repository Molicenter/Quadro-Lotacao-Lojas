# ==========================================================================
# Congelamento do relatório "Análise de Preenchimento por Período de Abertura"
# Quadro-Lotacao-Lojas — cole estas funções perto de combinar_banco_e_historico
# ==========================================================================
#
# Pré-requisito: rodar ql_fechamento_periodo.sql no Supabase antes de usar.
#
# Como plugar no app.py:
#
#   1) Envolva o cálculo atual (tudo que já existe hoje: chamada a
#      combinar_banco_e_historico, montagem de linhas_rel/df_rel, os merges
#      que geram o df_relatorio final com colunas Loja/Requisições/
#      Abertas/Concluídas/%, SEM a linha "Total") numa função sem
#      argumentos, por exemplo:
#
#          def _calcular_relatorio_ao_vivo():
#              registros_rel, _hist_bruto, _banco_bruto = combinar_banco_e_historico(supabase)
#              # ... exatamente o que já existe hoje ...
#              return df_relatorio
#
#   2) Troque a chamada direta a essa lógica por:
#
#          df_relatorio, veio_de_snapshot = obter_relatorio_periodo(
#              supabase, data_inicio_filtro, data_fim_filtro,
#              _calcular_relatorio_ao_vivo,
#          )
#
#          if veio_de_snapshot:
#              st.caption("📌 Período fechado — valores congelados no primeiro fechamento gerado.")
#
#      Daqui pra baixo, o resto do código (linha Total, tabela, gráfico
#      Plotly) continua igual, usando df_relatorio normalmente.
#
# Importante: isso congela o RESULTADO do relatório (Requisições/Abertas/
# Concluídas por loja), não mexe em ql_banco/ql_historico nem na
# deduplicação por Loja+Nome de combinar_banco_e_historico. Se dois
# registros diferentes do mesmo mês tiverem a mesma Loja com "Nome" vazio
# (vaga sem candidato ainda), eles continuam colidindo na MESMA chave
# dentro de combinar_banco_e_historico e um pode sobrescrever o outro —
# é provavelmente essa colisão (Loja + Nome em branco) que está fazendo
# Requisições/Abertas encolherem com o tempo. O congelamento abaixo evita
# que isso volte a mudar um período já fechado, mas não corrige a causa
# raiz na leitura ao vivo do período corrente. Se quiser, dá pra investigar
# depois trocando a chave de dedup para incluir algo mais único por
# requisição (um id, ou Loja+Nome+Data Abertura).

from datetime import date
import pandas as pd


def _periodo_esta_fechado(data_fim_filtro: date) -> bool:
    """Um período só é considerado 'fechado' quando a data fim já passou
    completamente — hoje ou uma data futura continuam ao vivo."""
    return data_fim_filtro < date.today()


def carregar_fechamento_salvo(supabase, data_inicio_filtro: date, data_fim_filtro: date):
    """Busca em ql_fechamentos_periodo um snapshot já congelado para esse
    período exato (mesma data_inicio e data_fim). Retorna um dict
    {loja: {"Requisições": int, "Abertas": int, "Concluídas": int}}
    ou None se ainda não existe snapshot para esse período."""
    try:
        resp = (
            supabase.table("ql_fechamentos_periodo")
            .select("*")
            .eq("data_inicio", data_inicio_filtro.isoformat())
            .eq("data_fim", data_fim_filtro.isoformat())
            .execute()
        )
        linhas = resp.data or []
    except Exception as e:
        print(f"[Fechamento] Erro ao ler ql_fechamentos_periodo: {e}")
        return None

    if not linhas:
        return None

    return {
        int(r["loja"]): {
            "Requisições": int(r["requisicoes"]),
            "Abertas": int(r["abertas"]),
            "Concluídas": int(r["concluidas"]),
        }
        for r in linhas
    }


def salvar_fechamento(supabase, data_inicio_filtro: date, data_fim_filtro: date, df_relatorio):
    """Congela o df_relatorio já calculado (uma linha por loja, SEM a
    linha 'Total') em ql_fechamentos_periodo. Upsert por
    (data_inicio, data_fim, loja) — chamar de novo não duplica nem
    sobrescreve com valores diferentes."""
    registros = []
    for _, linha in df_relatorio.iterrows():
        registros.append({
            "data_inicio": data_inicio_filtro.isoformat(),
            "data_fim": data_fim_filtro.isoformat(),
            "loja": int(linha["Loja"]),
            "requisicoes": int(linha["Requisições"]),
            "abertas": int(linha["Abertas"]),
            "concluidas": int(linha["Concluídas"]),
        })
    if not registros:
        return
    try:
        supabase.table("ql_fechamentos_periodo").upsert(
            registros, on_conflict="data_inicio,data_fim,loja"
        ).execute()
        print(f"[Fechamento] Snapshot salvo para {data_inicio_filtro}–{data_fim_filtro} "
              f"({len(registros)} loja(s)).")
    except Exception as e:
        print(f"[Fechamento] Erro ao salvar snapshot: {e}")


def obter_relatorio_periodo(supabase, data_inicio_filtro: date, data_fim_filtro: date, calcular_ao_vivo):
    """Ponto único de entrada para o relatório de período.

    calcular_ao_vivo: função sem argumentos que roda o cálculo atual do
    app e devolve o df_relatorio (colunas: Loja, Requisições, Abertas,
    Concluídas, %), sem a linha Total.

    Regras:
    - Período em andamento (data_fim_filtro >= hoje): sempre calcula ao
      vivo, nunca lê nem grava snapshot. Mês corrente continua dinâmico.
    - Período fechado (data_fim_filtro < hoje):
        - Se já existe snapshot para esse (data_inicio, data_fim) exato,
          devolve o snapshot congelado — não recalcula.
        - Se não existe ainda, calcula ao vivo uma vez e congela agora,
          pra nunca mais mudar.

    Retorna (df_relatorio, veio_de_snapshot).
    """
    if not _periodo_esta_fechado(data_fim_filtro):
        return calcular_ao_vivo(), False

    salvo = carregar_fechamento_salvo(supabase, data_inicio_filtro, data_fim_filtro)
    if salvo is not None:
        df = pd.DataFrame([
            {"Loja": loja, **valores} for loja, valores in salvo.items()
        ])
        df["%"] = df.apply(
            lambda r: int(round(r["Concluídas"] / r["Requisições"] * 100))
            if r["Requisições"] > 0 else 0,
            axis=1,
        )
        return df.sort_values("Loja").reset_index(drop=True), True

    df_relatorio = calcular_ao_vivo()
    salvar_fechamento(supabase, data_inicio_filtro, data_fim_filtro, df_relatorio)
    return df_relatorio, False
