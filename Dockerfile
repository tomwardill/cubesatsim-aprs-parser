FROM ghcr.io/astral-sh/uv:python3.13-trixie

ARG TARGETPLATFORM
ARG CACHE_NAME=${TARGETPLATFORM}

ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Install apt dependencies
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked,id=${CACHE_NAME}-apt \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    rtl-sdr \
    multimon-ng \
    swig \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/app/lg,id=${CACHE_NAME}-lg wget http://abyz.me.uk/lg/lg.zip && \
    unzip lg.zip && \
    cd lg && \
    make && \
    make install

# Copy the application files
COPY . .

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/uv,id=${CACHE_NAME}-uv uv sync --compile-bytecode --locked

ENTRYPOINT ["./run-parser.sh"]
