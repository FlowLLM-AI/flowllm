import re

from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.schema.service_config import OpConfig


class ExpressionParser:
    """
    Simple flow implementation that supports parsing operation expressions using Python eval.

    Supports flow expressions like:
    - "op1 >> op2" (sequential expressions)
    - "op1 | op2" (parallel expressions)  
    - "op1 >> (op2 | op3) >> op4" (mixed expressions)
    - "op1 >> (op1 | (op2 >> op3)) >> op4" (complex nested expressions)
    
    This implementation leverages Python's operator overloading (__rshift__ and __or__)
    defined in BaseOp to construct the operation tree.
    """

    def __init__(self, flow_content: str = ""):
        self.flow_content: str = flow_content

    def parse_flow(self) -> BaseOp:
        """
        Parse the flow content string into executable operations.
        
        Returns:
            BaseOp: The parsed flow as an executable operation tree
        """
        op_instances: dict = {}
        expression = re.sub(r'\s+', ' ', self.flow_content.strip())

        # Step 1: Extract all unique op names from the expression
        op_names = self._extract_op_names(expression)

        # Step 2: Create op instances for all extracted names
        for op_name in op_names:
            op_instances[op_name] = self._create_op(op_name)

        # Step 3: Execute the expression using Python eval with op instances as context
        result = eval(expression, {"__builtins__": {}}, op_instances)
        assert isinstance(result, BaseOp), f"Expression '{expression}' did not evaluate to a BaseOp instance"
        return result

    @staticmethod
    def _extract_op_names(expression: str) -> set:
        """
        Extract all operation names from the expression.
        
        Args:
            expression: The expression string
            
        Returns:
            set: Set of unique operation names
        """
        op_names = set()
        pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'
        forbidden_name_set = {'and', 'or', 'not', 'in', 'is', 'if', 'else', 'elif',
                              'for', 'while', 'def', 'class', 'import', 'from',
                              'return', 'yield', 'try', 'except', 'finally',
                              'with', 'as', 'pass', 'break', 'continue'}
        for match in re.finditer(pattern, expression):
            op_name = match.group()
            if op_name not in forbidden_name_set:
                op_names.add(op_name)

        return op_names

    @staticmethod
    def _create_op(op_name: str) -> BaseOp:
        """
        Create an operation instance from operation name.
        
        Args:
            op_name: Name of the operation
            
        Returns:
            BaseOp: The created operation instance
        """
        if op_name in C.service_config.op:
            op_config: OpConfig = C.service_config.op[op_name]
        else:
            op_config: OpConfig = OpConfig()

        if op_config.backend in C.registry_dict["op"]:
            op_cls = C.get_op_class(op_config.backend)

        elif op_name in C.registry_dict["op"]:
            op_cls = C.get_op_class(op_name)

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
