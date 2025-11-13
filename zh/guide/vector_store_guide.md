### Vector Store 使用指南

Vector Store 是用于存储、管理和检索向量嵌入的组件，支持工作空间管理、相似度搜索和元数据过滤等功能。

## 核心概念

**工作空间（Workspace）**：每个工作空间是一个独立的向量存储单元，用于组织和管理相关的向量节点。

**向量节点（VectorNode）**：包含文本内容、向量嵌入和元数据的数据单元，是存储和检索的基本单位。

**嵌入模型（Embedding Model）**：用于将文本转换为向量嵌入，支持自动生成节点向量和查询向量。

## 可用的实现类型

FlowLLM 提供了多种 Vector Store 实现，适用于不同的使用场景：

- **LocalVectorStore**：基于本地文件的实现，使用 JSONL 格式持久化存储，适合单机部署和小规模数据
- **MemoryVectorStore**：内存实现，数据存储在内存中，访问速度快，适合临时数据或测试场景
- **QdrantVectorStore**：基于 Qdrant 向量数据库，支持高性能向量搜索，适合大规模生产环境
- **ChromaVectorStore**：基于 ChromaDB 的实现，提供持久化存储和元数据过滤能力
- **EsVectorStore**：基于 Elasticsearch 的实现，支持强大的全文搜索和向量搜索组合

## 核心功能

### 工作空间管理

- **创建工作空间**：创建新的工作空间用于存储向量节点
- **删除工作空间**：删除工作空间及其所有数据
- **检查工作空间**：检查指定工作空间是否存在
- **列出工作空间**：获取所有已存在的工作空间列表
- **复制工作空间**：将一个工作空间的数据复制到另一个工作空间

### 节点操作

- **插入节点**：向工作空间插入向量节点，支持单个或批量插入，自动生成向量嵌入
- **删除节点**：根据节点 ID 删除指定节点
- **迭代节点**：遍历工作空间中的所有节点

### 向量搜索

- **相似度搜索**：基于文本查询进行向量相似度搜索，返回最相似的前 K 个结果
- **元数据过滤**：支持基于元数据的过滤条件，包括精确匹配和范围查询
- **相似度评分**：搜索结果包含相似度评分，用于评估匹配程度

### 数据导入导出

- **导出工作空间**：将工作空间数据导出到文件或指定路径
- **导入工作空间**：从文件或节点列表导入数据到工作空间
- **回调函数**：支持在导入导出过程中使用回调函数进行数据转换

## 同步与异步接口

所有 Vector Store 实现都提供同步和异步两套接口：

- **同步接口**：直接调用方法，适用于同步代码环境
- **异步接口**：以 `async_` 前缀命名，适用于异步代码环境，提供更好的并发性能

异步接口在以下场景中特别有用：
- 使用异步嵌入模型生成向量
- 在高并发环境中执行批量操作
- 与其他异步组件集成

## 配置选项

### 通用配置

- **embedding_model**：嵌入模型实例，用于生成向量嵌入
- **batch_size**：批量操作的大小，默认 1024

### LocalVectorStore 配置

- **store_dir**：存储目录路径，默认 `./local_vector_store`

### MemoryVectorStore 配置

- **store_dir**：持久化存储目录，默认 `./memory_vector_store`

### QdrantVectorStore 配置

- **url**：Qdrant 服务地址（可选，用于 Qdrant Cloud 或自定义部署）
- **host**：Qdrant 服务器主机，默认 `localhost`
- **port**：Qdrant 服务器端口，默认 `6333`
- **api_key**：API 密钥（用于 Qdrant Cloud 认证）
- **distance**：距离度量方式，支持 COSINE、EUCLIDEAN、DOT，默认 COSINE

### ChromaVectorStore 配置

- **store_dir**：ChromaDB 数据存储目录，默认 `./chroma_vector_store`

### EsVectorStore 配置

- **hosts**：Elasticsearch 主机地址，可以是字符串或列表，默认 `http://localhost:9200`
- **basic_auth**：基本认证凭据（用户名和密码）

## 元数据过滤

支持两种类型的元数据过滤：

- **精确匹配**：直接指定字段值进行精确匹配
- **范围查询**：使用 `gte`、`lte`、`gt`、`lt` 操作符进行数值范围查询
- **嵌套字段**：支持使用点号访问嵌套的元数据字段

## 使用场景建议

- **开发测试**：使用 MemoryVectorStore 或 LocalVectorStore，无需额外服务
- **小规模应用**：使用 LocalVectorStore 或 ChromaVectorStore，简单易用
- **生产环境**：使用 QdrantVectorStore 或 EsVectorStore，提供高性能和可扩展性
- **混合搜索**：使用 EsVectorStore，结合向量搜索和全文搜索能力

## 注意事项

- 确保嵌入模型的维度与 Vector Store 配置一致
- 大规模数据建议使用专业的向量数据库（Qdrant、Elasticsearch）
- 异步接口在异步环境中能提供更好的性能
- 定期备份重要数据，特别是使用内存存储时
- 根据数据规模选择合适的批量大小以优化性能

