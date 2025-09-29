import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Self, final

from click import Parameter

from nexus_client_sdk.nexus.algorithms import BaselineAlgorithm

@final
class ExecutionTreeSerializationTarget(Enum):
    PLAIN_TEXT = 'plain_text'
    MERMAID = 'mermaid'


@dataclass
class ExecutionTreeNode:
    children: set[Self]
    class_name: str

    def __eq__(self, other: Self) -> bool:
        return self.id == other.id

    def __hash__(self) -> int:
        return id(self)

    def add_child(self, child: Self) -> Self:
        self.children.add(child)
        return self

@final
@dataclass
class ExecutionTree:
    root_node: ExecutionTreeNode

    @classmethod
    def create(cls, root_node_name: str) -> Self:
        return cls(root_node=ExecutionTreeNode(children=set(), class_name=root_node_name))

    def add_child(self, node: ExecutionTreeNode):
        self.root_node.children.add(node)
        return self

    def serialize(self, target: ExecutionTreeSerializationTarget = ExecutionTreeSerializationTarget.PLAIN_TEXT) -> str:
        pass


def is_nexus_input_object_annotation(parameter: Parameter) -> bool:
    if type(parameter.annotation) == str:
        return False

    return "processor" in parameter.annotation.__name__.lower() or "reader" in parameter.annotation.__name__.lower()

def get_parameter_tree(parameter: inspect.Parameter) -> ExecutionTreeNode:
    sig = inspect.signature(parameter.annotation.__init__)
    dependents = list(filter(lambda meta: is_nexus_input_object_annotation(meta[1]), sig.parameters.items()))
    current_node = ExecutionTreeNode(children=set(), class_name=parameter.annotation.__name__)

    # leaf node
    if len(dependents) == 0:
        return current_node

    for _, dependent in dependents:
        current_node.add_child(get_parameter_tree(dependent))

    return current_node


def get_tree(algorithm_class: type[BaselineAlgorithm], tree_format: str = 'plain') -> ExecutionTree:
    """
     Generates a text representation of an execution tree for the provided algorithm class.
    :param algorithm_class: Nexus algorithm class to generate tree for
    :param tree_format: Output format. Supported formats: 'plain' (default), 'mermaid'
    :return:
    """
    root_node = inspect.signature(algorithm_class.__init__)
    tree = ExecutionTree.create(root_node_name=algorithm_class.__name__)
    processors = filter(lambda meta: "Processor" in meta[1].annotation.__name__ , root_node.parameters.items())
    for _, processor_parameter in processors:
        tree.add_child(get_parameter_tree(processor_parameter))

    return tree