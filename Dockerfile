FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# spacy model at build time (~12MB, CPU only)
RUN python -m spacy download en_core_web_sm

COPY server.py .

CMD ["python", "server.py"]
