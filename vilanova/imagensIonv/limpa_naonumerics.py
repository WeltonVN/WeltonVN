import os

# Defina aqui o diretório a ser limpo
DIRETORIO = "/mnt/imagensIonv"  # <-- Altere para o caminho da sua pasta

# Simulação: True = só mostra, False = apaga de verdade
DRY_RUN = False

# Lista para mostrar ao final
apagados = []

for arquivo in os.listdir(DIRETORIO):
    caminho = os.path.join(DIRETORIO, arquivo)
    if not os.path.isfile(caminho):
        continue
    nome, _ = os.path.splitext(arquivo)
    # Remove espaços extras do nome para isdigit() funcionar corretamente
    nome = nome.strip()
    if not nome.isdigit():
        apagados.append(arquivo)
        if DRY_RUN:
            print(f"[Simulação] Arquivo seria apagado: {arquivo}")
        else:
            try:
                os.remove(caminho)
                print(f"[APAGADO] {arquivo}")
            except Exception as e:
                print(f"[ERRO] Falha ao apagar {arquivo}: {e}")

print()
print(f"Total de arquivos não numéricos encontrados: {len(apagados)}")
if DRY_RUN:
    print("Nada foi apagado (DRY_RUN=True).")
else:
    print("Arquivos apagados com sucesso.")
