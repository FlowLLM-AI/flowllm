import json
from typing import List

from loguru import logger

from flowllm.op import OP_REGISTRY
from flowllm.op.base_op import BaseOp
from flowllm.schema.experience import BaseExperience
from flowllm.schema.request import BaseRequest
from flowllm.schema.vector_node import VectorNode


@OP_REGISTRY.register()
class UpdateVectorStoreOp(BaseOp):

    def execute(self):
        request: BaseRequest = self.context.request

        experience_ids: List[str] | None = self.context.response.deleted_experience_ids
        if experience_ids:
            self.vector_store.delete(node_ids=experience_ids, workspace_id=request.workspace_id)
            logger.info(f"delete experience_ids={json.dumps(experience_ids, indent=2)}")

        insert_experience_list: List[BaseExperience] | None = self.context.response.experience_list
        if insert_experience_list:
            insert_nodes: List[VectorNode] = [x.to_vector_node() for x in insert_experience_list]
            self.vector_store.insert(nodes=insert_nodes, workspace_id=request.workspace_id)
            logger.info(f"insert insert_node.size={len(insert_nodes)}")
