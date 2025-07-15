import pandas as pd
import requests
from sqlalchemy import create_engine
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import date
import traceback
import urllib
from pathlib import Path

def get_sql_server_connection_str():
    """Retorna a string de conexão com o banco de dados SQL Server."""
    user = 'rpa_bi'
    password = 'Rp@_B&_P@rvi'
    host = '10.0.10.243'
    port = '54949'
    database = 'stage'
    
    params = urllib.parse.quote_plus(
        f'DRIVER=ODBC Driver 17 for SQL Server;SERVER={host},{port};DATABASE={database};UID={user};PWD={password}')
    conn_str = f'mssql+pyodbc:///?odbc_connect={params}'
    return conn_str

def FIPE():
    try:
        conn_str = get_sql_server_connection_str()
        engine = create_engine(conn_str)
        
        inicio_query = time.time()
        query = "SELECT DISTINCT CAST(Fipe_Id AS VARCHAR(MAX)) AS Fipe_Id FROM [stage].[camada0].[AutoAvaliar_AvaliacoesTotais]"
        df_fipe = pd.read_sql(query, engine)
        fim_query = time.time()
        print(f"Tempo para carregar dados do banco com DISTINCT: {fim_query - inicio_query:.2f} segundos")
        
        lista_fipes = df_fipe['Fipe_Id'].dropna().tolist()
        
        def consultar_api(codigo_fipe, max_tentativas=3):
            url = f"https://brasilapi.com.br/api/fipe/preco/v1/{codigo_fipe}"
            tentativas = 0
            while tentativas < max_tentativas:
                try:
                    response = requests.get(url, timeout=10)
                    if response.status_code == 200:
                        dados = response.json()
                        resultados = []
                        for dado in dados:
                            resultados.append({
                                "Fipe_Codigo": codigo_fipe,
                                "valor": dado.get("valor"),
                                "marca": dado.get("marca"),
                                "modelo": dado.get("modelo"),
                                "anoModelo": dado.get("anoModelo"),
                                "combustivel": dado.get("combustivel"),
                                "mesReferencia": dado.get("mesReferencia"),
                                "tipoVeiculo": dado.get("tipoVeiculo"),
                                "siglaCombustivel": dado.get("siglaCombustivel")
                            })
                        return resultados
                    else:
                        print(f"Erro ao consultar {codigo_fipe} - Tentativa {tentativas + 1}: {response.status_code}")
                except Exception:
                    print(f"Erro no código {codigo_fipe} - Tentativa {tentativas + 1}: {traceback.format_exc()}")
                tentativas += 1
                time.sleep(2 ** tentativas)
            return None
        
        inicio_api = time.time()
        resultados_finais = []
        codigos_falharam = []
        max_workers = min(10, len(lista_fipes))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(consultar_api, codigo): codigo for codigo in lista_fipes}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        resultados_finais.extend(result)
                    else:
                        codigos_falharam.append(futures[future])
                except Exception:
                    print(f"Erro ao processar futuro: {traceback.format_exc()}")
        
        fim_api = time.time()
        print(f"Tempo para consumir API: {fim_api - inicio_api:.2f} segundos")
        
        if resultados_finais:
            df_resultados = pd.DataFrame(resultados_finais)
            df_resultados['data_atualizacao'] = date.today()
            print("Resultados obtidos da API:")
            print(df_resultados.head())
            
            inicio_insercao = time.time()
            df_resultados.to_sql("AutoAvaliar_Fipe_Resultados", engine, if_exists="replace", index=False, chunksize=1000)
            fim_insercao = time.time()
            
            print(f"Tempo para inserir dados no banco: {fim_insercao - inicio_insercao:.2f} segundos")
            print("Dados inseridos na tabela 'AutoAvaliar_Fipe_Resultados'.")
        else:
            print("Nenhum dado foi obtido da API.")
        
        if codigos_falharam:
            codigos_validos = [codigo for codigo in codigos_falharam if isinstance(codigo, str) and codigo.strip()]
            if codigos_validos:
                print("Códigos que falharam na primeira tentativa:")
                print(codigos_validos)
                
                # Caminho dinâmico para Downloads do usuário atual
                downloads_path = Path("C:/Users/adm.luiz.vinicius/Downloads")
                file_path = downloads_path / "codigos_falharam.txt"

                with open(file_path, "w", encoding="utf-8") as file:
                    for codigo in codigos_validos:
                        file.write(codigo + "\n")

                print(f"Arquivo salvo dinamicamente em: {file_path}")
            else:
                print("Nenhum código válido para salvar.")
    except Exception:
        print(f"Erro na função FIPE: {traceback.format_exc()}")

# Execução direta da função
if __name__ == "__main__":
    FIPE()
