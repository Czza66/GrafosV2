FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgl1 \
    coinor-cbc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]