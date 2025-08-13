import json
from pathlib import Path

import akshare as ak
import pandas as pd

from flowllm.enumeration.role import Role
from flowllm.llm import OpenAICompatibleBaseLLM
from flowllm.op.akshare.akshare_utlis import get_stock_zh_a_spot_em
from flowllm.op.akshare.fetch_url import fetch_webpage_text
from flowllm.op.base_op import BaseOp
from flowllm.schema.message import Message


class AkshareDataOp(BaseOp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cache_path: Path = Path(__file__).parent / "akshare_cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # model_name = "qwen3-235b-a22b-thinking-2507"
        # model_name = "qwen3-235b-a22b-instruct-2507"
        model_name = "qwen3-30b-a3b-thinking-2507"
        self.llm_client = OpenAICompatibleBaseLLM(model_name=model_name)

    def get_all_df(self):
        file_path = self.cache_path / "akshare_stock_zh_a_spot_em.csv"
        if not file_path.exists():
            df = get_stock_zh_a_spot_em()
            df.to_csv(self.cache_path / "akshare_stock_zh_a_spot_em.csv", index=False)

        df = pd.read_csv(file_path, dtype={'代码': str})
        if "序号" in df.columns:
            df = df.drop(columns=["序号"])
        print("download df complete.")
        return df

    def parse_query(self, query: str):
        all_df: pd.DataFrame = self.get_all_df()
        print(all_df)
        all_df.loc[:, "name"] = all_df.loc[:, "名称"].apply(lambda x: x.replace(" ", ""))

        result = []
        for line in all_df.to_dict(orient="records"):
            result.append(f"股票名称: {line['name']} 对应的股票代码: {line['代码']}")

        code_str = "\n".join(result)

        prompt = f"""
        # 股票和代码的映射表格
        {code_str}
        
        # 用户问题
        {query}
        
        # 请你提取出用户问题中在**映射表格**中存在的股票名称，并根据映射表格找到对应的股票代码，并返回一个json格式的字符串，格式如下：
        
        ```json
        {{
            "股票名称1": "股票代码1",
            "股票名称2": "股票代码2",
            ...
        }}
        ```
        不要去猜用户问题对应的股票，如果用户问题没有明确提及股票名称，直接返回空字典 
        ```json
        {{
        }}
        ```
        """

        def callback_handler(msg: Message):
            print(f"content={msg.content}")
            content = msg.content
            if "```" in content:
                content = content.split("```")[1]
                content = content.strip("json")
            content = json.loads(content.strip())
            return content

        llm_result: dict = self.llm_client.chat([Message(role=Role.USER, content=prompt)],
                                                callback_fn=callback_handler)
        print(json.dumps(llm_result, indent=2, ensure_ascii=False))

        # final_result = {}
        # for key in llm_result:
        #     key = key.replace(" ", "")
        #     code = all_df.loc[all_df["name"] == key, "代码"].values[0]
        #     final_result[key] = str(code)
        # print(json.dumps(final_result, indent=2, ensure_ascii=False))

        return llm_result

    def get_code_infos(self, code: str):
        if code.startswith("6"):
            symbol = f"SH{code}"
        elif code.startswith("0"):
            symbol = f"SZ{code}"
        elif code.startswith("3"):
            symbol = f"SZ{code}"
        elif code.startswith("8"):
            symbol = f"BJ{code}"
        else:
            print("不支持的股票代码")
            return {}

        stock_individual_basic_info_xq_df = ak.stock_individual_basic_info_xq(symbol=symbol)
        result = {}
        for line in stock_individual_basic_info_xq_df.to_dict(orient="records"):
            result[line["item"]] = line["value"]
        # print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    def get_code_current_info(self, code: str):
        file_path = self.cache_path / "current_info.csv"
        if not file_path.exists():
            stock_sh_a_spot_em_df = ak.stock_sh_a_spot_em()
            stock_sz_a_spot_em_df = ak.stock_sz_a_spot_em()
            stock_bj_a_spot_em_df = ak.stock_bj_a_spot_em()

            df = pd.concat([stock_sh_a_spot_em_df, stock_sz_a_spot_em_df, stock_bj_a_spot_em_df], axis=0)

            df.to_csv(file_path, index=False)

        df = pd.read_csv(file_path, dtype={"代码": str})
        result: pd.DataFrame = df.loc[df["代码"] == code, :]
        # print(result)
        if len(result) > 0:
            for line in result.to_dict(orient="records"):
                return line

        return {}

    def get_code_flow(self, code: str):
        stock_individual_fund_flow_df = ak.stock_individual_fund_flow(stock=code, market="sh")
        # print(stock_individual_fund_flow_df)
        line = {}
        for line in stock_individual_fund_flow_df.to_dict(orient="records"):
            ...
        return line

    def get_code_basic_financial(self, code: str):
        stock_financial_abstract_ths_df = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        line = {}
        for line in stock_financial_abstract_ths_df.to_dict(orient="records"):
            ...
        return line

    def get_code_news(self, code: str):
        stock_news_em_df = ak.stock_news_em(symbol=code)
        url_dict = {}
        for i, line in enumerate(stock_news_em_df.to_dict(orient="records")[:3]):
            url = line["新闻链接"]
            # http://finance.eastmoney.com/a/202508133482756869.html
            ts = url.split("/")[-1].split(".")[0]
            date = ts[:8]
            content = fetch_webpage_text(url)
            url_dict[f"新闻{i}，时间{date}"] = content
        print(json.dumps(url_dict, indent=2, ensure_ascii=False))
        return url_dict

    def execute(self):
        # self.parse_query(query="茅台和五粮液怎么看？")
        # print("=" * 10)
        # self.parse_query(query="有什么白酒的股票？")

        # self.get_code_infos("SZ000001")
        # self.get_code_current_info("000001")
        # self.get_code_flow("000001")
        # self.get_code_basic_financial("000001")
        self.get_code_news("000001")


if __name__ == "__main__":
    from flowllm.utils.common_utils import load_env

    load_env()
    op = AkshareDataOp()
    op()
