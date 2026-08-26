# AssinaPDF — Prefeitura de Imperatriz

Aplicativo desktop em Python para aplicar uma imagem de assinatura em lote a
arquivos PDF.

> Importante: a aplicação insere uma assinatura **visual por imagem**. Isso não
> equivale a uma assinatura digital criptográfica com certificado ICP-Brasil.

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

## Executar pelo código-fonte

No terminal, dentro desta pasta:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
python app.py
```

No Windows, ative o ambiente com `.venv\Scripts\activate`.

## Uso

1. Clique em **Selecionar PDFs** para escolher arquivos individuais ou em
   **Selecionar pasta** para carregar todos os PDFs de uma pasta.
2. Escolha a imagem da assinatura (PNG, JPG ou JPEG). PNG transparente costuma
   gerar o melhor resultado.
3. Defina a página, o canto, a largura e a margem.
4. Escolha a pasta de saída, se necessário, e clique em **ASSINAR PDFs**.

Os documentos originais não são alterados: as versões assinadas ficam na pasta
`pdfs_assinados`, ao lado dos PDFs, ou na pasta de saída escolhida.

## Logo institucional

A logo da Prefeitura já está incluída em `assets/logo_pmi_branca_3.png` e é
embarcada automaticamente no executável Windows.
