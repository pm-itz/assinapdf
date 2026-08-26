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
3. Defina a página, o canto, a largura e a margem. Para escolher a posição em
   cada documento individualmente, selecione **Manual por PDF** e clique em
   **Definir posições manualmente**. Na prévia, clique no ponto em que a
   assinatura deve ficar para cada PDF. Use o controle de **Tamanho da
   assinatura neste PDF** para redimensioná-la individualmente.
4. Escolha a pasta de saída, se necessário, e clique em **ASSINAR PDFs**.

Os documentos originais não são alterados: as versões assinadas ficam na pasta
`pdfs_assinados`, ao lado dos PDFs, ou na pasta de saída escolhida.

## Logo institucional

A logo da Prefeitura já está incluída em `assets/logo_pmi_branca_3.png` e é
embarcada automaticamente nos aplicativos Windows e Linux.
