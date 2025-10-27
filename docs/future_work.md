# 20251024 todo
1. optimize docs
   1. optimize README.md
      1. 基础能力：实现LLM+EMB+vectorstore驱动的工作流服务，不同http/stream_http/mcp/cmd模式
         1. install，然后以MCP为例
         2. 实现底层op 同步或者异步，注意输入，注意op之间交互，注意输出
         3. 定义参数：
            1. http/mcp/cmd
            2. LLM+EMB+vectorstore参数
            3. 定义flow，定义desc和input 、 等价代码定义
         4. flowllm启动，curl命令测试/python/node.js/python import
         5. http的不同
         6. stream_http的不同
         7. cmd的不同
      2. blog
         1. reading paper
         2. learning
      3. application
         1. reme_ai
         2. llm+search ui+demo
         3. deepresearch 
         4. 金融供给
         5. 金融因子图
         6. 金融deepresearch ?
         7. desktop pet
2. optimize code
   1. fastmcp提供更加高级的支持
   2. 