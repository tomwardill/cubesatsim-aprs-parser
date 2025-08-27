FROM ghcr.io/astral-sh/uv:python3.13-bookworm

ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install apt dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    rtl-sdr \
    multimon-ng \
    swig \
    liblgpio-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the application files
COPY . .

# Install Python dependencies
RUN uv sync

CMD ["./run.sh"]
