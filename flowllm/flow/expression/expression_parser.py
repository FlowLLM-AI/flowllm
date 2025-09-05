import re

from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp
from flowllm.schema.service_config import OpConfig


class ExpressionParser:
    SEQ_SYMBOL = ">>"
    PARALLEL_SYMBOL = "|"

    """
    Simple flow implementation that supports parsing operation expressions.

    Supports flow expressions like:
    - "op1 >> op2" (sequential expressions)
    - "op1 | op2" (parallel expressions)  
    - "op1 >> (op2 | op3) >> op4" (mixed expressions)
    - "op1 >> (op1 | (op2 >> op3)) >> op4" (complex nested expressions)
    """

    def __init__(self, flow_content: str = ""):
        self.flow_content: str = flow_content
        self._parsed_ops_cache = {}

    def parse_flow(self):
        self._parsed_ops_cache.clear()
        expression = re.sub(r'\s+', ' ', self.flow_content.strip())
        return self._parse_expression(expression)

    def _parse_expression(self, expression: str) -> BaseOp:
        """
        Parse the flow content string into executable operations.

        Supports expressions with operators:
        - ">>" for sequential execution
        - "|" for parallel execution
        - Parentheses for grouping operations

        Args:
            expression: The expression string to parse. If None, uses self.flow_content

        Returns:
            BaseOp: The parsed flow as an executable operation tree
        """
        # handle parentheses by finding and replacing innermost groups
        while '(' in expression:
            # Find the innermost parentheses
            start = -1
            for i, char in enumerate(expression):
                if char == '(':
                    start = i
                elif char == ')':
                    if start == -1:
                        raise ValueError(f"mismatched parentheses in expression: {expression}")

                    # extract and parse the inner expression
                    inner_expr = expression[start + 1:i]
                    inner_result = self._parse_expression(inner_expr)

                    # create a placeholder for the parsed inner expression
                    placeholder = f"__PARSED_OP_{len(self._parsed_ops_cache)}__"

                    # store the parsed operation for later retrieval
                    self._parsed_ops_cache[placeholder] = inner_result

                    # Replace the parentheses group with placeholder
                    expression = expression[:start] + placeholder + expression[i + 1:]
                    break
            else:
                if start != -1:
                    raise ValueError(f"mismatched parentheses in expression: {expression}")

        # Parse the expression without parentheses
        return self._parse_flat_expression(expression)

    def _parse_flat_expression(self, expression: str) -> BaseOp:
        """
        Parse a flat expression (no parentheses) into operation objects.

        Args:
            expression: The flat expression string

        Returns:
            BaseOp: The parsed operation tree
        """
        # split by '>>' first (sequential has higher precedence)
        sequential_parts = [part.strip() for part in expression.split(self.SEQ_SYMBOL)]

        if len(sequential_parts) > 1:
            # parse each part and create sequential operation
            ops = []
            for part in sequential_parts:
                part = part.strip()
                if part in self._parsed_ops_cache:
                    ops.append(self._parsed_ops_cache[part])
                else:
                    ops.append(self._parse_parallel_expression(part))

            return SequentialOp(ops=ops)

        else:
            # no sequential operators, parse for parallel
            return self._parse_parallel_expression(expression)

    def _parse_parallel_expression(self, expression: str) -> BaseOp:
        """
        Parse a parallel expression (operations separated by |).

        Args:
            expression: The expression string

        Returns:
            BaseOp: The parsed operation (single op or parallel op)
        """
        parallel_parts = [part.strip() for part in expression.split(self.PARALLEL_SYMBOL)]

        if len(parallel_parts) > 1:
            # create parallel operation
            ops = []
            for part in parallel_parts:
                part = part.strip()
                if part in self._parsed_ops_cache:
                    ops.append(self._parsed_ops_cache[part])
                else:
                    ops.append(self._create_op(part))

            return ParallelOp(ops=ops)

        else:
            # single operation
            part = expression.strip()
            if part in self._parsed_ops_cache:
                return self._parsed_ops_cache[part]
            else:
                return self._create_op(part)

    @staticmethod
    def _create_op(op_name: str) -> BaseOp:
        if op_name in C.service_config.op:
            op_config: OpConfig = C.service_config.op[op_name]
        else:
            op_config: OpConfig = OpConfig()

        if op_config.backend in C.registry_dict["op"]:
            op_cls = C.resolve_op(op_config.backend)

        elif op_name in C.registry_dict["op"]:
            op_cls = C.resolve_op(op_name)

        else:
            raise ValueError(f"op='{op_name}' is not registered!")

        kwargs = {
            "name": op_name,
            "max_retries": op_config.max_retries,
            "raise_exception": op_config.raise_exception,
            **op_config.params
        }

        if op_config.language:
            kwargs["language"] = op_config.language
        if op_config.prompt_path:
            kwargs["prompt_path"] = op_config.prompt_path
        if op_config.llm:
            kwargs["llm"] = op_config.llm
        if op_config.embedding_model:
            kwargs["embedding_model"] = op_config.embedding_model
        if op_config.vector_store:
            kwargs["vector_store"] = op_config.vector_store

        return op_cls(**kwargs)
