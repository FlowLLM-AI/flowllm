"""Expression parser for FlowLLM flows.

This module provides a lightweight parser that converts a textual flow
description into a composed `BaseOp` operation tree by leveraging Python
operator overloading defined on `BaseOp` (e.g., `>>` for sequential and `|` for
parallel composition). It supports multi-line definitions where preceding lines
are executed to set up context and the last line is evaluated as the flow
expression.

Examples
--------
Simple and complex expressions are supported, including nested and mixed
sequential/parallel compositions.

1) Sequential and parallel mixing:

    op_a >> (op_b | op_c) >> op_d

2) Deeply nested with grouping and multiple branches:

    (op_a | (op_b >> (op_c | op_d))) >> (op_e | op_f) >> op_g

3) Multi-line content where earlier lines define helpers and the last line is
   the final expression that evaluates to a `BaseOp`:

    # aliasing and intermediate compositions allowed in preceding lines
    stage1 = op_a >> op_b
    branch = (op_c | op_d | (op_e >> op_f))
    enriched = stage1 >> branch
    # the last non-empty line must be an expression returning BaseOp
    (enriched | op_g) >> (op_h >> (op_i | op_j))
"""

import re

from ..context import C
from ..op import BaseOp
from ..schema import OpConfig


class ExpressionParser:
    """
    Simple flow implementation that supports parsing operation expressions using Python eval.

    Supports flow expressions like:
    - "op1 >> op2" (sequential expressions)
    - "op1 | op2" (parallel expressions)
    - "op1 >> (op2 | op3) >> op4" (mixed expressions)
    - "op1 >> (op1 | (op2 >> op3)) >> op4" (complex nested expressions)
    - "(a | (b >> (c | d))) >> (e | f) >> g"
    - "((a >> b) | (c >> (d | e)) | f) >> (g | (h >> i))"
    - Multi-branch with pre-defined partials in earlier lines:
        stage = (a >> b)
        branches = (c | (d >> e) | (f >> (g | h)))
        stage >> branches >> (i | (j >> k))

    This implementation leverages Python's operator overloading (__rshift__ and __or__)
    defined in BaseOp to construct the operation tree.
    """

    def __init__(self, flow_content: str = ""):
        """Initialize the expression parser.

        Args:
            flow_content: Raw flow script text. The final non-empty line should
                be an expression that evaluates to a `BaseOp`. Any preceding
                non-empty lines are executed to prepare the environment.
        """
        self.flow_content: str = flow_content

    def parse_flow(self) -> BaseOp:
        """
        Parse the flow content string into executable operations.

        Supports multi-line content where all preceding lines are executed with
        exec, and the final line is evaluated with eval to produce the composed
        BaseOp.

        Returns:
            BaseOp: The parsed flow as an executable operation tree
        """
        # Normalize and split lines, remove empty lines
        raw = self.flow_content.strip()
        if not raw:
            raise ValueError("flow content is empty")

        # Step 1: Extract all unique op names from the whole content (use raw)
        op_names = self._extract_op_names(raw)

        # Step 2: Create op instances for all extracted names
        env: dict = {}
        for op_name in op_names:
            env[op_name] = self._create_op(op_name)

        # Step 3: Exec all but the last line in a restricted environment
        lines = [x.strip() for x in raw.splitlines() if x.strip()]
        if len(lines) > 1:
            exec_content = "\n".join(lines[:-1])
            exec(exec_content, {"__builtins__": {}}, env)

        # Step 4: Eval the final line to get the composed op
        # The last line must be an expression that evaluates to a BaseOp
        last_line_expr = lines[-1]
        result = eval(last_line_expr, {"__builtins__": {}}, env)
        assert isinstance(result, BaseOp), f"Expression '{last_line_expr}' did not evaluate to a BaseOp instance"
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
        # Build whitelist from registry and service config
        allowed_names = set()
        if C.registry_dict["op"]:
            allowed_names.update(C.registry_dict["op"].keys())
        if C.service_config is not None and C.service_config.op:
            allowed_names.update(C.service_config.op.keys())

        # Simple presence check with word boundaries to avoid partial matches
        result_names = set()
        for name in allowed_names:
            if re.search(rf"\b{re.escape(name)}\b", expression):
                result_names.add(name)

        return result_names

    @staticmethod
    def _create_op(op_name: str) -> BaseOp:
        """
        Create an operation instance from operation name.

        Args:
            op_name: Name of the operation

        Returns:
            BaseOp: The created operation instance
        """
        # service_config may be None in tests or minimal setups
        if C.service_config is not None and op_name in C.service_config.op:
            op_config: OpConfig = C.service_config.op[op_name]
        else:
            op_config: OpConfig = OpConfig()

        if op_config.backend in C.registry_dict["op"]:
            op_cls = C.get_op_class(op_config.backend)

        elif op_name in C.registry_dict["op"]:
            op_cls = C.get_op_class(op_name)

        else:
            raise ValueError(f"op=`{op_name}` is not registered!")

        kwargs = {
            "name": op_name,
            "max_retries": op_config.max_retries,
            "raise_exception": op_config.raise_exception,
            **op_config.params,
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
