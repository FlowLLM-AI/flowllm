#!/usr/bin/env python3
"""
Test script for SimpleFlow implementation
Demonstrates parsing and execution of flow expressions
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from flowllm.engine.simple_flow_engine import SimpleFlowEngine
from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.schema.service_config import ServiceConfig, OpConfig


class TestOp(BaseOp):
    """Test operation for demonstration purposes"""

    def execute(self):
        # Simulate some processing time
        time.sleep(0.1)
        result = f"{self.name}_result"
        print(f"  🔧 Executing {self.name} -> {result}")
        return result


def create_test_context():
    """Create test contexts with sample operations"""

    # Setup thread pool for parallel execution
    C["thread_pool"] = ThreadPoolExecutor(max_workers=4)

    # Register TestOp in the service context
    C.op_registry.register("test_op")(TestOp)

    # Create service config with op configurations
    service_config = ServiceConfig(
        op={
            "op1": OpConfig(backend="test_op"),
            "op2": OpConfig(backend="test_op"),
            "op3": OpConfig(backend="test_op"),
            "op4": OpConfig(backend="test_op")
        }
    )

    # Create flow context
    flow_context = FlowContext(service_config=service_config)

    return flow_context


def test_simple_expression():
    """Test simple sequential expression"""
    print("\n" + "=" * 60)
    print("TEST 1: Simple sequential expression 'op1 >> op2'")
    print("=" * 60)

    flow_context = create_test_context()

    flow = SimpleFlowEngine(
        flow_name="simple_sequential",
        flow_content="op1 >> op2",
        flow_context=flow_context)

    result = flow()
    print(f"Final result: {result}")


def test_parallel_expression():
    """Test parallel expression"""
    print("\n" + "=" * 60)
    print("TEST 2: Parallel expression 'op1 | op2'")
    print("=" * 60)

    flow_context = create_test_context()

    flow = SimpleFlowEngine(
        flow_name="simple_parallel",
        flow_content="op1 | op2",
        flow_context=flow_context)

    result = flow()
    print(f"Final result: {result}")


def test_mixed_expression():
    """Test mixed expression with parentheses"""
    print("\n" + "=" * 60)
    print("TEST 3: Mixed expression 'op1 >> (op2 | op3) >> op4'")
    print("=" * 60)

    flow_context = create_test_context()

    flow = SimpleFlowEngine(
        flow_name="mixed_flow",
        flow_content="op1 >> (op2 | op3) >> op4",
        flow_context=flow_context)

    result = flow()
    print(f"Final result: {result}")


def test_complex_expression():
    """Test complex nested expression"""
    print("\n" + "=" * 60)
    print("TEST 4: Complex expression 'op1 >> (op1 | (op2 >> op3)) >> op4'")
    print("=" * 60)

    flow_context = create_test_context()

    flow = SimpleFlowEngine(
        flow_name="complex_flow",
        flow_content="op1 >> (op1 | (op2 >> op3)) >> op4",
        flow_context=flow_context)

    result = flow()
    print(f"Final result: {result}")


def main():
    """Run all tests"""
    print("🧪 Testing SimpleFlow Implementation")
    print("This demonstrates parsing and execution of flow expressions")

    try:
        test_simple_expression()
        test_parallel_expression()
        test_mixed_expression()
        test_complex_expression()

        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
