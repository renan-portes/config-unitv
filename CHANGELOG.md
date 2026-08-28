# 📋 Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [1.5.0] - 27-08-2026
### 🚀 Inteligência Coletiva, Multi-tenant & Autenticação SaaS
- **Seleção em Massa e Download Personalizado no Cofre:** Adição de checkboxes individuais e cabeçalho mestre ("selecionar todos os visíveis") na tabela do Cofre, com o novo botão "Baixar Selecionadas (.ZIP)" gerando pacotes compactados dinamicamente via JSZip.
- **Renomeação Semântica de Exportação:** Atualização do botão de exportação global de contas virgens para "Exportar 0 Dias (.ZIP)".
- **Modal 'Meu Perfil' & Troca de Senha:** Novo modal de autoatendimento para o usuário conectado com exibição de nome, permissão e prazo de validade da assinatura (`expires_at`), acompanhado de formulário seguro para redefinição de senha com validação de senha atual via `PUT /api/auth/me/password`.
- **Ordenação Interativa e Multicoluna no Cofre:** Cabeçalhos clicáveis na tabela do Cofre (`Endereço MAC`, `ID da Conta`, `Dias Ativos`, `Status`, `Data do Teste`, `Usuário`) com ordenação ascendente/descendente e indicadores visuais dinâmicos (`▲`, `▼`, `↕`).
- **Filtros Avançados Combinados no Cofre:** Novos seletores dropdown de 'Dias Ativos' (Virgens 0 Dias, Ativas >0 Dias, Banidas) e 'Filtro de Usuário' exclusivo para administradores, operando em sincronia com a busca textual e o filtro de status geral.
- **Gestão Avançada de Assinaturas & Expiração (SaaS):** Adicionada coluna `expires_at` com migração automática no banco (`ensure_schema_migrations()`), trava comercial de bloqueio 403 Forbidden para contas vencidas no login e rotas protegidas.
- **CRUD Completo de Usuários no Painel Admin:** Endpoints `PUT /api/admin/users/{id}` (alteração de papel, redefinição de senha e renovação/extensão de dias) e `DELETE /api/admin/users/{id}` (com proteção contra auto-exclusão do admin logado).
- **Interface Visual de Assinaturas:** Seletor de validade no formulário de cadastro (7d, 15d, 30d, 90d, 365d, Vitalício), coluna de vencimento com status visual (Válido, Expirado, Vitalício) e modal de edição rápida para renovação de planos.
- **Empacotamento e Deploy Docker / Proxmox:** `Dockerfile` leve (`python:3.11-slim` com uvicorn) e `docker-compose.yml` isolado no serviço `config_generator_app`, mapeando a porta `8095:8000` para integração sem conflito com o Portainer e Nginx Proxy Manager, com volume persistente do SQLite (`./mining_history.db`).
- **Painel de Gestão Admin (UI & API):** Nova aba 'Gestão de Clientes' exclusiva para administradores com listagem de clientes cadastrados e formulário rápido para criação de novos usuários/admins sem necessidade de acesso ao terminal CLI.
- **Segurança e Proteção RBAC no Backend:** Endpoints `/api/admin/users` estritamente protegidos com `Depends(get_current_admin)`, rejeitando tentativas de acesso de usuários comuns com erro 403 Forbidden.
- **Exportação Direta de Contas Virgens (.ZIP):** Botão 'Baixar Virgens (.ZIP)' no Cofre consumindo `/api/vault/export-virgins` e gerando pacotes compactados automáticos via JSZip com estruturas `CONFIG_{ID}_0DIAS` e `cache.config.xml`.
- **Aba 'Cofre & Histórico' (UI):** Nova interface com métricas em tempo real (Total, Virgens, Recicladas, Banidas), busca textual rápida por MAC ou ID, filtros por status e cópia instantânea de MACs.
- **Motor Smart Skip (Inteligência Coletiva):** Verificação prévia no banco de dados antes de acionar o ADB. Contas já conhecidas como banidas/inválidas (`is_valid = False`) são ignoradas imediatamente, reduzindo o tempo de teste de ~13s para menos de 10ms por conta e poupando o emulador.
- **Enriquecimento Multi-tenant do Histórico:** Mapeamento `username` via `joinedload` em `AccountHistory.to_dict()` garantindo exibição clara do operador de cada teste.
- **Tela de Login e Proteção Visual no Frontend:** Novo card de login em glassmorphism dark mode com Tailwind CSS, que oculta todo o painel principal até a autenticação com sucesso.
- **Gerenciamento de Sessão JWT no Navegador:** Armazenamento do token de acesso no `localStorage`, validação persistente ao recarregar a página (`/api/auth/me`) e encerramento de sessão com logout seguro.
- **Interceptador Universal `authFetch`:** Injeção automática do cabeçalho `Authorization: Bearer <TOKEN>` em todas as requisições assíncronas do frontend e redirecionamento suave em caso de token expirado (401).
- **Header Dinâmico de Usuário:** Exibição do nome de usuário conectado e badge de papel (`USER` / `ADMIN`), acompanhado do botão de Sair (Logout).
- **Sistema de Usuários e Segurança JWT:** Mapeamento do modelo `User` com hashing seguro via `bcrypt` e emissão de tokens `JWT` com controle de papéis (`user` / `admin`).
- **Isolamento Multi-tenant no Histórico:** Relação `user_id` Foreign Key em `AccountHistory`. Usuários comuns visualizam exclusivamente suas próprias configurações mineradas no endpoint `/api/history`, enquanto administradores possuem visão global.
- **Proteção de Rotas com Bearer Auth:** Endpoints sensíveis (`/api/adb/inject`, `/api/history`) agora exigem autenticação JWT válida via header `Authorization: Bearer <token>`.
- **Utilitário de Inicialização de Administrador (`create_admin.py`):** Script CLI independente para criar ou atualizar credenciais do primeiro superusuário do sistema.
- **Persistência com SQLAlchemy:** Implementação de ORM desacoplado e agnóstico (compatível com SQLite local e PostgreSQL futuro via `DATABASE_URL`).
- **Gravação Automática no Fluxo ADB:** Persistência atômica via `session.merge()` ao testar contas no emulador, registrando contas válidas, recicladas e rejeições (EF9, Falha de Acesso, Bloqueios).

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
