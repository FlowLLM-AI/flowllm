from pydantic import BaseModel, Field
from fastmcp import FastMCP


# 定义参数模型
class CalculateParams(BaseModel):
    a: int = Field(description="第一个数字")
    b: int = Field(description="第二个数字")
    operation: str = Field(description="运算类型", enum=["add", "subtract", "multiply", "divide"])


# 创建 FastMCP 实例
mcp = FastMCP("Calculator")


# 注册工具函数
@mcp.tool()
def calculate(params: CalculateParams) -> str:
    """执行基本数学运算"""
    if params.operation == "add":
        result = params.a + params.b
    elif params.operation == "subtract":
        result = params.a - params.b
    elif params.operation == "multiply":
        result = params.a * params.b
    elif params.operation == "divide":
        result = params.a / params.b if params.b != 0 else "除数不能为零"

    return f"结果: {result}"

mcp.run(transport="sse", host="0.0.0.0", port=8000)