from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp


@C.register_op()
class TerminateOp(BaseOp):

    def execute(self):
        # Get status from context
        status = self.context.status
        assert status in ["success", "failure"], f"Invalid status: {status}"
        self.context.terminate_answer = f"The interaction has been completed with status: {status}"


if __name__ == "__main__":
    from flowllm.context.flow_context import FlowContext

    C.set_service_config().init_by_service_config()

    # Test success termination
    op = TerminateOp()
    context = FlowContext(status="success")
    result = op(context=context)
    print(f"Result: {context.terminate_answer}")

    # Test failure termination
    context.status = "failure"
    op(context=context)
    print(f"Result: {context.terminate_answer}")
