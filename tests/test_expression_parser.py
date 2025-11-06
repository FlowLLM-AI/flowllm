from flowllm.core.context.service_context import C
from flowllm.core.op.base_op import BaseOp
from flowllm.core.utils.common_utils import parse_flow_expression


# Define minimal ops for testing and register them with stable names
@C.register_op()
class ContainerOp(BaseOp):
    def execute(self):
        return self.name


@C.register_op()
class SearchOp(BaseOp):
    def execute(self):
        return self.name


@C.register_op()
class FindOp(BaseOp):
    def execute(self):
        return self.name


@C.register_op()
class Op1Op(BaseOp):
    def execute(self):
        return self.name


@C.register_op()
class Op2Op(BaseOp):
    def execute(self):
        return self.name


@C.register_op()
class Op3Op(BaseOp):
    def execute(self):
        return self.name


def test_expression_parser_single_line_sequential():
    flow = "Op1Op() >> Op2Op() >> Op3Op()"
    result = parse_flow_expression(flow)
    # Should be a SequentialOp with three ops
    from flowllm.core.op.sequential_op import SequentialOp

    assert isinstance(result, SequentialOp)
    assert len(result.ops) == 3
    assert isinstance(result.ops[0], Op1Op)
    assert isinstance(result.ops[1], Op2Op)
    assert isinstance(result.ops[2], Op3Op)


def test_expression_parser_multiline_exec_and_eval_independent():
    flow = """
op = ContainerOp()
op.ops.search = SearchOp()
op.ops.find = FindOp()
Op1Op() >> Op2Op() >> Op3Op()
""".strip()

    result = parse_flow_expression(flow)
    from flowllm.core.op.sequential_op import SequentialOp

    # The assignments should execute without affecting the final expression
    assert isinstance(result, SequentialOp)
    assert len(result.ops) == 3
    assert isinstance(result.ops[0], Op1Op)
    assert isinstance(result.ops[1], Op2Op)
    assert isinstance(result.ops[2], Op3Op)


def test_expression_parser_multiline_return_assigned_op():
    flow = """
op = ContainerOp()
op.ops.search = SearchOp()
op.ops.find = FindOp()
op
""".strip()

    result = parse_flow_expression(flow)
    assert isinstance(result, ContainerOp)
    # Verify assignments were applied to the container's ops
    assert hasattr(result.ops, "search")
    assert hasattr(result.ops, "find")
    assert isinstance(result.ops.search, SearchOp)
    assert isinstance(result.ops.find, FindOp)


def test_expression_parser_multiline_variable_reassignment_and_return():
    flow = """
opx = Op1Op() >> Op2Op()
opx = opx >> Op3Op()
opx
""".strip()

    result = parse_flow_expression(flow)
    from flowllm.core.op.sequential_op import SequentialOp

    assert isinstance(result, SequentialOp)
    assert len(result.ops) == 3
    assert isinstance(result.ops[0], Op1Op)
    assert isinstance(result.ops[1], Op2Op)
    assert isinstance(result.ops[2], Op3Op)


def test_expression_parser_parallel_basic():
    flow = "Op1Op() | Op2Op()"
    result = parse_flow_expression(flow)
    from flowllm.core.op.parallel_op import ParallelOp

    assert isinstance(result, ParallelOp)
    assert len(result.ops) == 2
    assert isinstance(result.ops[0], Op1Op)
    assert isinstance(result.ops[1], Op2Op)


def test_expression_parser_mixed_with_parentheses():
    flow = "Op1Op() >> (Op2Op() | Op3Op()) >> Op1Op()"
    result = parse_flow_expression(flow)
    from flowllm.core.op.sequential_op import SequentialOp
    from flowllm.core.op.parallel_op import ParallelOp

    assert isinstance(result, SequentialOp)
    assert len(result.ops) == 3
    assert isinstance(result.ops[0], Op1Op)
    assert isinstance(result.ops[1], ParallelOp)
    assert isinstance(result.ops[2], Op1Op)
    # Check inner parallel contents
    inner = result.ops[1]
    assert isinstance(inner.ops[0], Op2Op)
    assert isinstance(inner.ops[1], Op3Op)


def test_expression_parser_multiline_multiple_attribute_assignments_mixed_chain():
    flow = """
op1 = Op1Op()
op1.ops.search = SearchOp()
op1.ops.find = FindOp()
(op1 | Op2Op()) >> Op3Op()
""".strip()

    result = parse_flow_expression(flow)
    from flowllm.core.op.sequential_op import SequentialOp
    from flowllm.core.op.parallel_op import ParallelOp

    assert isinstance(result, SequentialOp)
    assert isinstance(result.ops[0], ParallelOp)
    assert isinstance(result.ops[1], Op3Op)
    # attribute assignments applied
    assert hasattr(result.ops[0].ops[0].ops, "search")
    assert hasattr(result.ops[0].ops[0].ops, "find")
    assert isinstance(result.ops[0].ops[0].ops.search, SearchOp)
    assert isinstance(result.ops[0].ops[0].ops.find, FindOp)

def test_expression_parser_complex_left_shift_parallel_and_sequential():
    flow = """
op = ContainerOp()
op << {"search": Op1Op(), "find": Op2Op()}
(op | Op2Op()) >> (Op1Op() | Op3Op()) >> op
""".strip()

    result = parse_flow_expression(flow)
    from flowllm.core.op.sequential_op import SequentialOp
    from flowllm.core.op.parallel_op import ParallelOp

    # Structure: Sequential with three parts: Parallel, Parallel, Container
    assert isinstance(result, SequentialOp)
    assert len(result.ops) == 3

    first = result.ops[0]
    second = result.ops[1]
    third = result.ops[2]

    # First parallel: (op | op2)
    assert isinstance(first, ParallelOp)
    assert len(first.ops) == 2
    assert isinstance(first.ops[0], ContainerOp)
    assert isinstance(first.ops[1], Op2Op)

    # Ensure left-shift attached named children to container
    container = first.ops[0]
    assert hasattr(container.ops, "search")
    assert hasattr(container.ops, "find")
    assert isinstance(container.ops.search, Op1Op)
    assert isinstance(container.ops.find, Op2Op)

    # Second parallel: (op1 | op3)
    assert isinstance(second, ParallelOp)
    assert len(second.ops) == 2
    assert isinstance(second.ops[0], Op1Op)
    assert isinstance(second.ops[1], Op3Op)

    # Final op is the container op
    assert isinstance(third, ContainerOp)

# pytest -q tests/test_expression_parser.py
