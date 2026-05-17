FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for pymysql
# fonts-noto-cjk: Korean / Japanese / Chinese glyphs for Pillow thumbnail overlay.
#   Installs NotoSansCJK-Bold.ttc and friends to /usr/share/fonts/opentype/noto/.
#   Required for the Korean channel (mysteries) and any future CJK channels —
#   without it, Pillow renders hangul as empty boxes (□□).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    fonts-noto-cjk \
    libass-dev \
    && sed -i 's/rights="none" pattern="@\*"/rights="read|write" pattern="@\*"/g' /etc/ImageMagick-*/policy.xml \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

CMD ["./start.sh"]
