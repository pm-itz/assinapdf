# AssinaPDF — Prefeitura de Imperatriz

Aplicativo desktop em Python para aplicar uma imagem de assinatura em lote a
arquivos PDF.

> Importante: a aplicação insere uma assinatura **visual por imagem**. Isso não
> equivale a uma assinatura digital criptográfica com certificado ICP-Brasil.

## Executar no Linux

O código da aplicação é multiplataforma. No Ubuntu ou Debian, instale primeiro
o Python, o suporte ao Tkinter e a criação de ambientes virtuais:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-tk
```

Em seguida, dentro desta pasta:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

No Fedora, o pacote gráfico se chama `python3-tkinter`; no Arch Linux e no
Manjaro, instale-o com `sudo pacman -S tk`.
Como é uma aplicação desktop, ela precisa ser executada em uma sessão gráfica
(X11 ou Wayland), não em um terminal remoto sem acesso a uma tela.

## Gerar um aplicativo portátil para Linux

Para gerar uma versão que não exige Python no computador de destino:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

O resultado fica em `dist/AssinaPDF/`. Distribua a pasta inteira e execute
`dist/AssinaPDF/AssinaPDF`. O build deve ser feito no Linux e, de preferência,
em uma distribuição tão antiga quanto a mais antiga que receberá o aplicativo,
por causa da compatibilidade da glibc.

O binário gerado é específico da arquitetura usada no build (por exemplo,
x86_64 ou ARM64). O PyInstaller não gera o aplicativo Linux a partir do
Windows; cada versão deve ser compilada em seu próprio sistema operacional.

## Gerar o instalador do Windows

Em um computador Windows, instale o [Python 3.10 ou superior](https://www.python.org/downloads/windows/)
e o [Inno Setup 6](https://jrsoftware.org/isdl.php). Depois, dê duplo clique em
`build_windows.bat`.

O processo gera:

- `dist\AssinaPDF\AssinaPDF.exe`: aplicativo portátil;
- `release\AssinaPDF-Setup.exe`: instalador para distribuir aos usuários.

O instalador cria atalhos no Menu Iniciar e oferece, opcionalmente, um atalho
na Área de Trabalho. Ele não exige Python na máquina de quem for usar o
aplicativo.

Além de `release\AssinaPDF-Setup.exe`, o script copia o instalador para a Área
de Trabalho de quem executou a compilação, facilitando sua distribuição e
instalação.

## Atualizações pelo aplicativo (Windows)

No menu **Ajuda > Verificar atualizações**, o AssinaPDF consulta a Release mais
recente do repositório oficial no GitHub. Quando houver uma versão mais nova,
o usuário confirma uma vez; o aplicativo baixa o instalador oficial, inicia a
atualização e fecha para concluir a instalação.

Para publicar uma atualização, altere `APP_VERSION` em `app.py` e
`MyAppVersion` em `installer.iss`, gere `AssinaPDF-Setup.exe` no Windows e
publique uma GitHub Release com a tag `v1.1.6`. Anexe ao Release
o arquivo com o nome exato `AssinaPDF-Setup.exe`.

## Executar pelo código-fonte no Windows

No terminal, dentro desta pasta:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python app.py
```

## Uso

1. Clique em **Selecionar PDFs** para escolher arquivos individuais ou em
   **Selecionar pasta** para carregar todos os PDFs de uma pasta.
2. Escolha a imagem da assinatura (PNG, JPG ou JPEG). PNG transparente costuma
   gerar o melhor resultado.
3. Escolha uma **Posição padrão** e clique em **Pré-visualizar posição padrão**
   para conferir o resultado antes de assinar. Essa é a opção mais simples e
   aplica o mesmo canto a todo o lote.
4. Em **Aplicar em**, escolha a primeira, a última, todas ou um **Intervalo
   personalizado**. Para o intervalo, informe páginas como `1-3, 5, 8-10`.
5. Somente se necessário, ative **Quero ajustar a posição manualmente**.
   Na janela de ajuste, escolha as **Páginas para assinatura manual**. Essa
   seleção é independente da posição padrão e também aceita um intervalo como
   `1-3, 5`. Use os controles **← Página** e **Página →** para visualizar as
   páginas escolhidas. Marque a opção **Usar a mesma posição e
   tamanho em todos os PDFs** para definir uma única escolha para o lote
   inteiro. Desmarque-a apenas se os documentos realmente precisarem de
   ajustes diferentes; os botões **Anterior** e **Próximo** serão exibidos.
6. Na prévia manual, clique no local desejado e ajuste o controle de tamanho.
   Os controles ficam acima da página e a visualização é centralizada.
7. Escolha a pasta de saída, se necessário, e clique em **ASSINAR PDFs**.

Os documentos originais não são alterados: as versões assinadas ficam na pasta
`pdfs_assinados`, ao lado dos PDFs, ou na pasta de saída escolhida.

## Logo institucional

A logo da Prefeitura já está incluída em `assets/logo_pmi_branca_3.png` e é
embarcada automaticamente nos aplicativos Windows e Linux.
