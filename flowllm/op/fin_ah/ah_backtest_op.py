"""
AH股回测Op
负责回测策略效果：
1. 使用Ridge回归训练模型
2. 计算IC和RIC
3. 生成选股池（top5）
4. 保存回测中间结果和最终结果
"""
from typing import List
import os
import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import spearmanr, pearsonr
from sklearn.linear_model import Ridge

from flowllm.context.service_context import C
from flowllm.op import BaseOp, BaseRayOp
from flowllm.utils.plot_utils import plot_figure


@C.register_op(register_app="FlowLLM")
class AhBacktestTableOp(BaseRayOp):
    """回测策略效果（父Op）"""

    def __init__(self,
                 input_dir: str = "data/feature",
                 output_dir: str = "data/backtest",
                 max_samples: int = 512,
                 use_open: bool = True,
                 use_weekly: bool = False,
                 start_date: int = 20200101,
                 **kwargs):
        super().__init__(**kwargs)
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_samples = max_samples
        self.use_open = use_open
        self.use_weekly = use_weekly
        self.start_date = start_date

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _load_feature_data(self) -> pd.DataFrame:
        """加载特征数据（支持独立运行）"""
        if self.use_weekly:
            cache_name = "feature_weekly.csv"
        else:
            cache_name = "feature_daily.csv"
        
        feature_path = os.path.join(self.input_dir, cache_name)
        
        if not os.path.exists(feature_path):
            raise FileNotFoundError(
                f"Feature file not found: {feature_path}\n"
                f"Please run AhFeatureTableOp first to generate features."
            )
        
        feature_df = pd.read_csv(feature_path)
        
        # 验证数据
        nan_size = feature_df.isnull().sum().sum()
        if nan_size > 0:
            logger.warning(f"Feature table has {nan_size} NaN values, will drop them")
            feature_df = feature_df.dropna()
        
        logger.info(f"Loaded feature data from {feature_path}, shape={feature_df.shape}")
        return feature_df

    def execute(self):
        """执行回测"""
        self._ensure_output_dir()
        
        # 加载特征数据（支持独立运行和Pipeline运行）
        feature_df = self._load_feature_data()
        
        # 设置参数到context
        self.context.max_samples = self.max_samples
        self.context.use_open = self.use_open
        self.context.feature_df = feature_df
        
        # 获取回测日期列表
        dt_a_list = sorted(set(feature_df.loc[feature_df.a_flag == 1, "dt"]))
        self.context.dt_a_list = dt_a_list
        logger.info(f"Date range: {dt_a_list[0]} to {dt_a_list[-1]}, total {len(dt_a_list)} days")
        
        # 筛选回测日期
        dts = [x for x in dt_a_list if x >= self.start_date]
        logger.info(f"Backtest dates: {dts[0]} to {dts[-1]}, total {len(dts)} days")
        
        # 并行执行回测
        b_op = self.ops[0]  # AhBacktestOp
        result = self.submit_and_join_parallel_op(op=b_op, dt=dts)
        
        # 整理最终结果
        final_df = pd.DataFrame([r["final"] for r in result]).sort_values(["dt"])
        
        # 保存最终结果
        final_output_path = os.path.join(self.output_dir, "backtest_final.csv")
        final_df.to_csv(final_output_path, index=False)
        logger.info(f"Saved final backtest results to {final_output_path}")
        
        # 整理中间结果（每天的选股池）
        intermediate_records = []
        for r in result:
            for stock in r["intermediate"]:
                intermediate_records.append(stock)
        
        intermediate_df = pd.DataFrame(intermediate_records)
        intermediate_output_path = os.path.join(self.output_dir, "backtest_pools.csv")
        intermediate_df.to_csv(intermediate_output_path, index=False)
        logger.info(f"Saved intermediate backtest results to {intermediate_output_path}")
        
        # 打印统计信息
        for key in ["model_ic", "model_ric", "rule_ic", "rule_ric"]:
            logger.info(f"{key}: mean={final_df[key].mean():.4f}, std={final_df[key].std():.4f}")
        
        # 绘制策略收益曲线
        strategy_list = [x for x in final_df.columns.tolist() if "_uplift" in x]
        logger.info(f"Found strategies: {strategy_list}")
        
        if strategy_list:
            plot_dict = {x: [v / 100 for v in final_df.loc[:, x].tolist()] for x in strategy_list}
            plot_output = os.path.join(self.output_dir, "ah_strategy.pdf")
            plot_figure(plot_dict, output_path=plot_output, xs=[str(x) for x in dts], ticks_gap=90)
            logger.info(f"Saved strategy plot to {plot_output}")
        
        return {
            "backtest_days": len(dts),
            "final_result_path": final_output_path,
            "intermediate_result_path": intermediate_output_path
        }


