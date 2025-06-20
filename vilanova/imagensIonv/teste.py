import os
import cx_Oracle
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração de log
log_handler = TimedRotatingFileHandler('processamento_imagens.log', when='D', interval=1, backupCount=7)
log_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

# Detalhes de conexão com o banco
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_SERVICE = os.getenv("DB_SERVICE")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Caminho da pasta montada
REPOSITORIO = os.getenv("MOUNT_POINT")

INTERVALO = 60 * 60  # 60 minutos em segundos

def conectar_ao_oracle():
    """Conecta ao banco de dados Oracle e retorna a conexão."""
    try:
        dsn_tns = cx_Oracle.makedsn(DB_HOST, DB_PORT, service_name=DB_SERVICE)
        return cx_Oracle.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn_tns)
    except cx_Oracle.DatabaseError as e:
        logger.error(f"Erro ao conectar ao Oracle: {repr(e)}")
        raise

def listar_arquivos(diretorio):
    """Lista os arquivos em um diretório específico."""
    try:
        return [(os.path.splitext(f)[0], os.path.splitext(f)[1].lstrip('.'))
                for f in os.listdir(diretorio) if os.path.isfile(os.path.join(diretorio, f))]
    except Exception as e:
        logger.error(f"Erro ao listar arquivos no diretório {diretorio}: {repr(e)}")
        raise

def processar_dados(conexao, dados):
    """Processa os dados, realizando insert ou update conforme o caso."""
    sql_insert = """
        INSERT INTO hub.IONV_IMAGENS_EXT (CODPROD, extensao, dta_atualizacao)
        SELECT :codprod, :extensao, SYSDATE FROM DUAL
        WHERE NOT EXISTS (
            SELECT 1 FROM hub.IONV_IMAGENS_EXT 
            WHERE CODPROD = :codprod AND extensao = :extensao
        )
    """

    sql_update = """
        UPDATE hub.IONV_IMAGENS_EXT
        SET dta_atualizacao = SYSDATE
        WHERE CODPROD = :codprod AND extensao = :extensao
    """

    try:
        with conexao.cursor() as cursor:
            for codprod, extensao in dados:
                cursor.execute(sql_update, {
                    'codprod': codprod,
                    'extensao': extensao
                })
                if cursor.rowcount == 0:  # Nenhuma linha foi atualizada, insere novo registro
                    cursor.execute(sql_insert, {
                        'codprod': codprod,
                        'extensao': extensao
                    })
            conexao.commit()
            logger.info(f"{len(dados)} registros processados no banco de dados.")
    except cx_Oracle.DatabaseError as e:
        logger.error(f"Erro ao processar dados no Oracle: {repr(e)}")
        conexao.rollback()
        raise

def main():
    """Função principal para orquestrar o processo."""
    while True:
        try:
            logger.info("Iniciando processamento de arquivos do repositório.")

            # Listar arquivos no diretório montado
            arquivos = listar_arquivos(REPOSITORIO)
            if not arquivos:
                logger.info("Nenhum arquivo encontrado no diretório.")
            else:
                logger.info(f"{len(arquivos)} arquivos encontrados no diretório.")

                # Conectar ao banco de dados
                conexao = conectar_ao_oracle()

                # Processar dados no banco de dados
                processar_dados(conexao, arquivos)

        except Exception as e:
            logger.error(f"Erro no processamento: {repr(e)}")
        finally:
            if 'conexao' in locals() and conexao:
                conexao.close()
            logger.info("Processamento finalizado. Aguardando 60 minutos para reiniciar.")

        time.sleep(INTERVALO)

if __name__ == "__main__":
    main()
