"""
etl_reverso.py - Carga da camada GOLD para o banco de dados
===============================================================

OBJETIVO DESTE EXERCÍCIO
--------------------------
Este é o último passo do pipeline: pegar os 4 arquivos CSV que você
gerou em `lakehouse/gold/saida/` e carregá-los em `application/database.sqlite`,
**sem mudar nada de estrutura** -- mesmas colunas, mesmos nomes, mesmos
valores. Cada CSV vira uma tabela de mesmo nome no banco.

Por que "ETL reverso"? Num pipeline normal, dados fluem de sistemas
operacionais para um banco analítico (landing -> bronze -> silver ->
gold, como você já fez). Aqui a gente inverte o sentido: pega o dado já
analítico/agregado da gold e carrega de volta num banco relacional --
exatamente o padrão que, no mercado, se chama de "reverse ETL" (levar
métricas prontas de volta para um sistema que outras ferramentas, como
este app Streamlit, conseguem consultar).

Não tem agregação, não tem limpeza, não tem SQL sofisticado aqui: é uma
ingestão simples, tipo "copiar e colar" o CSV para dentro de uma tabela.
Todo o trabalho de calcular as métricas já foi feito por você lá na
camada gold -- aqui você só está mudando o formato de armazenamento (de
CSV para SQLite) para o app Streamlit em `app.py` poder ler.

Isso fecha o pipeline completo:

    landing -> bronze -> silver -> gold -> database (ETL reverso) -> relatório

## O que fazer

Implemente as duas funções marcadas com `TODO`:
  - `criar_tabela()`: cria a tabela no banco com as colunas certas.
  - `inserir_linhas()`: insere as linhas do CSV na tabela, sem alterar
    nenhum valor.

Depois rode:
    python application/etl_reverso.py
    python application/verificar_etl_reverso.py
"""

import csv
import sqlite3
from pathlib import Path

GOLD_SAIDA = Path(__file__).parent.parent / "lakehouse" / "gold" / "saida"
BANCO = Path(__file__).parent / "database.sqlite"

# nome da tabela -> colunas esperadas (na mesma ordem do CSV de origem)
TABELAS = {
    "resumo_vendas_categoria": ["categoria", "quantidade_vendida", "valor_total"],
    "vendas_por_mes": ["mes", "quantidade_vendas", "valor_total"],
    "top_clientes": ["id_cliente", "nome", "valor_total"],
    "resumo_geral": ["total_vendas", "valor_total_geral", "ticket_medio"],
}


def ler_csv_gold(nome_tabela: str) -> list[dict]:
    caminho = GOLD_SAIDA / f"{nome_tabela}.csv"
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def criar_tabela(conexao: sqlite3.Connection, nome_tabela: str, colunas: list[str]) -> None:
    colunas_sql = ", ".join(colunas)

    conexao.execute(f"DROP TABLE IF EXISTS {nome_tabela}")
    conexao.execute(f"CREATE TABLE {nome_tabela} ({colunas_sql})") 
    # confesso que nao sabia NADA do que tinha que fazer aqui e tive que recorrer a uma LLM
    


def inserir_linhas(conexao: sqlite3.Connection, nome_tabela: str, colunas: list[str], linhas: list[dict]) -> None:
    colunas_sql = ", ".join(colunas)
    placeholders = ", ".join("?" for _ in colunas)
    sql = (
        f"INSERT INTO {nome_tabela} "
        f"({colunas_sql})"
        f"VALUES ({placeholders})"
    )
    for linha in linhas:
        valores = [linha.get(coluna, "") for coluna in colunas]
        conexao.execute(sql, valores)


def main() -> None:
    if BANCO.exists():
        BANCO.unlink()  # recomeça do zero a cada execução

    conexao = sqlite3.connect(BANCO)
    for nome_tabela, colunas in TABELAS.items():
        linhas = ler_csv_gold(nome_tabela)
        criar_tabela(conexao, nome_tabela, colunas)
        inserir_linhas(conexao, nome_tabela, colunas, linhas)
        print(f"{nome_tabela}: {len(linhas)} linhas carregadas")
    conexao.commit()
    conexao.close()

    print("\nAgora rode: python application/verificar_etl_reverso.py")


if __name__ == "__main__":
    main()
