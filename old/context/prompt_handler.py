from pathlib import Path

import yaml
from loguru import logger

from flowllm.context.base_context import BaseContext
from flowllm.context.service_context import C


class PromptHandler(BaseContext):

    def __init__(self, language: str = "", **kwargs):
        super().__init__(**kwargs)
        self.language: str = language or C.language

    def load_prompt_by_file(self, prompt_file_path: Path | str = None):
        if prompt_file_path is None:
            return self

        if isinstance(prompt_file_path, str):
            prompt_file_path = Path(prompt_file_path)

        if not prompt_file_path.exists():
            return self

        with prompt_file_path.open() as f:
            prompt_dict = yaml.load(f, yaml.FullLoader)
            self.load_prompt_dict(prompt_dict)
        return self

    def load_prompt_dict(self, prompt_dict: dict = None):
        if not prompt_dict:
            return self

        for key, value in prompt_dict.items():
            if isinstance(value, str):
                if key in self._data:
                    self._data[key] = value
                    logger.warning(f"prompt_dict key={key} overwrite!")

                else:
                    self._data[key] = value
                    logger.debug(f"add prompt_dict key={key}")
        return self

    def get_prompt(self, prompt_name: str):
        key: str = prompt_name
        if self.language and not key.endswith(self.language.strip()):
            key += "_" + self.language.strip()

        assert key in self._data, f"prompt_name={key} not found."
        return self._data[key]

    def prompt_format(self, prompt_name: str, **kwargs) -> str:
        prompt = self.get_prompt(prompt_name)

        flag_kwargs = {k: v for k, v in kwargs.items() if isinstance(v, bool)}
        other_kwargs = {k: v for k, v in kwargs.items() if not isinstance(v, bool)}

        if flag_kwargs:
            split_prompt = []
            for line in prompt.strip().split("\n"):
                hit = False
                hit_flag = True
                for key, flag in kwargs.items():
                    if not line.startswith(f"[{key}]"):
                        continue

                    else:
                        hit = True
                        hit_flag = flag
                        line = line.strip(f"[{key}]")
                        break

                if not hit:
                    split_prompt.append(line)
                elif hit_flag:
                    split_prompt.append(line)

            prompt = "\n".join(split_prompt)

        if other_kwargs:
            prompt = prompt.format(**other_kwargs)

        return prompt
