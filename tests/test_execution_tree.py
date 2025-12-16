from nexus_client_sdk.nexus.execution.trees import get_tree
from tests.sample_algorithm.sample_main import TestAlgorithm


def test_tree_generation():
    tree = get_tree(TestAlgorithm)
    assert len(tree.root_node.children) == 3 and tree.root_node.class_name == TestAlgorithm.__name__


def test_tree_serialization():
    mermaid_tree = get_tree(TestAlgorithm).serialize(sort_nodes=True)

    assert (
        mermaid_tree
        == """graph TB
TESTALGORITHM["TestAlgorithm"] --> XYPROCESSOR["XYProcessor"]
TESTALGORITHM["TestAlgorithm"] --> ZPROCESSOR["ZProcessor"]
TESTALGORITHM["TestAlgorithm"] --> ZZPROCESSOR["ZZProcessor"]
XYPROCESSOR["XYProcessor"] --> XYSAMPLEREADER["XYSampleReader"]
ZPROCESSOR["ZProcessor"] --> ZSAMPLEREADER["ZSampleReader"]
ZZPROCESSOR["ZZProcessor"] --> ZPROCESSOR["ZProcessor"]"""
    )
