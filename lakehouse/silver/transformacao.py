"""
transformacao.py - Camada SILVER
==================================

OBJETIVO DESTA CAMADA
----------------------
Aqui você limpa e padroniza o que veio da bronze, aplicando regras de
negócio claras (todas listadas em `lakehouse/silver/README.md`). O resultado deve
ser um conjunto de dados CONFIÁVEL: tipos corretos, sem duplicatas, sem
valores impossíveis, categorias padronizadas.

Entrada:  lakehouse/bronze/saida/*.csv   (o que você gerou na camada anterior)
Saída:    lakehouse/silver/saida/vendas_silver.csv
          lakehouse/silver/saida/clientes_silver.csv
          lakehouse/silver/saida/produtos_silver.csv

Regras de limpeza (resumo -- leia lakehouse/silver/README.md para os detalhes):

  clientes:
    - id_cliente vira inteiro.
    - email: tira espaços, deixa em minúsculo. Se não tiver "@", o
      registro é DESCARTADO (e-mail impossível de corrigir).
    - estado: tira espaços, deixa em MAIÚSCULO (sigla de 2 letras).
    - Se houver id_cliente duplicado, mantenha o ÚLTIMO registro que
      aparece no arquivo (é o mais recente).

  produtos:
    - id_produto vira inteiro, preco vira float (troque "," por "." antes
      de converter).
    - categoria: tire espaços e padronize a capitalização para bater
      EXATAMENTE com uma das categorias válidas (veja CATEGORIAS_VALIDAS
      no README). Dica: comparar em minúsculas e depois usar um
      dicionário de "categoria em minúsculo -> categoria oficial".
    - ativo: "sim" -> 1, "nao"/"não" -> 1 é ERRADO, "nao"/"não" -> 0,
      "1" -> 1, "0" -> 0, vazio -> 0 (trate como inativo).
    - Se houver id_produto duplicado, mantenha a PRIMEIRA ocorrência.

  vendas:
    - id_venda, id_cliente, id_produto viram inteiros.
    - data_venda: pode vir como "AAAA-MM-DD" ou "DD/MM/AAAA" (às vezes com
      espaços em volta) -> padronize sempre para "AAAA-MM-DD".
    - quantidade: vira inteiro. Linhas com quantidade vazia, zero ou
      negativa são DESCARTADAS (não fazem sentido no negócio).
    - valor_total: vira float (troque "," por "."). Linhas com valor
      vazio são DESCARTADAS.
    - Linhas EXATAMENTE duplicadas (mesmo id_venda repetido) -> mantenha
      só uma ocorrência.
    - Linhas cujo id_cliente ou id_produto não existe mais em
      clientes_silver / produtos_silver (porque foi descartado, ou porque
      nunca existiu -- ex.: id_cliente 9999) -> DESCARTADAS.

Dica de organização: processe clientes e produtos PRIMEIRO, guarde o
conjunto de ids válidos, e só então processe vendas usando esses ids
para o filtro de integridade referencial.
"""

import csv
from pathlib import Path

LAKEHOUSE = Path(__file__).parent.parent
BRONZE_SAIDA = LAKEHOUSE / "bronze" / "saida"
SAIDA = Path(__file__).parent / "saida"

CATEGORIAS_VALIDAS = {"Eletrônicos", "Livros", "Roupas", "Alimentos", "Brinquedos"}
ESTADOS_VALIDOS = {"SP", "RJ", "MG", "RS", "BA", "PR", "PE", "CE", "SC", "GO"}


def ler_csv(caminho: Path) -> list[dict]:
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def salvar_csv(registros: list[dict], caminho_saida: Path, colunas: list[str]) -> None:
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        for registro in registros:
            escritor.writerow({coluna: registro.get(coluna, "") for coluna in colunas})


def limpar_clientes(bronze: list[dict]) -> list[dict]:
    clientes_por_id = {}
    for cliente in bronze:
        email = cliente.get("email", "").strip().lower() # esse "" eh so pra colocar um texto vazio e nao dar erro caso nao exista
        if "@" not in email:
            continue
        id_cliente = int(cliente["id_cliente"])
        estado = cliente.get("estado", "").strip().upper()
        cliente_limpo = {
            "id_cliente": id_cliente, 
            "nome": cliente.get("nome", ""),
            "email": email,
            "cidade": cliente.get("cidade", ""),
            "estado": estado,
            "data_cadastro": cliente.get("data_cadastro", "")
        }
        clientes_por_id[id_cliente] = cliente_limpo
    return list(clientes_por_id.values())


