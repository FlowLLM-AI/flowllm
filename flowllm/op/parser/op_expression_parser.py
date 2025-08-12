"""
Operation Expression Parser

Parses text-based operation expressions and converts them to executable operation chains.
Supports expressions like: "op1 >> (op2 | op3) >> op4" or "op1 >> (op1 | (op2 >> op3)) >> op4"

Usage examples:
    # Parse and execute expression
    parser = OpExpressionParser()
    result = parser.parse_and_execute("op1 >> op2 >> op3", op_registry)
    
    # Parse to AST only
    ast = parser.parse("op1 >> (op2 | op3)")
    
    # Execute with custom operations
    ops = {"op1": MyOp1(), "op2": MyOp2(), "op3": MyOp3()}
    result = parser.execute_expression("op1 >> (op2 | op3)", ops)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Union, Any

from loguru import logger

from flowllm.op.base_op import BaseOp
from flowllm.op.parallel_op import ParallelOp
from flowllm.op.sequential_op import SequentialOp


class TokenType(Enum):
    """Token types for expression parsing"""
    IDENTIFIER = "IDENTIFIER"
    SEQUENTIAL = "SEQUENTIAL"  # >>
    PARALLEL = "PARALLEL"  # |
    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    EOF = "EOF"


@dataclass
class Token:
    """Token representation"""
    type: TokenType
    value: str
    position: int


class Tokenizer:
    """Tokenizes operation expressions into tokens"""

    def __init__(self, expression: str):
        self.expression = expression.strip()
        self.position = 0
        self.tokens: List[Token] = []

    def tokenize(self) -> List[Token]:
        """Tokenize the expression into a list of tokens"""
        self.tokens = []
        self.position = 0

        while self.position < len(self.expression):
            self._skip_whitespace()

            if self.position >= len(self.expression):
                break

            char = self.expression[self.position]

            if char == '>':
                if self._peek() == '>':
                    self.tokens.append(Token(TokenType.SEQUENTIAL, '>>', self.position))
                    self.position += 2
                else:
                    raise SyntaxError(f"Invalid operator '>' at position {self.position}")

            elif char == '|':
                self.tokens.append(Token(TokenType.PARALLEL, '|', self.position))
                self.position += 1

            elif char == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', self.position))
                self.position += 1

            elif char == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', self.position))
                self.position += 1

            elif char.isalnum() or char == '_':
                identifier = self._read_identifier()
                self.tokens.append(Token(TokenType.IDENTIFIER, identifier, self.position - len(identifier)))

            else:
                raise SyntaxError(f"Unexpected character '{char}' at position {self.position}")

        self.tokens.append(Token(TokenType.EOF, '', self.position))
        return self.tokens

    def _skip_whitespace(self):
        """Skip whitespace characters"""
        while self.position < len(self.expression) and self.expression[self.position].isspace():
            self.position += 1

    def _peek(self) -> str:
        """Peek at the next character without consuming it"""
        if self.position + 1 < len(self.expression):
            return self.expression[self.position + 1]
        return ''

    def _read_identifier(self) -> str:
        """Read an identifier (operation name)"""
        start = self.position
        while (self.position < len(self.expression) and
               (self.expression[self.position].isalnum() or self.expression[self.position] == '_')):
            self.position += 1
        return self.expression[start:self.position]


class ASTNode:
    """Base class for AST nodes"""
    pass


class OperationNode(ASTNode):
    """AST node for a single operation"""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"Op({self.name})"


class SequentialNode(ASTNode):
    """AST node for sequential operations (>>)"""

    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"Seq({self.left} >> {self.right})"


class ParallelNode(ASTNode):
    """AST node for parallel operations (|)"""

    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"Par({self.left} | {self.right})"


class Parser:
    """Parses tokens into an Abstract Syntax Tree (AST)"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.position = 0

    def parse(self) -> ASTNode:
        """Parse tokens into an AST"""
        result = self._parse_sequential()
        if not self._is_at_end():
            current_token = self._current_token()
            raise SyntaxError(f"Unexpected token '{current_token.value}' at position {current_token.position}")
        return result

    def _parse_sequential(self) -> ASTNode:
        """Parse sequential operations (lowest precedence)"""
        left = self._parse_parallel()

        while self._match(TokenType.SEQUENTIAL):
            right = self._parse_parallel()
            left = SequentialNode(left, right)

        return left

    def _parse_parallel(self) -> ASTNode:
        """Parse parallel operations (higher precedence than sequential)"""
        left = self._parse_primary()

        while self._match(TokenType.PARALLEL):
            right = self._parse_primary()
            left = ParallelNode(left, right)

        return left

    def _parse_primary(self) -> ASTNode:
        """Parse primary expressions (identifiers and parenthesized expressions)"""
        if self._match(TokenType.IDENTIFIER):
            return OperationNode(self._previous_token().value)

        if self._match(TokenType.LPAREN):
            expr = self._parse_sequential()
            if not self._match(TokenType.RPAREN):
                raise SyntaxError(f"Expected ')' after expression at position {self._current_token().position}")
            return expr

        current_token = self._current_token()
        raise SyntaxError(f"Expected identifier or '(' at position {current_token.position}")

    def _match(self, token_type: TokenType) -> bool:
        """Check if current token matches the given type and consume it"""
        if self._check(token_type):
            self._advance()
            return True
        return False

    def _check(self, token_type: TokenType) -> bool:
        """Check if current token is of the given type"""
        if self._is_at_end():
            return False
        return self._current_token().type == token_type

    def _advance(self) -> Token:
        """Consume and return the current token"""
        if not self._is_at_end():
            self.position += 1
        return self._previous_token()

    def _is_at_end(self) -> bool:
        """Check if we've reached the end of tokens"""
        return self._current_token().type == TokenType.EOF

    def _current_token(self) -> Token:
        """Get the current token"""
        return self.tokens[self.position]

    def _previous_token(self) -> Token:
        """Get the previous token"""
        return self.tokens[self.position - 1]


