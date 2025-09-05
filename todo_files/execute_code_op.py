import sys
from io import StringIO

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp


@C.register_op()
class ExecuteCodeOp(BaseOp):

    def execute(self):
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()

        try:
            code_key: str = self.op_params.get("code_key", "code")
            code_str: str = self.context[code_key]
            exec(code_str)
            code_result = redirected_output.getvalue()

        except Exception as e:
            logger.info(f"{self.name} encounter exception! error={e.args}")
            code_result = str(e)

        sys.stdout = old_stdout
        self.context.code_result = code_result


if __name__ == "__main__":
    C.set_service_config().init_by_service_config()
    op = ExecuteCodeOp()

    context = FlowContext(code="print('Hello World')")
    op(context=context)
    print(context.code_result)

    context.code = "print('Hello World!'"
    op(context=context)
    print(context.code_result)
