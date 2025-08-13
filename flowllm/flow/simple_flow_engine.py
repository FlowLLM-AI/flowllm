import re

from loguru import logger

from flowllm.context.service_context import C
from flowllm.flow.base_flow_engine import BaseFlowEngine
from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp
from flowllm.schema.service_config import OpConfig


@C.register_flow_engine()
class SimpleFlowEngine(BaseFlowEngine):
    SEQ_SYMBOL = ">>"
    PARALLEL_SYMBOL = "|"

    """
    Simple flow implementation that supports parsing and executing operation expressions.
    
    Supports flow expressions like:
    - "op1 >> op2" (sequential execution)
    - "op1 | op2" (parallel execution)  
    - "op1 >> (op2 | op3) >> op4" (mixed execution)
    - "op1 >> (op1 | (op2 >> op3)) >> op4" (complex nested execution)
    """

    def _parse_flow(self):
        expression = re.sub(r'\s+', ' ', self.flow_content.strip())
        self._parsed_flow = self._parse_expression(expression)

    def _parse_expression(self, expression: str) -> BaseOp:
        """
        Parse the flow content string into executable operations.
        
        Supports expressions with operators:
        - '>>' for sequential execution
        - '|' for parallel execution
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

            return SequentialOp(ops=ops, flow_context=self.flow_context)

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

            return ParallelOp(ops=ops, flow_context=self.flow_context)

        else:
            # single operation
            part = expression.strip()
            if part in self._parsed_ops_cache:
                return self._parsed_ops_cache[part]
            else:
                return self._create_op(part)

    def _create_op(self, op_name: str) -> BaseOp:
        if op_name in self.flow_context.service_config.op:
            op_config: OpConfig = self.flow_context.service_config.op[op_name]
            op_cls = C.resolve_op(op_config.backend)
            op: BaseOp = op_cls(name=op_name,
                                flow_context=self.flow_context,
                                llm=op_config.llm,
                                embedding_model=op_config.embedding_model,
                                vector_store=op_config.vector_store,
                                **op_config.params)

        elif op_name in C.op_registry:
            op_cls = C.resolve_op(op_name)
            op: BaseOp = op_cls(name=op_name, flow_context=self.flow_context)

        else:
            raise ValueError(f"op='{op_name}' is not registered!")

        return op

    def _print_flow(self):
        """
        Print the parsed flow structure in a readable format.
        Allows users to visualize the execution flow on screen.
        """
        assert self._parsed_flow is not None, "flow_content is not parsed!"

        logger.info(f"Expression: {self.flow_content}")
        self._print_operation_tree(self._parsed_flow, indent=0)

    def _print_operation_tree(self, op: BaseOp, indent: int = 0):
        """
        Recursively print the operation tree structure.
        
        Args:
            op: The operation to print
            indent: Current indentation level
        """
        prefix = "  " * indent
        if isinstance(op, SequentialOp):
            logger.info(f"{prefix}Sequential Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix}  Step {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        elif isinstance(op, ParallelOp):
            logger.info(f"{prefix}Parallel Execution:")
            for i, sub_op in enumerate(op.ops):
                logger.info(f"{prefix}  Branch {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)

        else:
            logger.info(f"{prefix}Operation: {op.name}")

    def _execute_flow(self):
        """
        Execute the parsed flow and return the result.
        
        Returns:
            The result of executing the flow
        """
        return self._parsed_flow.execute()
