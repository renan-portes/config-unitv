# 📋 Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.4.0] - 27-08-2026
### 🚀 Funcionalidades & Otimizações (Performance Leap)
- **Smart Wipe Engine:** Substituição do `pm clear` destrutivo pela limpeza cirúrgica de caches ocultos. Redução do tempo de injeção e leitura ADB de ~70s para ~13s por configuração.
- **Bypass Semântico (UiAutomator):** Novo motor de processamento XML em memória para localização dinâmica e bypass de tutoriais, pop-ups e cliques baseados em semântica de texto (abandonando coordenadas fixas).
- **OCR com Teimosia Automática:** Aumento da tolerância e normalização de entidades HTML e quebras de linha (`\n`) garantindo precisão absoluta na leitura de contas antigas e virgens.
- **Nomenclatura Estrita:** As exportações em lote agora seguem um padrão ultra-limpo: `CONFIG_{IDCONTA}_{DIAS}DIAS`.

### 🐛 Correções de Bugs
- Correção do botão 'Injetar no ADB' da aba Individual, refatorado para ler e transmitir apenas o conteúdo de `cache.config.xml`.
- Remoção total da geração inútil dos arquivos legados `.config` e `.properties` na exportação final.

---

## [1.3.1] - 2026-08-26

### ✨ Adicionado
- **🛡️ Concessão Automática de Permissões no Android 12 a 15 (`grant_all_app_permissions`):** Concede automaticamente via ADB todas as permissões de armazenamento, música e áudio (`READ_MEDIA_AUDIO`, `READ_MEDIA_IMAGES`, `MANAGE_EXTERNAL_STORAGE`) no MuMu Player e Android modernos, eliminando telas de bloqueio de permissão.
- **📦 Ferramentas ADB Portáteis Embutidas (`tools/`):** Inclusão de `adb.exe`, `AdbWinApi.dll` e `AdbWinUsbApi.dll` diretamente no projeto e dentro do executável `.exe`. Usuários não precisam mais instalar o Android SDK nem configurar o PATH do Windows.
- **🎮 Suporte Nativo ao MuMu Player:** Detecção e conexão automática nas portas `127.0.0.1:16384` (MuMu Player 12 / Pro) e `127.0.0.1:7555` (MuMu Player 6).
- **📐 Detecção Dinâmica de Resolução de Tela (`wm size`):** Cálculo proporcional de coordenadas de toque para abrir o perfil do aplicativo automaticamente em telas 720p (1280x720), 1080p (1920x1080), 2K, 4K e resoluções customizadas sem falhas de clique.
- **🔄 Auto-Descoberta Multi-Emuladores:** Varredura automática nas portas locais `21503`, `21513`, `21523`, `16384`, `16416`, `7555`, `5555`, `62001`.

### 🐛 Corrigido
- **Telas de Permissão no Android 12-15:** Resolvido o travamento no diálogo *"Permitir que a app UniTV Free aceda a música e áudio"* no MuMu Player.
- **Falha de Clique no Perfil:** Resolvido o problema onde alguns emuladores com resolução diferente de 1280x720 não abriam a tela de perfil automaticamente.
- **Erro `'adb' não é reconhecido`:** Resolvido com o localizador inteligente de binários ADB (`get_adb_cmd()`).
- **Device ADB Dinâmico:** Injeção e scanner agora respeitam 100% o IP/porta conectado sem fallback fixo para `21503`.

---

## [1.3.0] - 2026-08-26

### ✨ Adicionado
- **📦 Compilação Standalone em Executável (`dist/Gerador_IPTV.exe`):** Aplicativo portátil de 1 clique contendo backend FastAPI, Uvicorn, interface Web e criptografia embutida.
- **🎲 Sorteio Completo de 3 Octetos (`9C:00:D3:XX:YY:ZZ`):** Mais de 16,7 milhões de combinações possíveis para geração de MACs aleatórios e sequenciais.
- **☁️ Geração em Lote Simplificada (2 Origens):**
  - *Opção 1: Puxar da Nuvem (10k)* – Puxa configurações originais do pool de 10.231 configs sem modificar nada.
  - *Opção 2: Gerador Aleatório* – Prefixo `9C:00:D3:` com incremento sequencial (+1).
- **📥 Download em Massa (.ZIP):** Exportação de 10 a 500 pacotes de configurações compactados em um único arquivo.

### 📚 Documentação
- Reescrita completa do `README.md` com guia passo a passo, download do executável, tabela de portas e FAQ.

---

## [1.2.0] - 2026-08-25

### ✨ Adicionado
- **🎨 Interface Web Moderna:** Redesign visual com TailwindCSS, tema Dark Glassmorphism e ícones Lucide.
- **📲 Scanner e Validador ADB:** Automação para testar contas em lote no emulador, ler data de ativação e filtrar por meta de dias (≤0d, ≤30d, ≤70d, ≤100d).
- **🌐 Utilitário de Túnel Remoto (`Conectar_Emulador_Remoto.bat`):** Permite conectar emuladores de computadores locais a instâncias em VPS/Nuvem (`config.servidor.xyz.br`).
- **📦 Central de Aplicativos:** Aba para download direto dos APKs e versões de suporte.

---

## [1.1.0] - 2026-08-24

### ✨ Adicionado
- **🔐 Motor Criptográfico DES:** Suporte completo à criptografia/descriptografia de tokens `KEY_SP_SN` e `KEY_DEV_ID`.
- **📄 Geração Tripla:** Exportação simultânea de `.config`, `.properties` e `cache.config.xml`.
- **🔓 Decodificador Hexadecimal Embutido:** Ferramenta para decodificação de payloads e tokens na interface.

---

## [1.0.0] - 2026-08-20

### 🚀 Lançamento Inicial
- Criação do gerador básico de configurações `.config`.
- Suporte a Docker e deploy via Portainer Stacks.
