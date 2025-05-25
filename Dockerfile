FROM python:3.11-slim

# Instalar GLPK y dependencias básicas
RUN apt-get update && apt-get install -y \
    glpk-utils \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear el directorio de trabajo
WORKDIR /app

# Copiar archivos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exponer el puerto que usará uvicorn
EXPOSE 10000

# Comando para arrancar la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
