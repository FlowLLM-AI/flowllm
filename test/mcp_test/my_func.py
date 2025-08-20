# your_functions.py
from mcp_service_generator import MCPServiceGenerator


def create_user(**kwargs):
    """创建用户的实际业务逻辑"""
    username = kwargs.get('username')
    email = kwargs.get('email')
    age = kwargs.get('age', 18)

    # 模拟业务逻辑
    user_data = {
        'id': 12345,
        'username': username,
        'email': email,
        'age': age,
        'created_at': '2024-01-01'
    }

    return user_data


def create_order(**kwargs):
    """创建订单的实际业务逻辑"""
    product_id = kwargs.get('product_id')
    quantity = kwargs.get('quantity')
    price = kwargs.get('price', 99.99)

    # 模拟业务逻辑
    order_data = {
        'order_id': 'ORD-001',
        'product_id': product_id,
        'quantity': quantity,
        'total_price': price * quantity
    }

    return order_data


# main.py
if __name__ == "__main__":
    # 创建服务生成器
    generator = MCPServiceGenerator("config.yaml")

    # 函数映射
    function_mapping = {
        'user_service': create_user,
        'order_service': create_order
    }

    # 自动注册所有函数
    generator.auto_register_functions(function_mapping)

    # 启动服务
    generator.run(host="0.0.0.0", port=8000)
