from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.config import settings


@dataclass
class AppContext:
    base_url: str


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    yield AppContext(base_url=settings.base_url or "http://localhost:8088")


mcp = FastMCP(
    "Allure3 Report Server",
    instructions=(
        "Allure3 测试报告平台的 MCP Server。\n\n"
        "你可以：\n"
        "1. 用 list_projects 查看项目列表和概况\n"
        "2. 用 list_runs 查看项目的运行历史\n"
        "3. 用 get_run 获取某次运行的详细统计\n"
        "4. 用 analyze_failures 对失败测试做智能分析（推荐入口）\n"
        "5. 用 list_failed_tests 只看失败/异常的测试\n"
        "6. 用 get_test_detail 查看单个测试的步骤树和错误堆栈\n"
        "7. 用 compare_runs 对比多次运行的差异\n"
        "8. 用 get_run_trend 查看通过率趋势\n\n"
        "典型工作流：list_projects → list_runs → analyze_failures → get_test_detail"
    ),
    stateless_http=True,
    json_response=True,
    lifespan=app_lifespan,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)

from app.mcp import tools, resources, prompts  # noqa: E402, F401


def main():
    mcp.settings.host = settings.mcp_host
    mcp.settings.port = settings.mcp_port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
