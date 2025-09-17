# test

An MCP server built with Smithery.

## Prerequisites

- **Smithery API key**: Get yours at [smithery.ai/account/api-keys](https://smithery.ai/account/api-keys)

## Getting Started

1. Run the server:
   ```bash
   uv run dev
   ```

2. Test interactively:

   ```bash
   uv run playground
   ```

Try saying "Say hello to John" to test the example tool.

## Run with Docker

Build the image (from the project root):

```bash
docker build -t hello-server .
```

Run the container:

```bash
docker run --rm -p 8081:8081 --shm-size=1g hello-server
```

Notes:

- The server listens on `0.0.0.0:8081` and serves the MCP endpoint at `/mcp`.
- `--shm-size=1g` improves browser stability for Playwright/Firefox-based scraping.

You can now connect an MCP client to:

```
http://localhost:8081/mcp
```

## Development

Your server code is in `src/hello_server/server.py`. Add or update your server capabilities there.

## Deploy

Ready to deploy? Push your code to GitHub and deploy to Smithery:

1. Create a new repository at [github.com/new](https://github.com/new)

2. Initialize git and push to GitHub:
   ```bash
   git add .
   git commit -m "Hello world 👋"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
   ```

3. Deploy your server to Smithery at [smithery.ai/new](https://smithery.ai/new)