class OpExpressionExecutor:
    """Executes AST nodes using actual operation instances"""

    def __init__(self, operations: Dict[str, BaseOp]):
        self.operations = operations

    def execute(self, node: ASTNode) -> Union[BaseOp, SequentialOp, ParallelOp]:
        """Execute an AST node and return the corresponding operation"""
        if isinstance(node, OperationNode):
            if node.name not in self.operations:
                raise ValueError(f"Operation '{node.name}' not found in registry")
            return self.operations[node.name]

        elif isinstance(node, SequentialNode):
            left_op = self.execute(node.left)
            right_op = self.execute(node.right)
            return left_op >> right_op

        elif isinstance(node, ParallelNode):
            left_op = self.execute(node.left)
            right_op = self.execute(node.right)
            return left_op | right_op

        else:
            raise ValueError(f"Unknown AST node type: {type(node)}")


class OpExpressionParser:
    """Main parser class that combines tokenization, parsing, and execution"""

    def parse(self, expression: str) -> ASTNode:
        """Parse an expression string into an AST"""
        tokenizer = Tokenizer(expression)
        tokens = tokenizer.tokenize()
        parser = Parser(tokens)
        return parser.parse()

    def execute_ast(self, ast: ASTNode, operations: Dict[str, BaseOp]) -> Union[BaseOp, SequentialOp, ParallelOp]:
        """Execute an AST with the given operations"""
        executor = OpExpressionExecutor(operations)
        return executor.execute(ast)

    def parse_and_execute(self, expression: str, operations: Dict[str, BaseOp]) -> Union[
        BaseOp, SequentialOp, ParallelOp]:
        """Parse and execute an expression in one step"""
        ast = self.parse(expression)
        return self.execute_ast(ast, operations)

    def execute_expression(self, expression: str, operations: Dict[str, BaseOp], *args, **kwargs) -> Any:
        """Parse, execute, and run the expression with given arguments"""
        op_chain = self.parse_and_execute(expression, operations)
        return op_chain(*args, **kwargs)


def test_parser():
    """Test the operation expression parser"""
    from concurrent.futures import ThreadPoolExecutor
    from flowllm.context.service_context import ServiceContext

    # Create test operations
    class TestOp(BaseOp):
        def __init__(self, name: str, **kwargs):
            super().__init__(**kwargs)
            self.name = name

        def execute(self, data=None):
            import time
            time.sleep(0.1)  # Simulate execution time
            result = f"{self.name}({data})" if data else self.name
            logger.info(f"Executing {result}")
            return result

    # Create service context for parallel execution
    service_context = ServiceContext()
    service_context._data = {"thread_pool": ThreadPoolExecutor(max_workers=4)}

    # Create operation registry
    operations = {
        "op1": TestOp("op1", service_context=service_context),
        "op2": TestOp("op2", service_context=service_context),
        "op3": TestOp("op3", service_context=service_context),
        "op4": TestOp("op4", service_context=service_context),
    }

    parser = OpExpressionParser()

    # Test cases
    test_cases = [
        "op1 >> op2",
        "op1 | op2",
        "op1 >> (op2 | op3)",
        "op1 >> (op2 | op3) >> op4",
        "(op1 | op2) >> (op3 | op4)",
        "op1 >> (op1 | (op2 >> op3)) >> op4",
    ]

    for expression in test_cases:
        logger.info(f"=== Testing expression: {expression} ===")

        try:
            # Parse to AST
            ast = parser.parse(expression)
            logger.info(f"AST: {ast}")

            # Execute
            result = parser.execute_expression(expression, operations)
            logger.info(f"Result: {result}")

        except Exception as e:
            logger.error(f"Error parsing/executing '{expression}': {e}")

        logger.info("")

    # Clean up resources
    service_context._data["thread_pool"].shutdown()


if __name__ == "__main__":
    test_parser()
