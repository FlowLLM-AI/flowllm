"""
AH股数据下载Op
负责从Tushare下载原始数据：
1. A股日频数据
2. HK股日频数据
3. AH对比数据
4. 汇率数据（USDCNH, USDHKD）
"""
from typing import Dict
import os
import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.op import BaseOp
from flowllm.utils.tushare_client import TushareClient


@C.register_op(register_app="FlowLLM")
class AhDownloadOp(BaseOp):
    """下载AH股原始数据"""

    def __init__(self,
                 output_dir: str = "data/origin",
                 **kwargs):
        super().__init__(**kwargs)
        self.output_dir = output_dir
        self.ts_client = TushareClient()

    def _ensure_output_dir(self):
        """确保输出目录存在"""
        os.makedirs(self.output_dir, exist_ok=True)

    def _download_ah_comparison(self) -> pd.DataFrame:
        """下载AH对比数据"""
        logger.info("Downloading AH comparison data...")
        df = self.ts_client.request(api_name="stk_ah_comparison")
        
        # 获取最新的AH对比关系
        ah_df = df.loc[df.trade_date == df.trade_date.max(), ["hk_code", "ts_code", "name"]]
        
        # 保存原始数据
        output_path = os.path.join(self.output_dir, "stk_ah_comparison.csv")
        df.to_csv(output_path, index=False)
        logger.info(f"Saved AH comparison data to {output_path}, pairs={len(ah_df)}")
        
        return ah_df

    def _download_forex_data(self) -> Dict[str, pd.DataFrame]:
        """下载汇率数据"""
        logger.info("Downloading forex data...")
        forex_dict = {}
        
        for code in ['USDCNH.FXCM', 'USDHKD.FXCM']:
            df = self.ts_client.request(api_name="fx_daily", ts_code=code)
            output_path = os.path.join(self.output_dir, f"fx_daily_{code}.csv")
            df.to_csv(output_path, index=False)
            logger.info(f"Saved forex data to {output_path}, rows={len(df)}")
            forex_dict[code] = df
        
        return forex_dict

    def _download_stock_data(self, ah_df: pd.DataFrame) -> Dict[str, Dict[str, pd.DataFrame]]:
        """下载A股和HK股日频数据"""
        logger.info("Downloading stock daily data...")
        stock_dict = {}
        
        for line in tqdm(ah_df.to_dict(orient="records"), desc="Downloading stocks"):
            hk_code = line["hk_code"]
            ts_code = line["ts_code"]
            name = line["name"]
            
            try:
                # 下载A股数据
                a_stock_df = self.ts_client.request(api_name="daily", ts_code=ts_code)
                a_output_path = os.path.join(self.output_dir, f"daily_{ts_code}.csv")
                a_stock_df.to_csv(a_output_path, index=False)
                
                # 下载HK股数据
                hk_stock_df = self.ts_client.request(api_name="hk_daily", ts_code=hk_code)
                hk_output_path = os.path.join(self.output_dir, f"hk_daily_{hk_code}.csv")
                hk_stock_df.to_csv(hk_output_path, index=False)
                
                stock_dict[name] = {
                    "a_code": ts_code,
                    "hk_code": hk_code,
                    "a_df": a_stock_df,
                    "hk_df": hk_stock_df
                }
                
            except Exception as e:
                logger.error(f"Failed to download {name} ({ts_code}/{hk_code}): {e}")
                continue
        
        logger.info(f"Downloaded {len(stock_dict)} stock pairs")
        return stock_dict

    def execute(self):
        """执行下载"""
        self._ensure_output_dir()
        
        # 1. 下载AH对比数据
        ah_df = self._download_ah_comparison()
        
        # 2. 下载汇率数据
        forex_dict = self._download_forex_data()
        
        # 3. 下载股票数据
        stock_dict = self._download_stock_data(ah_df)
        
        result = {
            "ah_pairs": len(ah_df),
            "forex_count": len(forex_dict),
            "stock_pairs": len(stock_dict),
            "output_dir": self.output_dir
        }
        
        logger.info(f"Download completed: {result}")
        return result

