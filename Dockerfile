# Usando imagem base Python oficial ultra-leve
FROM python:3.11-slim

LABEL maintainer="Gerador de Configurações IPTV SaaS"
LABEL description="API REST e Painel Web para Mineração, Inteligência Coletiva e Gestão de Assinaturas"

WORKDIR /app

# Instala curl e adb para conexões e healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    android-tools-adb \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos essenciais da aplicação
COPY generator_engine.py .
COPY server.py .
COPY create_admin.py .
COPY index.html .
COPY logo.png .
COPY apps/ ./apps/

# Variáveis de ambiente padrão
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
