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
MINIMALISTICXYPROCESSOR["MinimalisticXYProcessor"] --> MINIMALISTICXYSAMPLEREADER["MinimalisticXYSampleReader"]
MINIMALISTICZPROCESSOR["MinimalisticZProcessor"] --> MINIMALISTICZSAMPLEREADER["MinimalisticZSampleReader"]
MINIMALISTICZZPROCESSOR["MinimalisticZZProcessor"] --> MINIMALISTICZPROCESSOR["MinimalisticZProcessor"]
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> MINIMALISTICXYPROCESSOR["MinimalisticXYProcessor"]
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> MINIMALISTICZPROCESSOR["MinimalisticZProcessor"]
TESTMINIMALISTICALGORITHM["TestMinimalisticAlgorithm"] --> MINIMALISTICZZPROCESSOR["MinimalisticZZProcessor"]"""
    )
