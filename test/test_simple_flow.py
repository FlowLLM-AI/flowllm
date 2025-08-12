#!/usr/bin/env python3
"""
Test script for SimpleFlow implementation
Demonstrates parsing and execution of flow expressions
"""

import sys
import os
from concurrent.futures import ThreadPoolExecutor
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from flowllm.flow.simple_flow import SimpleFlow
from flowllm.context.pipeline_context import FlowContext
from flowllm.context.service_context import ServiceContext
from flowllm.op.base_op import BaseOp


class TestOp(BaseOp):
    """Test operation for demonstration purposes"""
    
    def execute(self, data=None):
        # Simulate some processing time
        time.sleep(0.1)
        result = f"{self.name}_result"
        print(f"  🔧 Executing {self.name} -> {result}")
        return result


def create_test_context():
    """Create test contexts with sample operations"""
    
    # Create service context with thread pool for parallel execution
    service_context = ServiceContext(thread_pool=ThreadPoolExecutor(max_workers=4))
    
    # Create test operations
    op1 = TestOp("op1", service_context=service_context)
    op2 = TestOp("op2", service_context=service_context)
    op3 = TestOp("op3", service_context=service_context)
    op4 = TestOp("op4", service_context=service_context)
    
    # Create pipeline context with operation dictionary
    pipeline_context = FlowContext(
        op_dict={
            "op1": op1,
            "op2": op2,
            "op3": op3,
            "op4": op4
        }
    )
    
    return pipeline_context, service_context


def test_simple_expression():
    """Test simple sequential expression"""
    print("\n" + "="*60)
    print("TEST 1: Simple sequential expression 'op1 >> op2'")
    print("="*60)
    
    pipeline_context, service_context = create_test_context()
    
    flow = SimpleFlow(
        flow_name="simple_sequential",
        flow_content="op1 >> op2",
        pipeline_context=pipeline_context,
        service_context=service_context
    )
    
    flow.print_flow()
    result = flow.execute_flow()
    print(f"Final result: {result}")


def test_parallel_expression():
    """Test parallel expression"""
    print("\n" + "="*60)
    print("TEST 2: Parallel expression 'op1 | op2'")
    print("="*60)
    
    pipeline_context, service_context = create_test_context()
    
    flow = SimpleFlow(
        flow_name="simple_parallel",
        flow_content="op1 | op2",
        pipeline_context=pipeline_context,
        service_context=service_context
    )
    
    flow.print_flow()
    result = flow.execute_flow()
    print(f"Final result: {result}")


def test_mixed_expression():
    """Test mixed expression with parentheses"""
    print("\n" + "="*60)
    print("TEST 3: Mixed expression 'op1 >> (op2 | op3) >> op4'")
    print("="*60)
    
    pipeline_context, service_context = create_test_context()
    
    flow = SimpleFlow(
        flow_name="mixed_flow",
        flow_content="op1 >> (op2 | op3) >> op4",
        pipeline_context=pipeline_context,
        service_context=service_context
    )
    
    flow.print_flow()
    result = flow.execute_flow()
    print(f"Final result: {result}")


def test_complex_expression():
    """Test complex nested expression"""
    print("\n" + "="*60)
    print("TEST 4: Complex expression 'op1 >> (op1 | (op2 >> op3)) >> op4'")
    print("="*60)
    
    pipeline_context, service_context = create_test_context()
    
    flow = SimpleFlow(
        flow_name="complex_flow",
        flow_content="op1 >> (op1 | (op2 >> op3)) >> op4",
        pipeline_context=pipeline_context,
        service_context=service_context
    )
    
    flow.print_flow()
    result = flow.execute_flow()
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
        
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