def limpar_produtos(bronze: list[dict]) -> list[dict]:
    produtos_por_id = {}

    categorias_por_nome = {categoria.lower(): categoria for categoria in CATEGORIAS_VALIDAS}
    ativos = {
    "sim": 1,
    "1": 1,
    "nao": 0,
    "não": 0,
    "0": 0,
    "": 0
    } #esses dois dicionarios foi para criar aquilo que vai ser de "referência"
    for produto in bronze:
        id_produto = int(produto["id_produto"])
        if id_produto in produtos_por_id:
            continue

        preco_texto = produto["preco"].strip().replace(",", ".")
        preco = float(preco_texto)

        categoria_texto = produto["categoria"].strip().lower()
        categoria = categorias_por_nome.get(categoria_texto)
        if categoria is None:
            continue

        ativo_texto = produto.get("ativo", "").strip().lower()
        ativo = ativos.get(ativo_texto, 0)

        produto_limpo = {
            "id_produto": id_produto,
            "nome": produto.get("nome", ""),
            "categoria": categoria,
            "preco": preco,
            "ativo": ativo
        }
        produtos_por_id[id_produto] = produto_limpo
    return list(produtos_por_id.values())
    


def limpar_vendas(bronze: list[dict], ids_clientes_validos: set[int], ids_produtos_validos: set[int]) -> list[dict]:
    vendas_limpas = []
    ids_vendas_encontrados = set() # para ficar eficiente e nao ter duplicatas
    for venda in bronze:
        id_venda = int(venda["id_venda"])
        id_cliente = int(venda["id_cliente"])
        id_produto = int(venda["id_produto"])
        if id_venda in ids_vendas_encontrados:
            continue
        if id_cliente not in ids_clientes_validos:
            continue
        if id_produto not in ids_produtos_validos:
            continue

        quantidade_texto = venda.get("quantidade", "").strip()
        if not quantidade_texto:
            continue
        quantidade = int(quantidade_texto)
        if quantidade <= 0:
            continue

        valor_texto = venda.get("valor_total", "").strip()
        if not valor_texto:
            continue
        valor_total = float(valor_texto.replace(",", "."))

        data = venda.get("data_venda", "").strip()
        if "/" in data:
            dia, mes, ano = data.split("/")
            data = f"{ano}-{mes}-{dia}"
        venda_limpa = {
            "id_venda": id_venda,
            "id_cliente": id_cliente,
            "id_produto": id_produto,
            "quantidade": quantidade,
            "data_venda": data,
            "valor_total": valor_total
        }
        vendas_limpas.append(venda_limpa)
        ids_vendas_encontrados.add(id_venda)
    return vendas_limpas

        

def main() -> None:
    clientes_bronze = ler_csv(BRONZE_SAIDA / "clientes_bronze.csv")
    produtos_bronze = ler_csv(BRONZE_SAIDA / "produtos_bronze.csv")
    vendas_bronze = ler_csv(BRONZE_SAIDA / "vendas_bronze.csv")

    clientes = limpar_clientes(clientes_bronze)
    produtos = limpar_produtos(produtos_bronze)

    ids_clientes_validos = {c["id_cliente"] for c in clientes}
    ids_produtos_validos = {p["id_produto"] for p in produtos}

    vendas = limpar_vendas(vendas_bronze, ids_clientes_validos, ids_produtos_validos)

    salvar_csv(clientes, SAIDA / "clientes_silver.csv", ["id_cliente", "nome", "email", "cidade", "estado", "data_cadastro"])
    salvar_csv(produtos, SAIDA / "produtos_silver.csv", ["id_produto", "nome", "categoria", "preco", "ativo"])
    salvar_csv(vendas, SAIDA / "vendas_silver.csv", ["id_venda", "id_cliente", "id_produto", "quantidade", "data_venda", "valor_total"])

    print(f"clientes_silver.csv: {len(clientes)} linhas")
    print(f"produtos_silver.csv: {len(produtos)} linhas")
    print(f"vendas_silver.csv:   {len(vendas)} linhas")
    print("\nAgora rode: python lakehouse/silver/verificar_silver.py")


if __name__ == "__main__":
    main()
