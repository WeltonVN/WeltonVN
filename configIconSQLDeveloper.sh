1. Criar o script customizado
Criar o script de lançamento:

Abra um terminal e crie o script chamado launch-sqldeveloper.sh no diretório ~/bin (se o diretório não existir, você pode criá-lo com mkdir -p ~/bin):

bash
Copy code
nano ~/bin/launch-sqldeveloper.sh
Adicionar o conteúdo do script:

Copie e cole o seguinte conteúdo no arquivo launch-sqldeveloper.sh:

bash
Copy code
#!/bin/bash
JAVA_HOME=/usr/lib/jvm/java-11-oracle  # Verifique se você está usando Java 11 ou modifique conforme necessário
SQLD_HOME=/opt/sqldeveloper

# Launch Oracle's startup script asynchronously
env JAVA_HOME=$JAVA_HOME $SQLD_HOME/sqldeveloper.sh $* &

i="0"
while [ $i -lt 20 ]
do
    # Try to get SQL Developer window ID
    WIN_ID=$(xwininfo -root -tree | grep -i 'oracle sql developer' | grep -oP '(0x[a-f0-9]+)')

    # If it is non-empty (window already exists)
    if [ -n "$WIN_ID" ]
    then
        echo "WIN_ID=$WIN_ID"

        # Set WM_CLASS property of main window to same value that is used for the launcher window
        xprop -id $WIN_ID -f WM_CLASS 8s -set WM_CLASS "oracle-ide-osgi-boot-OracleIdeLauncher"

        # and exit loop
        break
    else
        # Otherwise sleep for one second and increment loop counter
        echo "Sleeping: $i"
        sleep 1s
        i=$((i+1))
    fi
done
echo "Done"
Tornar o script executável:

Agora, torne o script executável:

bash
Copy code
chmod +x ~/bin/launch-sqldeveloper.sh
2. Atualizar o arquivo .desktop
Agora, precisamos modificar o arquivo .desktop para usar o script customizado em vez de iniciar o SQL Developer diretamente.

Editar o arquivo .desktop:

Abra o arquivo .desktop:

bash
Copy code
sudo nano /usr/share/applications/sqldeveloper.desktop
Modificar a linha Exec:

Modifique a linha Exec para apontar para o script que criamos:

bash
Copy code
Exec=sh -c '$HOME/bin/launch-sqldeveloper.sh %F'
Atualizar o StartupWMClass (deixe essa linha como está):

bash
Copy code
StartupWMClass=oracle-ide-osgi-boot-OracleIdeLauncher
Salvar e fechar o arquivo.

3. Testar a solução
Agora, você pode testar a solução:

Feche completamente o SQL Developer, caso ele esteja em execução.
No menu de aplicativos, procure por "SQL Developer" e abra o aplicativo.
