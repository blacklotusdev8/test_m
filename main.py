import os
from hello_server.server import create_server

server = create_server()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    # Run Streamable HTTP (MCP endpoint path defaults to /mcp)
    print(f"Starting FastMCP HTTP server on port {port} ...", flush=True)
    server.run(transport="http", port=port)
