"""
AH股策略Pipeline
串联所有Op完成完整的数据处理和回测流程：
1. 下载原始数据 (AhDownloadOp)
2. 修复数据 (AhFixOp)
3. 生成特征标签 (AhFeatureTableOp + AhDailyFeatureOp/AhWeeklyFeatureOp)
4. 回测策略 (AhBacktestTableOp + AhBacktestOp)
"""
from flowllm.app import FlowLLMApp
from flowllm.op.fin_ah.ah_download_op import AhDownloadOp
from flowllm.op.fin_ah.ah_fix_op import AhFixOp
from flowllm.op.fin_ah.ah_feature_op import (
    AhFeatureTableOp,
    AhDailyFeatureOp,
    AhWeeklyFeatureOp
)
from flowllm.op.fin_ah.ah_backtest_op import (
    AhBacktestTableOp,
    AhBacktestOp
)


def run_ah_pipeline(
    use_weekly: bool = True,
    use_open: bool = True,
    max_samples: int = 512,
    start_date: int = 20200101,
    ray_max_workers: int = 8,
    skip_download: bool = True,
    skip_fix: bool = False
):
    """
    运行AH股策略完整流程
    
    注意：各个Op之间通过文件系统（data目录）交互，不依赖context传递数据
    每个Op都可以独立运行，只要前置的数据文件存在
    
    Args:
        use_weekly: 是否使用周频数据（True=周频，False=日频）
        use_open: 是否使用开盘价计算收益（避免look-ahead bias）
        max_samples: 回测时使用的最大训练样本数
        start_date: 回测开始日期
        ray_max_workers: Ray并行worker数量
        skip_download: 是否跳过下载步骤（默认True，假设已有data/origin数据）
        skip_fix: 是否跳过修复步骤（默认False，通常需要修复）
    """
    with FlowLLMApp(load_default_config=True) as app:
        # 配置Ray
        app.service_config.ray_max_workers = ray_max_workers
        
        ops = []
        
        # 1. 下载数据（可选）
        if not skip_download:
            ops.append(AhDownloadOp(output_dir="data/origin"))
        
        # 2. 修复数据（可选）
        if not skip_fix:
            ops.append(AhFixOp(input_dir="data/origin", output_dir="data/fixed"))
        
        # 3. 生成特征（必需）
        feature_op = (
            AhFeatureTableOp(
                input_dir="data/fixed",
                output_dir="data/feature",
                use_open=use_open,
                use_weekly=use_weekly
            ) 
            << AhDailyFeatureOp() 
            << AhWeeklyFeatureOp()
        )
        ops.append(feature_op)
        
        # 4. 回测（必需）
        backtest_op = (
            AhBacktestTableOp(
                input_dir="data/feature",
                output_dir="data/backtest",
                max_samples=max_samples,
                use_open=use_open,
                use_weekly=use_weekly,
                start_date=start_date
            )
            << AhBacktestOp()
        )
        ops.append(backtest_op)
        
        # 构建Pipeline：通过 << 串联所有Op
        pipeline = ops[0]
        for op in ops[1:]:
            pipeline = pipeline << op
        
        # 执行Pipeline
        result = pipeline.call()
        print(f"\n{'='*60}")
        print("Pipeline completed successfully!")
        print(f"{'='*60}")
        print(f"Result: {result}")
        
        return result


def run_download_only():
    """仅下载数据"""
    with FlowLLMApp(load_default_config=True) as app:
        op = AhDownloadOp(output_dir="data/origin")
        result = op.call()
        print(f"Download completed: {result}")
        return result


def run_fix_only():
    """仅修复数据"""
    with FlowLLMApp(load_default_config=True) as app:
        op = AhFixOp(input_dir="data/origin", output_dir="data/fixed")
        result = op.call()
        print(f"Fix completed: {result}")
        return result


def run_feature_only(use_weekly: bool = True, use_open: bool = True):
    """仅生成特征"""
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8
        
        op = (
            AhFeatureTableOp(
                input_dir="data/fixed",
                output_dir="data/feature",
                use_open=use_open,
                use_weekly=use_weekly
            )
            << AhDailyFeatureOp()
            << AhWeeklyFeatureOp()
        )
        result = op.call()
        print(f"Feature generation completed: {result}")
        return result


def run_backtest_only(
    use_weekly: bool = True,
    use_open: bool = True,
    max_samples: int = 512,
    start_date: int = 20200101
):
    """仅运行回测"""
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = 8
        
        op = (
            AhBacktestTableOp(
                input_dir="data/feature",
                output_dir="data/backtest",
                max_samples=max_samples,
                use_open=use_open,
                use_weekly=use_weekly,
                start_date=start_date
            )
            << AhBacktestOp()
        )
        result = op.call()
        print(f"Backtest completed: {result}")
        return result


if __name__ == "__main__":
    # 方式1: 运行完整Pipeline（假设已有data/origin数据）
    # run_ah_pipeline(
    #     use_weekly=True,
    #     use_open=True,
    #     max_samples=512,
    #     start_date=20200101,
    #     ray_max_workers=8,
    #     skip_download=True,  # 跳过下载，使用已有数据
    #     skip_fix=False       # 不跳过修复
    # )
    
    # 方式3: 分步独立运行（各Op通过data目录交互）
    # run_download_only()                    # 生成 data/origin/*
    run_fix_only()                         # 读取 data/origin/*, 生成 data/fixed/*
    # run_feature_only(use_weekly=True)      # 读取 data/fixed/*, 生成 data/feature/*
    # run_backtest_only(use_weekly=True)     # 读取 data/feature/*, 生成 data/backtest/*

