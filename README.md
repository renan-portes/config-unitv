<div align="center">
  <img src="logo.png" alt="Logo" width="120" style="border-radius: 20px;" />
  <h1>⚡ Gerador de Configurações IPTV & Painel ADB</h1>
  <p>Gerador moderno, rápido e completo de arquivos <code>.config</code>, <code>.properties</code> e <code>cache.config.xml</code> com interface web responsiva, suporte a geração em lote, pool da nuvem de 10.000+ arquivos, scanner automático e injeção direta via ADB no emulador.</p>

  <p>
    <a href="https://github.com/renan-portes/config-unitv/releases"><img src="https://img.shields.io/badge/Download-Execut%C3%A1vel_.EXE_(Windows)-6366f1?style=for-the-badge&logo=windows" alt="Download Executavel Windows" /></a>
    <a href="https://pixgg.com.br/rzao"><img src="https://img.shields.io/badge/Apoiar-PixGG-10b981?style=for-the-badge&logo=pix" alt="Apoiar com Pix" /></a>
  </p>
</div>

---

> [!TIP]
> **Você não precisa instalar Python nem configurar nada!**  
> Se você quer apenas usar o gerador no seu computador, baixe o executável pronto na aba [**Releases**](https://github.com/renan-portes/config-unitv/releases) (`Gerador_IPTV.exe`), dê dois cliques e o painel abrirá automaticamente no seu navegador!

---

## 📑 Sumário

1. [📥 Como Baixar e Executar](#-como-baixar-e-executar)
2. [🕹️ Como Funciona o Gerador](#-como-funciona-o-gerador)
   - [Geração Individual](#1-gerador-individual)
   - [Geração em Lote (Download em .ZIP)](#2-gerador-em-lote-massa)
3. [🔌 Guia Completo: Conexão ADB ao Emulador Android](#-guia-completo-conexão-adb-ao-emulador-android)
   - [Tabela de Portas dos Emuladores](#tabela-de-portas-adb-dos-emuladores)
   - [Conectar no PC Local](#modo-a-usando-o-gerador-no-seu-pc-local)
   - [Conectar a um Servidor Remoto / VPS](#modo-b-usando-o-gerador-em-um-sitevps-remoto-ex-configservidorxyzbr)
4. [❓ Perguntas Frequentes & Resolução de Problemas (FAQ)](#-perguntas-frequentes--resolução-de-problemas-faq)
5. [🐳 Instalação Avançada (Docker / Portainer / Código-Fonte)](#-instalação-avançada-docker--portainer)
6. [🤝 Como Contribuir](#-como-contribuir-pull-requests)
7. [💖 Apoie o Projeto](#-apoie-o-projeto)

---

## 📥 Como Baixar e Executar

### Opção 1: Executável Standalone `.exe` (Mais Fácil / Recomendado)
1. Acesse a página de [**Releases do GitHub**](https://github.com/renan-portes/config-unitv/releases).
2. Baixe o arquivo **`Gerador_IPTV.exe`**.
3. Dê **dois cliques** no arquivo baixado:
   - O servidor iniciará automaticamente em segundo plano.
   - Seu navegador abrirá instantaneamente em `http://localhost:8000`.

### Opção 2: Pelo Código-Fonte no Windows
1. Baixe o ZIP deste repositório e extraia em qualquer pasta.
2. Dê dois cliques em **`Iniciar_Gerador.bat`**.
   - O script verificará o Python, instalará as dependências e abrirá o navegador.

---

## 🕹️ Como Funciona o Gerador

O painel foi desenhado para ser intuitivo e conta com duas ferramentas principais na aba **Gerador**:

### 1. Gerador Individual
Ideal para quem quer inspecionar, editar manualmente e testar uma configuração específica:
- **Prefixo Travado `9C:00:D3:`**: Garante o padrão nativo dos dispositivos.
- **Sorteio dos 3 Octetos Finais**: Sorteia combinações de `00` a `FF` para os octetos finais (`XX:YY:ZZ`), gerando mais de 16,7 milhões de combinações possíveis.
- **Preview em Tempo Real**: Visualize os arquivos `.config`, `.properties` e `cache.config.xml` gerados com criptografia DES em tempo real.
- **Ações Rápidas**:
  - **Baixar Pacote (.ZIP)**: Baixa a pasta pronta com os 3 arquivos necessários.
  - **Injetar no Emulador**: Se o seu emulador estiver conectado via ADB, injeta a configuração e abre o app com 1 clique!

---

### 2. Gerador em Lote (Massa)
Ideal para gerar ou baixar múltiplos pacotes de 10 a 500 configurações de uma só vez para testar no emulador ou baixar em `.ZIP`:

- **☁️ Opção 1: Puxar da Nuvem (10k)** *(Padrão)*:
  - Sorteia a quantidade selecionada do pool de **10.231 configurações originais**.
  - Mantém o **MAC real**, **Device ID original** e o **User ID** intactos sem qualquer alteração.
- **✨ Opção 2: Gerador Aleatório (Novas Contas / 0 Dias)**:
  - Cria novas configurações com o prefixo **`9C:00:D3:`**.
  - Permite informar um MAC Base customizado ou sortear, com suporte ao **Incremento Sequencial (+1)** (ex: `...01`, `...02`, `...03`...).
- **Exportação:** Clique em **`Baixar Lote Completo (.ZIP)`** para salvar todas as pastas organizadas (`CONFIG_1`, `CONFIG_2`, etc.) em um único arquivo compactado.

---

## 🔌 Guia Completo: Conexão ADB ao Emulador Android

O **ADB (Android Debug Bridge)** é o protocolo que permite ao gerador transferir os arquivos `.config` diretamente para a memória do aplicativo no emulador e testar o funcionamento da conta sem precisar fazer nada manualmente.

### Tabela de Portas ADB dos Emuladores:

| Emulador | Endereço / Porta Padrão | Observações |
|---|---|---|
| **MuMu Player 12 / Pro** | `127.0.0.1:16384` | Instância 0 (`16384`), Instância 1 (`16416`)... |
| **MuMu Player 6** | `127.0.0.1:7555` | Versão clássica do MuMu Player |
| **MEmu Play** | `127.0.0.1:21503` | Instância 1 (`21503`), Instância 2 (`21513`)... |
| **LDPlayer 9 / 4** | `127.0.0.1:5555` | Em instâncias extras, pode ser `5556`, `5558`... |
| **NoxPlayer** | `127.0.0.1:62001` | Em multi-instância pode usar `62025` |
| **BlueStacks 5** | `127.0.0.1:5555` | Requer ativar "Depuração ADB" nas configurações |
| **SmartGaGa** | `127.0.0.1:5555` | Porta padrão Android |

> [!IMPORTANT]
> **Ordem Recomendada de Inicialização:**  
> 1. Abra e aguarde o seu **Emulador Android carregar totalmente ANTES de abrir o executável** (`Gerador_IPTV.exe`).  
> 2. Ao abrir o executável com o emulador já ligado, a detecção e conexão ADB ocorrem de forma **100% automática**.  
> *(Se você ligou o emulador depois do executável já estar aberto, basta ir na aba **"Conexão ADB & Aplicativos"** e clicar no botão **"Reconectar ADB"**).*

---

### MODO A: Usando o Gerador no seu PC Local (`localhost:8000` ou `.exe`)

1. Abra o seu emulador Android (ex: MuMu, LDPlayer, MEmu, Nox) e aguarde carregar a tela inicial.
2. Abra o **`Gerador_IPTV.exe`** ou acesse `http://localhost:8000`.
3. O painel detectará o emulador automaticamente com o badge verde **`Conectado`**.
4. Pronto! Você já pode usar a injeção com 1 clique e rodar o **Scanner de Contas**.

---

### MODO B: Usando o Gerador em um Site/VPS Remoto (ex: `config.servidor.xyz.br`)

Se o gerador estiver hospedado em um servidor web na nuvem (VPS/Docker), o servidor não consegue enxergar o `127.0.0.1` do seu computador local diretamente. Para resolver isso:

1. Baixe e dê dois cliques no arquivo **[`Conectar_Emulador_Remoto.bat`](file:///d:/workspace/config/Conectar_Emulador_Remoto.bat)** no seu computador.
2. Escolha o seu emulador (1 para MEmu, 2 para Nox, 3 para LDPlayer).
3. O script iniciará um túnel seguro e exibirá um endereço público, por exemplo:
   ```text
   tcp.pinggy.io:48921
   ```
4. **Copie esse endereço** e cole no campo **"Endereço do Dispositivo ADB"** no site do gerador.
5. Clique em **Conectar**. Agora o site remoto conseguirá injetar e escanear contas diretamente no emulador do seu computador!

---

## ❓ Perguntas Frequentes & Resolução de Problemas (FAQ)

### 1. O painel diz "Nenhum dispositivo ADB conectado". O que fazer?
- Certifique-se de que o emulador está aberto e totalmente carregado antes de clicar em conectar.
- Verifique se a porta corresponde ao seu emulador (consulte a [Tabela de Portas](#tabela-de-portas-adb-dos-emuladores)).
- Nas configurações do seu emulador, certifique-se de que a opção **"Depuração ADB"** ou **"Root"** está ativada.

### 2. O que o botão "Injetar" faz exatamente?
Ele envia os arquivos `.config` e `.properties` para o diretório de dados do aplicativo no Android (`/data/data/com.unitv.free/...`), limpa caches corrompidos e executa o aplicativo para carregar as informações.

### 3. Como passar as pastas do `.ZIP` para o emulador manualmente se eu não quiser usar ADB?
Você pode abrir o emulador, instalar um gerenciador de arquivos (ex: *FX File Explorer* ou *ZArchiver*) e colar a pasta `CONFIG_X` no diretório compartilhado do seu emulador no Windows (geralmente `C:\Users\SeuUsuario\Downloads` ou pasta compartilhada do MEmu/LDPlayer).

---

## 🐳 Instalação Avançada (Docker / Portainer)

### Com Docker Compose:
```bash
docker compose up -d --build
```
Acesse no navegador: **`http://localhost:8095`**

### No Portainer (Stacks):
1. No Portainer, vá em **Stacks** ➔ **Add stack**.
2. Selecione **Repository** e informe a URL:
   ```text
   https://github.com/renan-portes/config-unitv.git
   ```
3. Defina o Compose path como `docker-compose.yml` e clique em **Deploy the stack**.

---

## 🤝 Como Contribuir (Pull Requests)

Se você descobriu melhorias de código, otimizações criptográficas ou novos métodos para validação de contas, sinta-se à vontade para enviar um **Pull Request (PR)**!

1. Faça um **Fork** deste repositório.
2. Crie uma branch com a sua melhoria (`git checkout -b feature/minha-melhoria`).
3. Commit suas alterações (`git commit -m "feat: minha melhoria"`).
4. Faça o push para o seu fork (`git push origin feature/minha-melhoria`).
5. Abra um **Pull Request** no GitHub.

---

## 💖 Apoie o Projeto

Se este gerador e as ferramentas automatizadas facilitaram o seu trabalho, você pode apoiar o desenvolvimento contínuo via Pix:

<div align="center">
  <a href="https://pixgg.com.br/rzao">
    <img src="https://img.shields.io/badge/Apoiar%20com%20Pix-PixGG%20%2F%20rzao-10b981?style=for-the-badge&logo=pix" alt="Doar via Pix" />
  </a>
  <p><b>Chave Pix / Link:</b> <a href="https://pixgg.com.br/rzao">https://pixgg.com.br/rzao</a></p>
</div>

---

## 📄 Licença

Distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
