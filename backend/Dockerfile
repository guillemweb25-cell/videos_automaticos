FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for pymysql
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ffmpeg \
    imagemagick \
    && sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@\*"/g' /etc/ImageMagick-*/policy.xml \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

CMD ["./start.sh"]
