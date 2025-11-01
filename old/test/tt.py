import asyncio

def sync_function(x):
    import time
    time.sleep(2)  # 模拟耗时操作（如文件读写、CPU 计算）
    return x * x

async def async_wrapper(x):
    # 在线程中运行同步函数
    result = await asyncio.to_thread(sync_function, x)
    return result

async def main():
    result = await async_wrapper(5)
    print(result)  # 输出: 25

asyncio.run(main())