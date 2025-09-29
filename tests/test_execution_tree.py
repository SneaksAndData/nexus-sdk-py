from nexus_client_sdk.nexus.execution.trees import get_tree
from tests.sample_algorithm.sample_main import TestAlgorithm


def test_tree_generation():
    tree = get_tree(TestAlgorithm)
    assert len(tree.root_node.children) == 2 and tree.root_node.class_name == TestAlgorithm.__name__


def test_tree_serialization():
    mermaid_tree = get_tree(TestAlgorithm).serialize()

    assert (
        mermaid_tree
        == """graph TB
TESTALGORITHM["TestAlgorithm"] --> XYPROCESSOR["XYProcessor"] --> XYREADER["XYReader"]
TESTALGORITHM["TestAlgorithm"] --> ZPROCESSOR["ZProcessor"] --> ZREADER["ZReader"]"""
    )
