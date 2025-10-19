from loguru import logger

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.exception("tiktoken not installed. OpenAI models will use character-based estimation.")

try:
    from modelscope import AutoTokenizer as ModelScopeTokenizer

    MODELSCOPE_AVAILABLE = True
except ImportError as e:
    MODELSCOPE_AVAILABLE = False
    logger.exception("modelscope not installed. Qwen models will use character-based estimation.")


class TokenCounter:

    def __init__(self, default_type: str = "qwen", default_model: str = None):
        self._tokenizer_cache = {}

        # Validate and set default type
        valid_types = ("auto", "openai", "qwen", "char")
        if default_type not in valid_types:
            raise ValueError(f"default_type must be one of {valid_types}, got: {default_type}")
        self.default_type = default_type

        # Set default model based on type
        if default_model is None:
            if default_type == "openai":
                self.default_model = "gpt-4o"  # o200k_base encoding
            elif default_type == "qwen":
                self.default_model = "Qwen/Qwen3-32B"
            else:
                self.default_model = "Qwen/Qwen3-32B"  # fallback default
        else:
            self.default_model = default_model

    def count(self, text: str, model_name: str = None) -> int:
        if not text:
            return 0

        # Use default model if not specified
        if model_name is None:
            model_name = self.default_model

        # Force specific tokenizer type if set
        if self.default_type == "openai":
            return self._count_with_tiktoken(text, model_name)
        elif self.default_type == "qwen":
            return self._count_with_qwen_tokenizer(text, model_name)
        elif self.default_type == "char":
            return self._estimate_from_chars(text)

        # Auto mode: detect from model name
        model_lower = model_name.lower()

        # Route 1: GPT models → tiktoken
        if model_lower.startswith("gpt"):
            return self._count_with_tiktoken(text, model_name)

        # Route 2: Qwen models → ModelScope
        # Detect by "qwen" prefix or "/" (ModelScope path format)
        if model_lower.startswith("qwen") or "/" in model_name:
            return self._count_with_qwen_tokenizer(text, model_name)

        # Route 3: Fallback → character estimation
        return self._estimate_from_chars(text)

    def _count_with_tiktoken(self, text: str, model_name: str) -> int:
        """Count tokens using tiktoken (for GPT models)."""
        if not TIKTOKEN_AVAILABLE:
            logger.debug(f"tiktoken not available, using fallback for {model_name}")
            return self._estimate_from_chars(text)

        try:
            # Get encoding for the model
            if model_name.startswith("gpt-4o"):
                encoding_name = "o200k_base"
            elif model_name.startswith("gpt-4") or model_name.startswith("gpt-3.5"):
                encoding_name = "cl100k_base"
            else:
                encoding_name = "cl100k_base"  # default

            # Cache encoding
            if encoding_name not in self._tokenizer_cache:
                self._tokenizer_cache[encoding_name] = tiktoken.get_encoding(encoding_name)

            encoding = self._tokenizer_cache[encoding_name]
            return len(encoding.encode(text))

        except Exception as e:
            logger.debug(f"tiktoken failed for {model_name}: {e}, using fallback")
            return self._estimate_from_chars(text)

    def _count_with_qwen_tokenizer(self, text: str, model_name: str) -> int:
        """
        Count tokens using ModelScope tokenizer (for Qwen models).
        
        Expects a direct ModelScope path: "qwen/Qwen2.5-72B-Instruct"
        """
        if not MODELSCOPE_AVAILABLE:
            logger.debug(f"modelscope not available, using fallback for {model_name}")
            return self._estimate_from_chars(text)

        try:
            # Use model_name directly as ModelScope path
            ms_model = model_name

            # Load and cache tokenizer
            if ms_model not in self._tokenizer_cache:
                logger.info(f"Loading Qwen tokenizer: {ms_model} (only ~2-5MB)")
                tokenizer = ModelScopeTokenizer.from_pretrained(ms_model, trust_remote_code=True)
                self._tokenizer_cache[ms_model] = tokenizer

            tokenizer = self._tokenizer_cache[ms_model]
            return len(tokenizer.encode(text))

        except Exception as e:
            logger.warning(
                f"Failed to load tokenizer for '{model_name}': {e}\n"
                f"Ensure the ModelScope path is correct.\n"
                f"Example: 'qwen/Qwen2.5-72B-Instruct' or 'qwen/Qwen-7B-Chat'\n"
                f"Falling back to character estimation."
            )
            return self._estimate_from_chars(text)

    @staticmethod
    def _estimate_from_chars(text: str) -> int:
        """
        Fallback: Estimate tokens from character count.
        Simple heuristic: tokens ≈ characters / 4
        """
        if not text:
            return 0

        # Slightly better heuristic for Chinese
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars

        # Chinese: ~2 chars/token, English: ~4 chars/token
        estimated = (chinese_chars // 2) + (other_chars // 4)
        return max(1, estimated)


if __name__ == "__main__":
    counter = TokenCounter()
    token_count = counter.count("我爱吃苹果")
    print(f"Token count for qwen: {token_count}")