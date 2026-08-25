# ⚡ Gerador de Configurações IPTV

Gerador moderno, rápido e completo de arquivos `.config`, `.properties` e `cache.config.xml`, com interface web responsiva, suporte a geração em lote, integração com banco de dados na nuvem (10.000+ arquivos) e injeção automática via ADB.

---

## 🚀 Funcionalidades

- **✨ Geração Individual & Personalizada**: Gera arquivos com endereços MAC randômicos, Device IDs exclusivos e User IDs novos.
- **📦 Geração em Lote**: Gera 10, 50 ou 100+ configurações de uma só vez, exportando em `.ZIP` ou gravando diretamente no disco.
- **☁️ Integração com Pool da Nuvem (10.000+ configs)**: Busca instantânea de configurações ativas diretamente do repositório online.
- **📲 Injeção ADB com 1 Clique**: Detecta emuladores Android (ex: MEmu em `127.0.0.1:21503`), limpa o cache, injeta o arquivo `.config` e inicia o aplicativo automaticamente.
- **🔓 Decodificador Hexadecimal**: Ferramenta embutida para decodificar tokens, Device IDs e chaves criptografadas.
- **📦 Central de Aplicativos**: Aba dedicada para download direto de versões de aplicativos.
- **🐳 100% Compatível com Docker e Portainer**: Pronto para deploy em VPS, servidores locais ou nuvem.

---

## 🛠️ Como Executar

### 1. No Windows (Execução Rápida)
Dê dois cliques no arquivo:
```bash
Iniciar_Gerador.bat
```
O script instalará as dependências necessárias e abrirá automaticamente o painel em seu navegador (`http://localhost:8000`).

---

### 2. Com Docker & Docker Compose
Execute no terminal:
```bash
docker compose up -d --build
```
Acesse no navegador: **`http://localhost:8095`** (ou através do seu IP/Domínio).

---

### 3. No Portainer (Stacks)
1. No painel do Portainer, vá em **Stacks** ➔ **Add stack**.
2. Escolha o método **Repository** e aponte para este repositório Git:
   ```
   https://github.com/renan-portes/config-unitv.git
   ```
3. Defina o Compose path como `docker-compose.yml` e clique em **Deploy the stack**.

---

## 📁 Estrutura do Projeto

```
├── generator_engine.py    # Motor criptográfico e gerador de arquivos
├── server.py              # API REST desenvolvida em FastAPI / Uvicorn
├── index.html             # Painel Web moderno (TailwindCSS + Lucide Icons)
├── Iniciar_Gerador.bat    # Inicializador rápido para Windows
├── Dockerfile             # Configuração de build da imagem Docker
├── docker-compose.yml     # Orquestração do container Docker (porta 8095)
├── requirements.txt       # Dependências Python
└── README.md              # Documentação do projeto
```

---

## 📡 Endpoints da API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Verificação de status do servidor |
| `POST` | `/api/generate-single` | Gera uma configuração individual |
| `POST` | `/api/generate-bulk` | Gera configurações em lote |
| `POST` | `/api/download-single-zip` | Baixa configuração única como arquivo `.ZIP` |
| `POST` | `/api/download-bulk-zip` | Baixa lote completo como `.ZIP` |
| `GET` | `/api/cloud/random` | Puxa uma configuração do pool online (10k) |
| `GET` | `/api/adb/devices` | Lista emuladores e aparelhos conectados via ADB |
| `POST` | `/api/adb/inject` | Injeta a configuração diretamente no emulador |
| `POST` | `/api/decode-hex` | Decodifica chave hexadecimal |

---

## 📄 Licença
Distribuído sob a licença MIT. Consulte `LICENSE` para mais detalhes.
