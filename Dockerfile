FROM python:3.12-bookworm

WORKDIR /app

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
RUN uv run playwright install --with-deps

# Install Scrapling browser dependencies (Camoufox, etc.)
# Use -f to force reinstall if needed; fall back to plain install if -f is unsupported
RUN uv run scrapling install -f || uv run scrapling install

# Expose the HTTP port used by FastMCP
EXPOSE 8081

# Start the server over Streamable HTTP
CMD ["uv", "run", "python", "main.py"]