class AhBacktestOp(BaseOp):
    """单日回测（子Op）"""

    def execute(self):
        dt = self.context.dt
        feature_df: pd.DataFrame = self.context.feature_df
        max_samples = self.context.max_samples
        
        # 准备训练集和测试集
        train_dt_a_list: List[int] = [x for x in self.context.dt_a_list if x < dt][-max_samples:-1]
        train_df: pd.DataFrame = feature_df.loc[feature_df.dt.isin(train_dt_a_list)].copy()
        test_df: pd.DataFrame = feature_df.loc[feature_df.dt == dt].copy()
        
        if len(test_df) == 0:
            logger.warning(f"No test data for dt={dt}")
            return {"final": {}, "intermediate": []}
        
        # 定义特征列
        ah_ratio_key = "ah_ratio"
        label_key = "a_label"
        pred_key = "pred_y_nd"
        
        # 根据是否周频选择特征
        if "ah_amount5" in feature_df.columns:
            # 周频模式
            x_cols = [ah_ratio_key, "ah_amount5"]
        else:
            # 日频模式
            x_cols = [ah_ratio_key, "ah_amount"]
        
        # 添加历史涨跌幅特征
        for i in [20]:  # 可以根据需要调整
            x_cols.append(f"avg_{i}d_a_pct")
            x_cols.append(f"avg_{i}d_hk_pct")
        
        # 准备训练和测试数据
        train_x_nd: np.ndarray = train_df.loc[:, x_cols].values
        train_y_nd: np.ndarray = train_df.loc[:, label_key].values
        test_x_nd: np.ndarray = test_df.loc[:, x_cols].values
        test_y_nd: np.ndarray = test_df.loc[:, label_key].values
        rule_y_nd: np.ndarray = test_df.loc[:, ah_ratio_key].values
        
        # 训练模型
        model = Ridge(alpha=1.0)
        model.fit(train_x_nd, train_y_nd)
        
        # 预测
        pred_y_nd: np.ndarray = model.predict(test_x_nd)
        test_df.loc[:, pred_key] = pred_y_nd
        
        # 计算IC和RIC
        try:
            model_ic, _ = pearsonr(pred_y_nd, test_y_nd)
            model_ric, _ = spearmanr(pred_y_nd, test_y_nd)
            rule_ic, _ = pearsonr(rule_y_nd, test_y_nd)
            rule_ric, _ = spearmanr(rule_y_nd, test_y_nd)
        except Exception as e:
            logger.error(f"Failed to calculate IC for dt={dt}: {e}")
            model_ic = model_ric = rule_ic = rule_ric = 0.0
        
        # 生成选股池
        model_df = test_df.sort_values(by=pred_key, ascending=False)[:5]
        rule_df = test_df.sort_values(by=ah_ratio_key, ascending=False)[:5]
        
        # 最终结果
        final_result = {
            "dt": dt,
            "size": len(test_df),
            "model_ic": model_ic,
            "model_ric": model_ric,
            "rule_ic": rule_ic,
            "rule_ric": rule_ric,
            "rule_names": ",".join(rule_df.loc[:, "name"].tolist()),
            "rule_uplift": rule_df.loc[:, label_key].mean(),
            "model_names": ",".join(model_df.loc[:, "name"].tolist()),
            "model_uplift": model_df.loc[:, label_key].mean(),
            "all_uplift": test_y_nd.mean(),
        }
        
        # 计算分块收益
        block_size = 10
        block_cnt = max(1, round(len(test_df) / block_size))
        test_df_sorted = test_df.sort_values(by=pred_key, ascending=False)
        for i in range(block_size):
            block_data = test_df_sorted[i * block_cnt: (i + 1) * block_cnt]
            if len(block_data) > 0:
                final_result[f"p{i}_uplift"] = block_data.loc[:, label_key].mean()
            else:
                final_result[f"p{i}_uplift"] = 0.0
        
        # 中间结果（选股池详情）
        intermediate_result = []
        
        # 模型选股池
        for _, row in model_df.iterrows():
            intermediate_result.append({
                "dt": dt,
                "strategy": "model",
                "name": row["name"],
                "code": row["code"],
                "ah_ratio": row[ah_ratio_key],
                "pred_uplift": row[pred_key],
                "actual_uplift": row[label_key]
            })
        
        # 规则选股池
        for _, row in rule_df.iterrows():
            intermediate_result.append({
                "dt": dt,
                "strategy": "rule",
                "name": row["name"],
                "code": row["code"],
                "ah_ratio": row[ah_ratio_key],
                "pred_uplift": None,
                "actual_uplift": row[label_key]
            })
        
        return {
            "final": final_result,
            "intermediate": intermediate_result
        }

