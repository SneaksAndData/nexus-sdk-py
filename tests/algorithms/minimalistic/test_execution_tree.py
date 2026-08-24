from nexus_client_sdk.nexus.execution.trees import get_tree
from tests.algorithms.minimalistic.sample_main_minimalistic import TestMinimalisticAlgorithm


def test_tree_generation():
    tree = get_tree(TestMinimalisticAlgorithm)
    assert len(tree.root_node.children) == 3 and tree.root_node.class_name == TestMinimalisticAlgorithm.__name__


def test_tree_serialization():
    mermaid_tree = get_tree(TestMinimalisticAlgorithm).serialize(sort_nodes=True)

    assert (
        mermaid_tree
        == """graph TB
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> XYPROCESSOR["XYProcessor"]
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> ZPROCESSOR["ZProcessor"]
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> ZZPROCESSOR["ZZProcessor"]
XYPROCESSOR["XYProcessor"] --> XYSAMPLEREADER["XYSampleReader"]
ZPROCESSOR["ZProcessor"] --> ZSAMPLEREADER["ZSampleReader"]
ZZPROCESSOR["ZZProcessor"] --> ZPROCESSOR["ZProcessor"]"""
    )
