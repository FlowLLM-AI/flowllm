"""
AH股回测Op
负责回测策略效果：
1. 使用Ridge回归训练模型
2. 计算IC和RIC
3. 生成选股池（top5）
4. 保存回测中间结果和最终结果
"""
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import Ridge

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.plot_utils import plot_figure

TOP_N = 5  # 选股池大小
BLOCK_SIZE = 10  # 分块数量（用于分析收益分布）


@C.register_op(register_app="FlowLLM")
class AhBacktestTableOp(BaseRayOp):
    """回测策略效果（父Op）"""

    def __init__(
        self,
        input_dir: str = "data/feature",
        output_dir: str = "data/backtest",
        max_samples: int = 512,
        use_open: bool = True,
        use_weekly: bool = False,
        start_date: int = 20200101,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_samples = max_samples
        self.use_open = use_open
        self.use_weekly = use_weekly
        self.start_date = start_date

    def _ensure_output_dir(self) -> None:
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_feature_data(self) -> pd.DataFrame:
        """加载特征数据"""
        cache_name = "feature_weekly.csv" if self.use_weekly else "feature_daily.csv"
        feature_path = os.path.join(self.input_dir, cache_name)
        
        if not os.path.exists(feature_path):
            raise FileNotFoundError(
                f"Feature file not found: {feature_path}\n"
                f"Please run AhFeatureTableOp first to generate features."
            )
        
        df = pd.read_csv(feature_path)
        
        # 删除NaN值
        nan_count = df.isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"Dropping {nan_count} NaN values from feature data")
            df = df.dropna()
        
        logger.info(f"Loaded features: {df.shape} from {feature_path}")
        return df

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """保存DataFrame到CSV"""
        output_path = os.path.join(self.output_dir, filename)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {filename}: {len(df)} rows")

    def _plot_strategies(self, final_df: pd.DataFrame, dates: List[int]) -> None:
        """绘制策略收益曲线"""
        strategy_cols = [c for c in final_df.columns if "_uplift" in c]
        if not strategy_cols:
            logger.warning("No strategy columns found for plotting")
            return
        
        logger.info(f"Plotting {len(strategy_cols)} strategies: {strategy_cols}")
        plot_dict = {col: [v / 100 for v in final_df[col].tolist()] for col in strategy_cols}
        plot_output = os.path.join(self.output_dir, "ah_strategy.pdf")
        plot_figure(plot_dict, output_path=plot_output, xs=[str(d) for d in dates], ticks_gap=90)
        logger.info(f"Saved strategy plot to {plot_output}")

    def execute(self) -> None:
        """执行回测"""
        self._ensure_output_dir()
        
        # 加载特征数据
        feature_df = self._load_feature_data()
        
        # 设置context参数
        self.context.max_samples = self.max_samples
        self.context.use_open = self.use_open
        self.context.feature_df = feature_df
        
        # 获取回测日期列表
        dt_list = sorted(feature_df.loc[feature_df.a_flag == 1, "dt"].unique())
        self.context.dt_a_list = dt_list
        logger.info(f"Available dates: {dt_list[0]} to {dt_list[-1]} ({len(dt_list)} days)")
        
        # 筛选回测日期
        backtest_dates = [d for d in dt_list if d >= self.start_date]
        logger.info(f"Backtest dates: {backtest_dates[0]} to {backtest_dates[-1]} ({len(backtest_dates)} days)")
        
        # 并行执行回测
        result = self.submit_and_join_parallel_op(op=self.ops[0], dt=backtest_dates)
        
        # 整理并保存最终结果
        final_df = pd.DataFrame([r["final"] for r in result]).sort_values("dt")
        self._save_dataframe(final_df, "backtest_final.csv")
        
        # 整理并保存中间结果（选股池）
        intermediate_records = [stock for r in result for stock in r["intermediate"]]
        intermediate_df = pd.DataFrame(intermediate_records)
        self._save_dataframe(intermediate_df, "backtest_pools.csv")
        
        # 打印IC/RIC统计
        for metric in ["model_ic", "model_ric", "rule_ic", "rule_ric"]:
            mean_val = final_df[metric].mean()
            std_val = final_df[metric].std()
            logger.info(f"{metric}: mean={mean_val:.4f}, std={std_val:.4f}")
        
        # 绘制策略收益曲线
        self._plot_strategies(final_df, backtest_dates)
        
        logger.info(f"Backtest completed: {len(backtest_dates)} days, results in {self.output_dir}")


