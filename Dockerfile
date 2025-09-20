FROM python:3.12-bookworm

WORKDIR /app

# System packages to make headless browsers and header generation more deterministic
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales tzdata ca-certificates \
    fonts-noto fonts-noto-cjk fonts-liberation \
    libnss3 libdbus-glib-1-2 libxss1 libxrandr2 libxtst6 \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen en_US.UTF-8 \
    && update-ca-certificates

# Environment for consistent headers and rendering
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV TZ=Etc/UTC
ENV XDG_CACHE_HOME=/tmp/.cache
ENV XDG_CONFIG_HOME=/tmp/.config
ENV XDG_RUNTIME_DIR=/tmp/.runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project configuration first for better layer caching
COPY pyproject.toml .
# Copy lockfile if present (will be used if compatible; otherwise `uv sync` will resolve)
COPY uv.lock .

# Copy application source
COPY src/ ./src/
COPY main.py ./

# Install Python dependencies into a virtualenv managed by uv
# Using non-frozen sync so new deps added to pyproject can be resolved during build
RUN uv sync

# Install Playwright browsers and system dependencies inside the environment
RUN uv run playwright install-deps
RUN uv run playwright install --with-deps

# Install Scrapling browser dependencies (Camoufox, etc.)
#RUN uv run camoufox fetch
# Use -f to force reinstall if needed; fall back to plain install if -f is unsupported
RUN uv run scrapling install -f || uv run scrapling install

# Expose the HTTP port used by FastMCP
EXPOSE 8081

# Start the server over Streamable HTTP
CMD ["uv", "run", "dev"]