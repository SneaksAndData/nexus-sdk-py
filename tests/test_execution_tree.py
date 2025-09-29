from nexus_client_sdk.nexus.execution.trees import get_tree
from tests.sample_algorithm.sample_main import TestAlgorithm


def test_tree_generation():
    tree = get_tree(TestAlgorithm)
    assert len(tree.root_node.children) == 2 and tree.root_node.class_name == TestAlgorithm.__name__