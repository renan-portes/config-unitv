# Usando imagem base Python oficial ultra-leve
FROM python:3.11-slim

# Metadados
LABEL maintainer="Gerador .config IPTV"
LABEL description="Gerador de arquivos .config, .properties e cache.config.xml"

# Define diretório de trabalho
WORKDIR /app

# Instala dependências de compilação mínimas se necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivo de requisitos primeiro para aproveitar o cache de build do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos do projeto
COPY generator_engine.py .
COPY server.py .
COPY index.html .

# Copia pastas de configurações de exemplo existentes se existirem
COPY CONFIG_* ./
COPY HackDroid/ ./HackDroid/

# Variáveis de ambiente padrão
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

# Expõe a porta do servidor
EXPOSE 8000

# Healthcheck do container
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Comando de inicialização do servidor Uvicorn
CMD ["python", "server.py"]
