import json
import time

import akshare as ak
import pandas as pd
from loguru import logger
from tqdm import tqdm

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_op import BaseOp
from flowllm.utils.fetch_url import fetch_webpage_text


@C.register_op()
class GetAkAInfoOp(BaseOp):

    def execute_code(self, code: str) -> dict:
        df = ak.stock_individual_info_em(symbol=code)
        result = {}
        for line in df.to_dict(orient="records"):
            result[line["item"].strip()] = line["value"]
        return {"基本信息": result}

    def execute(self):
        max_retries: int = self.op_params.get("max_retries", 3)
        for code, info_dict in self.context.code_infos.items():
            result = {}
            for i in range(max_retries):
                try:
                    result = self.execute_code(code)
                    break

                except Exception as _:
                    if i != max_retries - 1:
                        time.sleep(i * 2 + 1)

            if result:
                info_dict.update(result)

        time.sleep(1)
        logger.info(f"code_infos={json.dumps(self.context.code_infos, ensure_ascii=False, indent=2)}")


@C.register_op()
class GetAkASpotOp(GetAkAInfoOp):

    def execute_code(self, code: str) -> dict:
        from flowllm.op.akshare import GetAkACodeOp

        df: pd.DataFrame = GetAkACodeOp.download_a_stock_df()
        df = df.loc[df["代码"] == code, :]
        result = {}
        if len(df) > 0:
            result["实时行情"] = df.to_dict(orient="records")[-1]

        return result


@C.register_op()
class GetAkAMoneyFlowOp(GetAkAInfoOp):

    def execute_code(self, code: str) -> dict:
        df = ak.stock_individual_fund_flow(stock=code)
        result = {}
        if len(df) > 0:
            result["资金流入流出"] = {k: str(v) for k, v in df.to_dict(orient="records")[-1].items()}
        return result


@C.register_op()
class GetAkAFinancialInfoOp(GetAkAInfoOp):

    def execute_code(self, code: str) -> dict:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        result = {}
        if len(df) > 0:
            result["财务信息"] = {k: str(v) for k, v in df.to_dict(orient="records")[-1].items()}
        return result


@C.register_op()
class GetAkANewsOp(GetAkAInfoOp):

    def execute_code(self, code: str) -> dict:
        stock_news_em_df = ak.stock_news_em(symbol=code)
        top_n_news: int = self.op_params.get("top_n_news", 1)

        news_content_list = []
        for i, line in enumerate(tqdm(stock_news_em_df.to_dict(orient="records")[:top_n_news])):
            url = line["新闻链接"]
            # http://finance.eastmoney.com/a/202508133482756869.html
            ts = url.split("/")[-1].split(".")[0]
            date = ts[:8]
            content = fetch_webpage_text(url).strip()
            content = f"新闻{i}\n时间{date}\n{content}"
            news_content_list.append(content)

        return {"新闻": "\n\n".join(news_content_list)}


@C.register_op()
class MergeAkAInfoOp(BaseOp):

    def execute(self):
        code_content = {}
        for code, info_dict in self.context.code_infos.items():
            content_list = [f"\n\n### {code}"]
            for key, value in info_dict.items():
                content_list.append(f"\n#### {code}-{key}")
                if isinstance(value, str):
                    content_list.append(value)
                elif isinstance(value, dict):
                    for attr_name, attr_value in value.items():
                        content_list.append(f"{attr_name}: {attr_value}")
                elif isinstance(value, list):
                    content_list.extend([x.strip() for x in value if x])

            code_content[code] = "\n".join(content_list)

        answer = "\n".join(code_content.values())
        logger.info(f"answer=\n{answer}")
        self.context.response.answer = answer.strip()


if __name__ == "__main__":
    C.set_service_config().init_by_service_config()

    code_infos = {"000858": {}, "600519": {}}
    context = FlowContext(code_infos=code_infos, query="茅台和五粮现在价格多少？")

    op1 = GetAkAInfoOp()
    op2 = GetAkASpotOp()
    op3 = GetAkAMoneyFlowOp()
    op4 = GetAkAFinancialInfoOp()
    op5 = GetAkANewsOp()
    op6 = MergeAkAInfoOp()

    op = op1 >> op2 >> op3 >> op4 >> op5 >> op6
    op(context=context)
