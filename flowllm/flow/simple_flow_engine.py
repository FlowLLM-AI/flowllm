import re
from typing import Optional


from flowllm.context.service_context import C
from flowllm.flow.base_flow_engine import BaseFlowEngine
from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp


@C.register_flow()
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._parsed_flow: Optional[BaseOp] = None

    def _parse_flow(self) -> BaseOp:
        """
        Parse the flow content string into executable operations.
        
        Supports expressions with operators:
        - '>>' for sequential execution
        - '|' for parallel execution
        - Parentheses for grouping operations
        
        Returns:
            BaseOp: The parsed flow as an executable operation tree
        """
        if self._parsed_flow is not None:
            return self._parsed_flow

        expression = re.sub(r'\s+', ' ', self.flow_content.strip())
        self._parsed_flow = self._parse_expression(expression)
        return self._parsed_flow

    def _parse_expression(self, expression: str) -> BaseOp:
        """
        Parse a flow expression string into operation objects.
        
        Args:
            expression: The flow expression string
            op_dict: Dictionary mapping operation names to operation instances
            
        Returns:
            BaseOp: The parsed operation tree
        """
        # Handle parentheses by recursively parsing nested expressions
        while '(' in expression:
            # Find the innermost parentheses
            start = -1
            for i, char in enumerate(expression):
                if char == '(':
                    start = i
                elif char == ')':
                    if start == -1:
                        raise ValueError(f"Mismatched parentheses in expression: {expression}")

                    # Extract and parse the inner expression
                    inner_expr = expression[start + 1:i]
                    inner_result = self._parse_expression(inner_expr, op_dict)

                    # Replace the parentheses group with a placeholder
                    placeholder = f"__TEMP_OP_{id(inner_result)}__"
                    op_dict[placeholder] = inner_result
                    expression = expression[:start] + placeholder + expression[i + 1:]
                    break
            else:
                if start != -1:
                    raise ValueError(f"Mismatched parentheses in expression: {expression}")

        # Now parse the expression without parentheses
        return self._parse_flat_expression(expression, op_dict)

    def _parse_flat_expression(self, expression: str, op_dict: dict) -> BaseOp:
        """
        Parse a flat expression (no parentheses) into operation objects.
        
        Args:
            expression: The flat expression string
            op_dict: Dictionary mapping operation names to operation instances
            
        Returns:
            BaseOp: The parsed operation tree
        """
        # Split by '>>' first (sequential has higher precedence)
        sequential_parts = [part.strip() for part in expression.split(self.SEQ_SYMBOL)]

        if len(sequential_parts) > 1:
            # Parse each part and create sequential operation
            parsed_parts = []
            for part in sequential_parts:
                parsed_parts.append(self._parse_parallel_expression(part, op_dict))

            return SequentialOp(
                ops=parsed_parts,
                pipeline_context=self.pipeline_context,
                service_context=self.service_context
            )
        else:
            # No sequential operators, parse for parallel
            return self._parse_parallel_expression(expression, op_dict)

    def _parse_parallel_expression(self, expression: str, op_dict: dict) -> BaseOp:
        """
        Parse a parallel expression (operations separated by |).
        
        Args:
            expression: The expression string
            op_dict: Dictionary mapping operation names to operation instances
            
        Returns:
            BaseOp: The parsed operation (single op or parallel op)
        """
        parallel_parts = [part.strip() for part in expression.split(self.PARALLEL_SYMBOL)]

        if len(parallel_parts) > 1:
            # Create parallel operation
            parsed_parts = []
            for part in parallel_parts:
                op_name = part.strip()
                if op_name not in op_dict:
                    raise ValueError(f"Operation '{op_name}' not found in pipeline context")
                parsed_parts.append(op_dict[op_name])

            return ParallelOp(
                ops=parsed_parts,
                pipeline_context=self.pipeline_context,
                service_context=self.service_context
            )
        else:
            # Single operation
            op_name = expression.strip()
            if op_name not in op_dict:
                raise ValueError(f"Operation '{op_name}' not found in pipeline context")
            return op_dict[op_name]

    def print_flow(self):
        """
        Print the parsed flow structure in a readable format.
        Allows users to visualize the execution flow on screen.
        """
        if self._parsed_flow is None:
            self.parse_flow()

        print(f"\n=== Flow: {self.flow_name} ===")
        print(f"Expression: {self.flow_content}")
        print("Parsed Structure:")
        self._print_operation_tree(self._parsed_flow, indent=0)
        print("=" * (len(f"Flow: {self.flow_name}") + 8))

    def _print_operation_tree(self, op: BaseOp, indent: int = 0):
        """
        Recursively print the operation tree structure.
        
        Args:
            op: The operation to print
            indent: Current indentation level
        """
        prefix = "  " * indent

        if isinstance(op, SequentialOp):
            print(f"{prefix}Sequential Execution:")
            for i, sub_op in enumerate(op.ops):
                print(f"{prefix}  Step {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)
        elif isinstance(op, ParallelOp):
            print(f"{prefix}Parallel Execution:")
            for i, sub_op in enumerate(op.ops):
                print(f"{prefix}  Branch {i + 1}:")
                self._print_operation_tree(sub_op, indent + 2)
        else:
            print(f"{prefix}Operation: {op.name}")

    def execute_flow(self):
        """
        Execute the parsed flow and return the result.
        
        Returns:
            The result of executing the flow
        """
        if self._parsed_flow is None:
            self.parse_flow()

        print(f"\n🚀 Executing flow: {self.flow_name}")
        print(f"📝 Expression: {self.flow_content}")

        try:
            result = self._parsed_flow()
            print(f"✅ Flow execution completed successfully")
            return result
        except Exception as e:
            print(f"❌ Flow execution failed: {str(e)}")
            raise
