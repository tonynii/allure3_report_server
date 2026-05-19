from mcp.server.fastmcp.prompts import base

from app.mcp.server import mcp


@mcp.prompt(title="Failure Root Cause Analysis")
def failure_analysis_prompt(project_key: str, run_id: str) -> list[base.Message]:
    """分析测试失败的根因，给出修复建议"""
    return [
        base.UserMessage(
            f"请分析项目 '{project_key}' 的运行 '{run_id}' 中所有失败测试的根因。\n\n"
            "分析步骤：\n"
            "1. 用 analyze_failures 获取失败概览和分类\n"
            "2. 对每类失败，用 list_failed_tests 获取错误详情\n"
            "3. 对关键失败，用 get_test_detail 查看步骤树和完整堆栈\n"
            "4. 总结根因并给出具体修复建议"
        ),
    ]


@mcp.prompt(title="Project Health Check")
def health_check_prompt(project_key: str) -> list[base.Message]:
    """项目健康度检查和趋势分析"""
    return [
        base.UserMessage(
            f"请对项目 '{project_key}' 进行健康度分析：\n\n"
            "1. 用 list_runs 查看最近的运行列表\n"
            "2. 用 get_run_trend 查看通过率趋势\n"
            "3. 分析趋势是在好转、恶化还是稳定\n"
            "4. 如有最近失败的运行，用 analyze_failures 分析失败模式\n"
            "5. 给出项目健康度评估和改进建议"
        ),
    ]