class AhBacktestOp(BaseOp):
    """单日回测（子Op）"""

    @staticmethod
    def _get_feature_columns(feature_df: pd.DataFrame) -> List[str]:
        """获取特征列（根据是否周频自动选择）"""
        # 基础特征：AH比价
        features = ["ah_ratio"]
        
        # 成交额特征（周频用5日均值，日频用当日）
        if "ah_amount5" in feature_df.columns:
            features.append("ah_amount5")  # 周频
        else:
            features.append("ah_amount")  # 日频
        
        # 历史涨跌幅特征
        features.extend(["avg_20d_a_pct", "avg_20d_hk_pct"])
        
        return features

    @staticmethod
    def _calculate_ic(pred: np.ndarray, actual: np.ndarray) -> Tuple[float, float]:
        """计算IC和RIC"""
        try:
            ic, _ = pearsonr(pred, actual)
            ric, _ = spearmanr(pred, actual)
            return ic, ric
        except Exception as e:
            logger.exception(f"Failed to calculate IC: {e}")
            return 0.0, 0.0

    @staticmethod
    def _create_stock_pool_records(
        df: pd.DataFrame,
        dt: int,
        strategy: str,
        pred_col: Optional[str] = None
    ) -> List[Dict]:
        """创建选股池记录"""
        records = []
        for _, row in df.iterrows():
            records.append({
                "dt": dt,
                "strategy": strategy,
                "name": row["name"],
                "code": row["code"],
                "ah_ratio": row["ah_ratio"],
                "pred_uplift": row[pred_col] if pred_col else None,
                "actual_uplift": row["a_label"]
            })
        return records

    def execute(self) -> Dict:
        dt = self.context.dt
        feature_df = self.context.feature_df
        max_samples = self.context.max_samples
        
        # 准备训练集和测试集
        train_dates = [d for d in self.context.dt_a_list if d < dt][-max_samples:-1]
        train_df = feature_df.loc[feature_df.dt.isin(train_dates)].copy()
        test_df = feature_df.loc[feature_df.dt == dt].copy()
        
        if test_df.empty:
            logger.warning(f"No test data for dt={dt}")
            return {"final": {}, "intermediate": []}
        
        # 获取特征列
        feature_cols = self._get_feature_columns(feature_df)
        label_col = "a_label"
        pred_col = "pred_y"
        
        # 准备数据
        train_x = train_df[feature_cols].values
        train_y = train_df[label_col].values
        test_x = test_df[feature_cols].values
        test_y = test_df[label_col].values
        rule_score = test_df["ah_ratio"].values
        
        # 训练Ridge回归模型
        model = Ridge(alpha=1.0)
        model.fit(train_x, train_y)
        
        # 预测
        pred_y = model.predict(test_x)
        test_df[pred_col] = pred_y
        
        # 计算IC和RIC
        model_ic, model_ric = self._calculate_ic(pred_y, test_y)
        rule_ic, rule_ric = self._calculate_ic(rule_score, test_y)
        
        # 生成选股池（Top N）
        model_pool = test_df.nlargest(TOP_N, pred_col)
        rule_pool = test_df.nlargest(TOP_N, "ah_ratio")
        
        # 构建最终结果
        final_result = {
            "dt": dt,
            "size": len(test_df),
            "model_ic": model_ic,
            "model_ric": model_ric,
            "rule_ic": rule_ic,
            "rule_ric": rule_ric,
            "model_names": ",".join(model_pool["name"].tolist()),
            "model_uplift": model_pool[label_col].mean(),
            "rule_names": ",".join(rule_pool["name"].tolist()),
            "rule_uplift": rule_pool[label_col].mean(),
            "all_uplift": test_y.mean(),
        }
        
        # 计算分块收益（按预测值排序后分成N块）
        block_count = max(1, round(len(test_df) / BLOCK_SIZE))
        test_df_sorted = test_df.sort_values(pred_col, ascending=False)
        
        for i in range(BLOCK_SIZE):
            start_idx = i * block_count
            end_idx = (i + 1) * block_count
            block_data = test_df_sorted.iloc[start_idx:end_idx]
            final_result[f"p{i}_uplift"] = block_data[label_col].mean() if len(block_data) > 0 else 0.0
        
        # 构建中间结果（选股池详情）
        intermediate_result = []
        intermediate_result.extend(self._create_stock_pool_records(model_pool, dt, "model", pred_col))
        intermediate_result.extend(self._create_stock_pool_records(rule_pool, dt, "rule"))
        
        return {"final": final_result, "intermediate": intermediate_result}


def main(
    use_weekly: bool = False,
    use_open: bool = True,
    max_samples: int = 512,
    start_date: int = 20200101,
    ray_workers: int = 8
):
    """运行AH股回测"""
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = ray_workers
        
        op = AhBacktestTableOp(
            input_dir="data/feature",
            output_dir="data/backtest",
            max_samples=max_samples,
            use_open=use_open,
            use_weekly=use_weekly,
            start_date=start_date
        ) << AhBacktestOp()
        
        op.call()


if __name__ == "__main__":
    # 日频回测
    # main(use_weekly=False, use_open=True, max_samples=512, start_date=20200101)
    
    # 周频回测
    main(use_weekly=True, use_open=True, max_samples=512, start_date=20200101)
