import asyncio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    async with stdio_client(
        StdioServerParameters(command="gitingest", args=["--mcp-server"]),
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print("🛠️  Outils disponibles:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Call the ingest_repository tool
            print("\n📞 Appel de l'outil ingest_repository...")
            result = await session.call_tool(
                "ingest_repository", {"source": "https://github.com/coderamp-labs/gitingest"}
            )
            print(result)


asyncio.run(main())
