<div align="center">
  <img src="logo.png" alt="Logo" width="120" style="border-radius: 20px;" />
  <h1>⚡ Gerador de Configurações IPTV</h1>
  <p>Gerador moderno, rápido e completo de arquivos <code>.config</code>, <code>.properties</code> e <code>cache.config.xml</code> com interface web responsiva, suporte a geração em lote, pool local/nuvem de 10.000+ arquivos e injeção automática via ADB.</p>
</div>

---

> [!NOTE]
> **Status do Projeto & Modo 0 Dias:**  
> As configurações geradas pelo painel e obtidas através do pool integrado (10k) são válidas e prontas para uso.  
> O algoritmo para geração de **contas com 0 dias virgens** está atualmente em **fase de desenvolvimento**. Contribuições da comunidade são muito bem-vindas através de **Pull Requests**!

---

## 🚀 Funcionalidades

- **✨ Geração Individual & Customizada**: Gera arquivos com endereços MAC randômicos, Device IDs exclusivos e User IDs novos.
- **📦 Geração em Lote**: Gera 10, 50 ou 100+ configurações de uma só vez, exportando em `.ZIP` ou gravando diretamente no disco.
- **☁️ Integração com Pool Integrado (10.000+ configs)**: Busca instantânea de configurações ativas diretamente do banco local indexado (`ids.json`).
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

## 🤝 Como Contribuir (Pull Requests)

Se você descobriu novos padrões de chaves, melhorias de código, testes ou quer ajudar no desenvolvimento do modo de **0 dias virgens**, sinta-se à vontade para abrir uma *Issue* ou enviar um **Pull Request (PR)**!

### 💡 O que é um Pull Request?
Um **Pull Request (PR)** é a ferramenta do GitHub que permite que você sugira melhorias no código:
1. Você cria uma cópia (Fork) deste projeto na sua própria conta do GitHub.
2. Faz as alterações ou melhorias que deseja.
3. Envia uma solicitação (*Pull Request*) para que a sua contribuição seja revisada e incorporada ao projeto principal.

### 📋 Passo a Passo para Enviar sua Contribuição:
1. Clique no botão **`Fork`** no canto superior direito desta página no GitHub.
2. Clone o seu fork na sua máquina:
   ```bash
   git clone https://github.com/SEU-USUARIO/config-unitv.git
   ```
3. Crie uma nova branch para a sua funcionalidade:
   ```bash
   git checkout -b feature/minha-melhoria
   ```
4. Faça as alterações no código e crie o commit:
   ```bash
   git commit -m "feat: descricao da melhoria implementada"
   ```
5. Envie para o seu fork no GitHub:
   ```bash
   git push origin feature/minha-melhoria
   ```
6. Acesse a página do seu fork no GitHub e clique no botão verde **`Compare & pull request`** para enviar sua sugestão.

---

## 📁 Estrutura do Projeto

```
├── generator_engine.py    # Motor criptográfico e gerador de arquivos
├── server.py              # API REST desenvolvida em FastAPI / Uvicorn
├── index.html             # Painel Web moderno (TailwindCSS + Lucide Icons)
├── logo.png               # Logotipo e Favicon do projeto
├── ids.json               # Pool com 10.231 IDs indexados localmente
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
| `GET` | `/api/cloud/random` | Puxa uma configuração do pool integrado (10k) |
| `GET` | `/api/adb/devices` | Lista emuladores e aparelhos conectados via ADB |
| `POST` | `/api/adb/inject` | Injeta a configuração diretamente no emulador |
| `POST` | `/api/decode-hex` | Decodifica chave hexadecimal |

---

## 💖 Apoie o Projeto
Se este projeto foi útil para você, considere apoiar o desenvolvimento via Pix:  
👉 **[Apoiar com Pix no PixGG](https://pixgg.com.br/rzao)**

---

## 📄 Licença
Distribuído sob a licença MIT. Consulte `LICENSE` para mais detalhes.
