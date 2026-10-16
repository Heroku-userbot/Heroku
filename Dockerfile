FROM python:3.14

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DOCKER=true \
    GIT_PYTHON_REFRESH=quiet

RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    ffmpeg \
    gcc \
    git \
    libavcodec-dev \
    libavdevice-dev \
    libavformat-dev \
    libavutil-dev \
    libcairo2 \
    libmagic1 \
    libswscale-dev \
    openssh-server \
    xfonts-75dpi \
    xfonts-base \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install --no-install-recommends -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /data
RUN mkdir /data/private

RUN git clone https://github.com/Heroku-userbot/Heroku /data/Heroku

WORKDIR /data/Heroku

ARG HEROKU_REF=master
RUN git fetch origin "${HEROKU_REF}" && git checkout "${HEROKU_REF}" && git pull origin "${HEROKU_REF}"

RUN pip install --no-cache-dir --no-warn-script-location --disable-pip-version-check --upgrade -r requirements.txt

CMD ["python", "-m", "heroku", "--root"]
