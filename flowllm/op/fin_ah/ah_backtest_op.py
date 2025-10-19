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
import ray
import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import pearsonr, spearmanr
from sklearn.linear_model import Ridge

from flowllm.app import FlowLLMApp
from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.plot_utils import plot_figure

TOP_5 = 5  # 选股池大小（top5）
TOP_10 = 10  # 选股池大小（top10）
BLOCK_SIZE = 10  # 分块数量（用于分析收益分布）


@C.register_op(register_app="FlowLLM")
class AhBacktestTableOp(BaseRayOp):
    """回测策略效果（父Op）"""

    def __init__(
        self,
        input_dir: str = "data/feature",
        output_dir: str = "data/backtest",
        max_samples: int = 512,
        use_weekly: bool = False,
        start_date: int = 20200101,
        feature_columns: List[str] = None,
        label_column: str = "a_label",
        label_normalization: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_samples = max_samples
        self.use_weekly = use_weekly
        self.start_date = start_date
        self.feature_columns = feature_columns
        self.label_column = label_column
        self.label_normalization = label_normalization
        # 自动根据use_weekly设置文件后缀
        self.file_suffix = "weekly" if use_weekly else "daily"
        
        # 验证label_normalization参数
        if label_normalization and label_normalization not in ["mean", "median"]:
            raise ValueError(f"label_normalization must be 'mean', 'median', or None, got '{label_normalization}'")

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

    def _get_output_filename(self, base_filename: str) -> str:
        """生成带后缀的输出文件名"""
        if self.file_suffix:
            name, ext = os.path.splitext(base_filename)
            return f"{name}_{self.file_suffix}{ext}"
        return base_filename

    def _save_dataframe(self, df: pd.DataFrame, filename: str) -> None:
        """保存DataFrame到CSV"""
        output_filename = self._get_output_filename(filename)
        output_path = os.path.join(self.output_dir, output_filename)
        df.to_csv(output_path, index=False)
        logger.info(f"Saved {output_filename}: {len(df)} rows")

    def _plot_strategies(self, final_df: pd.DataFrame, dates: List[int]) -> None:
        """绘制策略收益曲线"""
        strategy_cols = [c for c in final_df.columns if "_uplift" in c]
        if not strategy_cols:
            logger.warning("No strategy columns found for plotting")
            return
        
        logger.info(f"Plotting {len(strategy_cols)} strategies: {strategy_cols}")
        plot_dict = {col: [v / 100 for v in final_df[col].tolist()] for col in strategy_cols}
        plot_filename = self._get_output_filename("ah_strategy.pdf")
        plot_output = os.path.join(self.output_dir, plot_filename)
        plot_figure(plot_dict, output_path=plot_output, xs=[str(d) for d in dates], ticks_gap=90)
        logger.info(f"Saved strategy plot to {plot_output}")

    def _normalize_labels(self, feature_df: pd.DataFrame) -> pd.DataFrame:
        """对每天的label进行归一化处理（减去均值或中位数）"""
        if not self.label_normalization:
            return feature_df
        
        logger.info(f"Normalizing labels using {self.label_normalization}")
        feature_df = feature_df.copy()
        
        # 获取所有label列（包括a_label和a_label_1d到a_label_5d）
        label_cols = [col for col in feature_df.columns if col.startswith("a_label")]
        
        for dt in feature_df["dt"].unique():
            dt_mask = feature_df["dt"] == dt
            
            for label_col in label_cols:
                if label_col not in feature_df.columns:
                    continue
                
                label_values = feature_df.loc[dt_mask, label_col]
                
                if self.label_normalization == "mean":
                    baseline = label_values.mean()
                elif self.label_normalization == "median":
                    baseline = label_values.median()
                else:
                    continue
                
                feature_df.loc[dt_mask, label_col] = label_values - baseline
        
        logger.info(f"Label normalization completed for {len(label_cols)} label columns")
        return feature_df

    def execute(self) -> None:
        """执行回测"""
        self._ensure_output_dir()
        
        # 加载特征数据
        feature_df = self._load_feature_data()
        
        # 对label进行归一化处理
        feature_df = self._normalize_labels(feature_df)
        
        # 设置context参数
        self.context.max_samples = self.max_samples
        self.context.feature_df = feature_df
        self.context.feature_columns = self.feature_columns
        self.context.label_column = self.label_column
        
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
    def _calculate_ic(pred: np.ndarray, actual: np.ndarray) -> Tuple[float, float]:
        """计算IC和RIC"""
        try:
            ic, _ = pearsonr(pred, actual)
            ric, _ = spearmanr(pred, actual)
            return ic, ric
        except Exception as e:
            ray.logger.exception(f"Failed to calculate IC: {e}")
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
                "pred_value": row[pred_col] if pred_col else None,
                "label": row["a_label"],
                "actual_uplift": row["uplift"]
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
            ray.logger.warning(f"No test data for dt={dt}")
            return {"final": {}, "intermediate": []}
        
        # 获取特征列和标签列
        feature_cols = self.context.feature_columns
        label_col = self.context.label_column
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
        
        # 生成选股池（Top 5 和 Top 10）
        model_pool_5 = test_df.nlargest(TOP_5, pred_col)
        model_pool_10 = test_df.nlargest(TOP_10, pred_col)
        rule_pool_5 = test_df.nlargest(TOP_5, "ah_ratio")
        rule_pool_10 = test_df.nlargest(TOP_10, "ah_ratio")
        
        # 构建最终结果（用uplift计算实际收益，用label计算IC）
        final_result = {
            "dt": dt,
            "size": len(test_df),
            "model_ic": model_ic,
            "model_ric": model_ric,
            "rule_ic": rule_ic,
            "rule_ric": rule_ric,
            # Top5 结果
            "model_names": ",".join(model_pool_5["name"].tolist()),
            "model_uplift": model_pool_5["uplift"].mean(),
            "rule_names": ",".join(rule_pool_5["name"].tolist()),
            "rule_uplift": rule_pool_5["uplift"].mean(),
            # Top10 结果
            "model_names_10": ",".join(model_pool_10["name"].tolist()),
            "model_uplift_10": model_pool_10["uplift"].mean(),
            "rule_names_10": ",".join(rule_pool_10["name"].tolist()),
            "rule_uplift_10": rule_pool_10["uplift"].mean(),
            # 全部股票平均
            "all_uplift": test_df["uplift"].mean(),
        }
        
        # 计算分块收益（按预测值排序后分成N块，使用uplift计算实际收益）
        block_count = max(1, round(len(test_df) / BLOCK_SIZE))
        test_df_sorted = test_df.sort_values(pred_col, ascending=False)
        
        for i in range(BLOCK_SIZE):
            start_idx = i * block_count
            end_idx = (i + 1) * block_count
            block_data = test_df_sorted.iloc[start_idx:end_idx]
            final_result[f"p{i}_uplift"] = block_data["uplift"].mean() if len(block_data) > 0 else 0.0
        
        # 构建中间结果（选股池详情）
        intermediate_result = []
        intermediate_result.extend(self._create_stock_pool_records(model_pool_5, dt, "model_top5", pred_col))
        intermediate_result.extend(self._create_stock_pool_records(rule_pool_5, dt, "rule_top5"))
        intermediate_result.extend(self._create_stock_pool_records(model_pool_10, dt, "model_top10", pred_col))
        intermediate_result.extend(self._create_stock_pool_records(rule_pool_10, dt, "rule_top10"))
        
        return {"final": final_result, "intermediate": intermediate_result}


def main(
    input_dir: str = "data/feature",
    output_dir: str = "data/backtest",
    max_samples: int = 512,
    use_weekly: bool = False,
    start_date: int = 20200101,
    feature_columns: List[str] = None,
    label_column: str = "a_label",
    label_normalization: Optional[str] = None,
    ray_workers: int = 8
):
    """运行AH股回测
    
    Args:
        input_dir: 特征数据目录
        output_dir: 回测结果输出目录
        max_samples: 训练样本数量
        use_weekly: 是否使用周频数据
        start_date: 回测开始日期
        feature_columns: 使用的特征列表（必须指定）
        label_column: 使用的标签列（默认a_label，可选a_label_1d, a_label_2d, a_label_3d, a_label_4d, a_label_5d）
        label_normalization: label归一化方式（None/mean/median），每天的label减去所有股票的均值或中位数
        ray_workers: Ray并行workers数量
    """
    with FlowLLMApp(load_default_config=True) as app:
        app.service_config.ray_max_workers = ray_workers
        
        op = AhBacktestTableOp(
            input_dir=input_dir,
            output_dir=output_dir,
            max_samples=max_samples,
            use_weekly=use_weekly,
            start_date=start_date,
            feature_columns=feature_columns,
            label_column=label_column,
            label_normalization=label_normalization
        ) << AhBacktestOp()
        
        op.call()


if __name__ == "__main__":
    # 日频回测配置 - 默认使用5天标签
    daily_config = {
        "input_dir": "data/feature",
        "output_dir": "data/backtest",
        "max_samples": 512,
        "use_weekly": False,
        "start_date": 20200101,
        "feature_columns": [
            "ah_ratio",
            # "ah_amount",
            # "avg_1d_ah_pct_diff",
            # "avg_5d_ah_pct_diff",
            # "avg_1d_ah_amount_ratio",
            # "avg_5d_ah_amount_ratio",

            "avg_1d_a_pct",
            "avg_1d_hk_pct",
            "avg_5d_a_pct",
            "avg_5d_hk_pct",
            # "avg_20d_a_pct",
            # "avg_20d_hk_pct",
            "avg_1d_a_amount",
            "avg_1d_hk_amount",
            # "avg_5d_a_amount",
            # "avg_5d_hk_amount",
        ],
        "label_column": "a_label_5d",  # 可选: a_label_1d, a_label_2d, a_label_3d, a_label_4d, a_label_5d
        "label_normalization": "mean",  # None / "mean" / "median"
        "ray_workers": 8
    }
    
    # 周频回测配置
    weekly_config = {
        "input_dir": "data/feature",
        "output_dir": "data/backtest",
        "max_samples": 512,
        "use_weekly": True,
        "start_date": 20200101,
        "feature_columns": [
            "ah_ratio",
            "ah_amount5",
            "avg_3d_a_pct",
            "avg_3d_hk_pct",
            "avg_10d_a_pct",
            "avg_10d_hk_pct"
        ],
        "label_column": "a_label",  # 周频使用默认label
        "label_normalization": "mean",  # None / "mean" / "median"
        "ray_workers": 8
    }
    
    # 执行日频回测
    main(**daily_config)
    
    # 执行周频回测
    # main(**weekly_config)
    
    # 示例: 使用1天标签进行回测
    # daily_1d_config = daily_config.copy()
    # daily_1d_config["label_column"] = "a_label_1d"
    # daily_1d_config["output_dir"] = "data/backtest_1d"
    # main(**daily_1d_config)
    
    # 示例: 使用均值归一化的回测
    # daily_mean_config = daily_config.copy()
    # daily_mean_config["label_normalization"] = "mean"
    # daily_mean_config["output_dir"] = "data/backtest_mean"
    # main(**daily_mean_config)
    
    # 示例: 使用中位数归一化的回测
    # daily_median_config = daily_config.copy()
    # daily_median_config["label_normalization"] = "median"
    # daily_median_config["output_dir"] = "data/backtest_median"
    # main(**daily_median_config)
