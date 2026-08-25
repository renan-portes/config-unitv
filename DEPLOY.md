# 🚀 Guia de Implantação e Uso do Gerador de .config

Este projeto é um gerador completo de arquivos de configuração (`.config`, `.properties` e `cache.config.xml`) para aparelhos e aplicativos IPTV / HackDroid, baseado na engenharia reversa de mais de 87 configurações reais.

---

## 💻 1. Como Usar no Windows (Uso Local Imediato)

Você pode rodar localmente no seu computador Windows de duas formas:

### Opção A: 1 Clique com o Arquivo `.bat` (Mais Fácil)
1. Dê 2 cliques no arquivo **`Iniciar_Gerador.bat`**.
2. O script verificará o Python, instalará as dependências automaticamente e abrirá o painel no seu navegador (`http://localhost:8000`).

### Opção B: Via Terminal / Prompt de Comando
```bash
pip install -r requirements.txt
python server.py
```
Acesse: `http://localhost:8000`

---

## 🐳 2. Como Rodar com Docker em Servidor / VPS (com seu Domínio)

Para colocar o gerador rodando na nuvem no seu domínio **`config.servidor.xyz.br`**:

### Passo 1: Enviar os arquivos para o seu servidor VPS
Copie a pasta do projeto para o seu servidor (via `scp`, `git`, `rsync` ou FileZilla), por exemplo em `/opt/config-generator`.

### Passo 2: Iniciar o container com Docker Compose
Entre na pasta do projeto no servidor e execute:
```bash
docker compose up -d --build
```

O container compilará e iniciará rodando na porta `8000` em segundo plano com reinicialização automática (`restart: unless-stopped`).

Para verificar se está rodando:
```bash
docker compose ps
docker compose logs -f
```

---

## 🌐 3. Configurar Domínio Próprio (`config.servidor.xyz.br`) com Nginx + HTTPS

### Passo 1: Apontar o DNS
No painel do seu registrador de domínio / Cloudflare, crie uma entrada DNS tipo **A**:
- **Tipo:** `A`
- **Nome:** `config` (ou `config.servidor.xyz.br`)
- **Valor / IP:** `IP_DO_SEU_SERVIDOR_VPS`
- **Proxy Cloudflare:** Desativado (DNS Only) ou Ativado com SSL Full.

---

### Passo 2: Configurar o Nginx no Servidor

Crie o arquivo de configuração do site:
```bash
sudo nano /etc/nginx/sites-available/config.servidor.xyz.br.conf
```

Cole a seguinte configuração:
```nginx
server {
    listen 80;
    server_name config.servidor.xyz.br;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ative o site e reinicie o Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/config.servidor.xyz.br.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### Passo 3: Ativar Certificado SSL Gratuito (HTTPS) com Certbot

Execute:
```bash
sudo apt update && sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d config.servidor.xyz.br
```

Siga as instruções na tela e escolha a opção de redirecionar HTTP para HTTPS automaticamente.

Pronto! Seu gerador estará disponível mundialmente e de forma segura em:
👉 **`https://config.servidor.xyz.br`**

---

## 📱 4. Como Usar no Celular / Android / Tablet

- Abra o navegador do celular (Chrome / Firefox) e acesse o endereço do servidor (ou `https://config.servidor.xyz.br`).
- A interface é **100% responsiva** e se adapta perfeitamente ao tamanho da tela.
- **Dica PWA:** No Chrome do Android, clique nos 3 pontinhos e selecione **"Adicionar à tela inicial"**. Ele funcionará como se fosse um **APK / App Nativo** instalado no seu celular!

---

## 🛠️ 5. Funcionalidades Incluídas no Painel

1. **⚡ Gerador Individual**:
   - Geração de MAC aleatório válido ou inserção de MAC personalizado.
   - Cálculo automático do token de 192-bit DES em Hex e Base64.
   - Pré-visualização em tempo real de `.config`, `.properties` e `cache.config.xml`.
   - Download individual de arquivos, download em pacote `.ZIP` ou gravação direta no disco.

2. **📦 Gerador em Massa (Bulk)**:
   - Geração de até 100+ configurações simultâneas em sequência.
   - Download de todas as pastas empacotadas em um único arquivo `.ZIP`.

3. **📚 Biblioteca de 87 Configurações**:
   - Tabela pesquisável com todas as 87 configurações originais catalogadas (`CONFIG_1..20` e `HackDroid 1..67`).
   - Visualização do código-fonte e download direto de qualquer configuração existente.

4. **🔍 Decodificador Hexadecimal**:
   - Ferramenta de inspeção de strings hexadecimais para validar chaves e tokens de identificação de aparelhos.
