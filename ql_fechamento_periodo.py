# ==========================================================================
# Congelamento do relatório "Análise de Preenchimento por Período de Abertura"
# Quadro-Lotacao-Lojas — cole estas funções perto de combinar_banco_e_historico
# ==========================================================================
#
# v2 (set/2026): agora também congela "Concluídas RH" (Status RH = "Requisição
# atendida"), que vem da mesma fonte deduplicada (combinar_banco_e_historico)
# que Requisições/Abertas e por isso decai do mesmo jeito. "Concluídas DP"
# (admitidos conforme a planilha/ledger) continua sempre calculada ao vivo —
# ela já não decai, vem de uma fonte estável.
#
# Pré-requisito: rodar migracao_v2_concluidas_rh.sql no Supabase ANTES de
# atualizar o app.py (renomeia a coluna concluidas -> concluidas_dp e cria
# concluidas_rh). Se está criando a tabela do zero agora, use
# ql_fechamento_periodo.sql (já vem com o esquema novo).
#
# Como plugar no app.py — veja o app_py_patch.md / app.py que te mandei:
# a função _montar_df_relatorio_ao_vivo() precisa devolver um DataFrame com
# as colunas: Loja, Requisições, Abertas, Concluídas DP, Concluídas RH, %.

from datetime import date
import pandas as pd


def _periodo_esta_fechado(data_fim_filtro: date) -> bool:
    """Um período só é considerado 'fechado' quando a data fim já passou
    completamente — hoje ou uma data futura continuam ao vivo."""
    return data_fim_filtro < date.today()


def carregar_fechamento_salvo(supabase, data_inicio_filtro: date, data_fim_filtro: date):
    """Busca em ql_fechamentos_periodo um snapshot já congelado para esse
    período exato (mesma data_inicio e data_fim). Retorna um dict
    {loja: {"Requisições": int, "Abertas": int, "Concluídas DP": int,
    "Concluídas RH": int}} ou None se ainda não existe snapshot."""
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
            "Concluídas DP": int(r.get("concluidas_dp", 0)),
            "Concluídas RH": int(r.get("concluidas_rh", 0)),
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
            "concluidas_dp": int(linha["Concluídas DP"]),
            "concluidas_rh": int(linha["Concluídas RH"]),
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


def sobrescrever_concluidas_rh_snapshot(supabase, data_inicio_filtro: date, data_fim_filtro: date, concluidas_rh_por_loja):
    """Atualiza SÓ a coluna concluidas_rh de um snapshot já congelado, sem
    tocar em requisicoes/abertas/concluidas_dp. Serve pra preencher
    Concluídas RH de períodos que foram congelados antes dessa métrica
    existir (ficaram com 0). O valor vem do estado ATUAL do banco — se o
    período já estava fechado há um tempo, pode carregar um pouco do mesmo
    decaimento de Requisições/Abertas, mas ainda assim é bem melhor do que
    ficar zerado pra sempre.

    concluidas_rh_por_loja: DataFrame com colunas 'Loja' e 'Concluídas RH'
    (o mesmo que o app já calcula ao vivo antes de decidir se usa o
    snapshot ou não). Retorna a qtde de lojas atualizadas."""
    atualizados = 0
    for _, linha in concluidas_rh_por_loja.iterrows():
        try:
            supabase.table("ql_fechamentos_periodo").update(
                {"concluidas_rh": int(linha["Concluídas RH"])}
            ).eq("data_inicio", data_inicio_filtro.isoformat()) \
             .eq("data_fim", data_fim_filtro.isoformat()) \
             .eq("loja", int(linha["Loja"])) \
             .execute()
            atualizados += 1
        except Exception as e:
            print(f"[Fechamento] Erro ao atualizar concluidas_rh (loja {linha.get('Loja')}): {e}")
    if atualizados:
        print(f"[Fechamento] Concluídas RH recalculada em {atualizados} loja(s) "
              f"para {data_inicio_filtro}–{data_fim_filtro}.")
    return atualizados


def obter_relatorio_periodo(supabase, data_inicio_filtro: date, data_fim_filtro: date, calcular_ao_vivo):
    """Ponto único de entrada para o relatório de período.

    calcular_ao_vivo: função sem argumentos que roda o cálculo atual do
    app e devolve o df_relatorio (colunas: Loja, Requisições, Abertas,
    Concluídas DP, Concluídas RH, %), sem a linha Total.

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
            lambda r: int(round(r["Concluídas DP"] / r["Requisições"] * 100))
            if r["Requisições"] > 0 else 0,
            axis=1,
        )
        return df.sort_values("Loja").reset_index(drop=True), True

    df_relatorio = calcular_ao_vivo()
    salvar_fechamento(supabase, data_inicio_filtro, data_fim_filtro, df_relatorio)
    return df_relatorio, False
