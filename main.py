import os
from hello_server.server import create_server

server = create_server()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8081"))
    path = os.getenv("MCP_PATH", "/mcp")
    host = os.getenv("HOST", "0.0.0.0")
    # Run FastMCP over streamable HTTP so it can be accessed by web clients / Smithery
    server.run(transport="http" ,port=port, path=path)
