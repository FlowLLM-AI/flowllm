from old.utils.registry import Registry

OP_REGISTRY = Registry()

from old.op.mock_op import Mock1Op, Mock2Op, Mock3Op, Mock4Op, Mock5Op, Mock6Op

from old.op.vector_store.update_vector_store_op import UpdateVectorStoreOp
from old.op.vector_store.recall_vector_store_op import RecallVectorStoreOp
from old.op.vector_store.vector_store_action_op import VectorStoreActionOp
from old.op.react.react_v1_op import ReactV1Op
