# Usando imagem base Python oficial ultra-leve
FROM python:3.11-slim

LABEL maintainer="Gerador de Configurações IPTV"
LABEL description="Gerador de arquivos .config, .properties e cache.config.xml"

WORKDIR /app

# Instala curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos essenciais da aplicação
COPY generator_engine.py .
COPY server.py .
COPY index.html .
COPY logo.png .
COPY ids.json .

# Variáveis de ambiente padrão
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "server.py"]
