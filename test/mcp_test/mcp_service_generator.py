import yaml
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, create_model
import inspect





class MCPServiceGenerator:
    def __init__(self, config_file: str):
        self.config = self._load_config(config_file)
        self.app = FastMCP("Dynamic Service")

    def _load_config(self, config_file: str) -> Dict:
        """加载配置文件"""
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _create_pydantic_model(self, func_name: str, params: Dict) -> BaseModel:
        """动态创建 Pydantic 模型"""
        fields = {}

        for param_name, param_config in params.items():
            param_type = param_config.get('type', 'string')
            required = param_config.get('required', True)
            description = param_config.get('description', '')

            # 类型映射
            type_mapping = {
                'string': str,
                'integer': int,
                'number': float,
                'boolean': bool
            }

            field_type = type_mapping.get(param_type, str)

            if not required:
                field_type = Optional[field_type]
                fields[param_name] = (field_type, None)
            else:
                fields[param_name] = (field_type, ...)

        return create_model(f"{func_name}Model", **fields)

    def register_function(self, func_name: str, actual_func):
        """注册函数到 FastMCP"""
        func_config = self.config['functions'][func_name]

        # 创建动态模型
        model_class = self._create_pydantic_model(
            func_name,
            func_config['parameters']
        )

        # 注册到 FastMCP
        @self.app.tool(
            name=func_config['name'],
            description=func_config['description']
        )
        def dynamic_handler(params: model_class) -> str:
            # 将 Pydantic 模型转换为 kwargs
            kwargs = params.dict(exclude_none=True)

            # 调用实际函数
            try:
                result = actual_func(**kwargs)
                return f"执行成功: {result}"
            except Exception as e:
                return f"执行失败: {str(e)}"

        return dynamic_handler

    def auto_register_functions(self, function_mapping: Dict[str, callable]):
        """自动注册所有配置的函数"""
        for func_name, actual_func in function_mapping.items():
            if func_name in self.config['functions']:
                self.register_function(func_name, actual_func)
                print(f"✅ 已注册函数: {func_name}")

    def run(self, host: str = "localhost", port: int = 8000):
        """启动服务"""
        print(f"🚀 FastMCP 服务启动在 {host}:{port}")
        self.app.run(transport="sse", host=host, port=port)
