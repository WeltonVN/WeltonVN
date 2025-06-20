import os
import cx_Oracle
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração do fuso horário para Brasília
TZ = pytz.timezone('America/Sao_Paulo')

# Configuração de log
class TimezoneFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

log_handler = TimedRotatingFileHandler('processamento_imagens.log', when='H', interval=1, backupCount=7)
log_handler.setLevel(logging.INFO)
log_formatter = TimezoneFormatter('%(asctime)s - %(levelname)s - %(message)s')
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

INTERVALO = 1 * 60 * 60  # 1 hora em segundos

HORARIO_INICIO = 7  # 7:00 AM
HORARIO_FIM = 19    # 7:00 PM

def conectar_ao_oracle():
    """Conecta ao banco de dados Oracle e retorna a conexão."""
    try:
        dsn_tns = cx_Oracle.makedsn(DB_HOST, DB_PORT, service_name=DB_SERVICE)
        return cx_Oracle.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn_tns)
    except cx_Oracle.DatabaseError as e:
        error, = e.args
        logger.error("Erro ao conectar ao Oracle:")
        logger.error(f"  ORA-erro: {getattr(error, 'code', None)}")
        logger.error(f"  Mensagem: {getattr(error, 'message', repr(e))}")
        logger.error(f"  Contexto: {getattr(error, 'context', None)}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def listar_arquivos(diretorio):
    """Lista os arquivos em um diretório específico com suas datas de inclusão."""
    try:
        if not os.path.exists(diretorio):
            logger.warning(f"Diretório {diretorio} não encontrado ou não montado.")
            return []

        arquivos = []
        for f in os.listdir(diretorio):
            if not os.path.isfile(os.path.join(diretorio, f)):
                continue
            codprod = os.path.splitext(f)[0]
            extensao = os.path.splitext(f)[1].lstrip('.').lower()  # padroniza extensão
            data_inclusao = datetime.fromtimestamp(os.path.getmtime(os.path.join(diretorio, f)))
            # Verifica se o nome do arquivo é numérico
            if not codprod.isdigit():
                logger.info(f"Arquivo ignorado (não numérico): {f}")
                continue
            arquivos.append((int(codprod), extensao, data_inclusao))

        return arquivos
    except Exception as e:
        logger.error(f"Erro ao listar arquivos no diretório {diretorio}: {repr(e)}")
        raise

def filtrar_unicos_por_codprod(arquivos):
    """
    Mantém apenas um arquivo por CODPROD (mais recente).
    """
    arquivos_unicos = {}
    for codprod, extensao, data_inclusao in arquivos:
        if codprod not in arquivos_unicos or data_inclusao > arquivos_unicos[codprod][1]:
            arquivos_unicos[codprod] = (extensao, data_inclusao)
    return [(codprod, ext, dt) for codprod, (ext, dt) in arquivos_unicos.items()]

def preencher_tabela_temporaria(conexao, arquivos):
    """Preenche a tabela temporária com os dados do diretório."""
    try:
        with conexao.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE hub.TMP_IONV_IMAGENS")
            logger.info("Tabela hub.TMP_IONV_IMAGENS truncada com sucesso.")

            sql_insert = """
                INSERT INTO hub.TMP_IONV_IMAGENS (CODPROD, EXTENSAO, DTA_ATUALIZACAO)
                VALUES (:1, :2, :3)
            """
            cursor.executemany(sql_insert, arquivos)
            conexao.commit()
            logger.info(f"{len(arquivos)} registros inseridos na tabela temporária.")
    except cx_Oracle.DatabaseError as e:
        error, = e.args
        logger.error("Erro ao preencher a tabela temporária:")
        logger.error(f"  ORA-erro: {getattr(error, 'code', None)}")
        logger.error(f"  Mensagem: {getattr(error, 'message', repr(e))}")
        logger.error(f"  Contexto: {getattr(error, 'context', None)}")
        import traceback
        logger.error(traceback.format_exc())
        conexao.rollback()
        raise

def executar_merge_e_delete(conexao):
    """Executa o MERGE e DELETE para sincronizar as tabelas."""
    try:
        with conexao.cursor() as cursor:
            # MERGE: Insere ou atualiza os registros
            merge_sql = """
                MERGE INTO hub.IONV_IMAGENS_EXT tgt
                USING hub.TMP_IONV_IMAGENS src
                ON (tgt.CODPROD = src.CODPROD)
                WHEN MATCHED THEN
                    UPDATE SET
                        tgt.EXTENSAO = src.EXTENSAO,
                        tgt.DTA_ATUALIZACAO = src.DTA_ATUALIZACAO
                    WHERE tgt.EXTENSAO != src.EXTENSAO
                       OR tgt.DTA_ATUALIZACAO != src.DTA_ATUALIZACAO
                WHEN NOT MATCHED THEN
                    INSERT (CODPROD, EXTENSAO, DTA_ATUALIZACAO)
                    VALUES (src.CODPROD, src.EXTENSAO, src.DTA_ATUALIZACAO)
            """
            cursor.execute(merge_sql)
            logger.info("MERGE executado com sucesso.")

            # DELETE: Remove os registros que existem na produção, mas não estão na origem
            delete_sql = """
                DELETE FROM hub.IONV_IMAGENS_EXT tgt
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM hub.TMP_IONV_IMAGENS src
                    WHERE tgt.CODPROD = src.CODPROD
                )
            """
            cursor.execute(delete_sql)
            logger.info("DELETE executado com sucesso.")

            conexao.commit()
    except cx_Oracle.DatabaseError as e:
        error, = e.args
        logger.error("Erro ao executar MERGE/DELETE no Oracle:")
        logger.error(f"  ORA-erro: {getattr(error, 'code', None)}")
        logger.error(f"  Mensagem: {getattr(error, 'message', repr(e))}")
        logger.error(f"  Contexto: {getattr(error, 'context', None)}")
        import traceback
        logger.error(traceback.format_exc())
        conexao.rollback()
        raise

def calcular_tempo_espera():
    """Calcula o tempo de espera até o próximo horário permitido."""
    agora = datetime.now(tz=TZ)
    if agora.hour >= HORARIO_FIM or agora.hour < HORARIO_INICIO:
        if agora.hour >= HORARIO_FIM:
            proximo_inicio = (agora + timedelta(days=1)).replace(hour=HORARIO_INICIO, minute=0, second=0, microsecond=0)
        else:
            proximo_inicio = agora.replace(hour=HORARIO_INICIO, minute=0, second=0, microsecond=0)
        tempo_espera = (proximo_inicio - agora).total_seconds()
        logger.info(f"Fora do horário permitido. Aguardando até {proximo_inicio}.")
        return tempo_espera
    return 0

def main():
    """Função principal para orquestrar o processo."""
    while True:
        try:
            tempo_espera = calcular_tempo_espera()
            if tempo_espera > 0:
                time.sleep(tempo_espera)

            logger.info("Iniciando processamento de arquivos do repositório.")

            arquivos = listar_arquivos(REPOSITORIO)
            if not arquivos:
                logger.info("Nenhum arquivo encontrado no diretório.")
            else:
                logger.info(f"{len(arquivos)} arquivos encontrados no diretório.")

                arquivos = filtrar_unicos_por_codprod(arquivos)
                logger.info(f"{len(arquivos)} arquivos únicos (por CODPROD) serão inseridos.")

                conexao = conectar_ao_oracle()
                try:
                    preencher_tabela_temporaria(conexao, arquivos)
                    executar_merge_e_delete(conexao)
                finally:
                    conexao.close()
                    logger.info("Conexão com o banco de dados encerrada.")

        except Exception as e:
            import traceback
            logger.error(f"Erro no processamento: {repr(e)}")
            logger.error(traceback.format_exc())

        logger.info("Processamento finalizado. Aguardando próxima execução.")
        time.sleep(INTERVALO)

if __name__ == "__main__":
    main()
