import inspect
from dataclasses import dataclass
from typing import Self, final

from nexus_client_sdk.nexus.algorithms import BaselineAlgorithm


@dataclass
class ExecutionTreeNode:
    """
    Nexus execution tree node
    """

    children: set[Self]
    class_name: str

    def __eq__(self, other: Self) -> bool:
        return self.__hash__() == other.__hash__()

    def __hash__(self) -> int:
        return id(self)

    def serialize(self) -> str:
        """
          Serializes this node to a Mermaid Flowchart.
        :return:
        """
        result_lines = []
        root = f'{self.class_name.upper()}["{self.class_name}"]'
        for child in self.children:
            result_lines.append(f"{root} --> {child.serialize()}")

        if len(self.children) == 0:
            result_lines.append(root)

        return "\n".join(result_lines)

    def add_child(self, child: Self) -> Self:
        """
         Adds a child node
        :param child:
        :return:
        """
        self.children.add(child)
        return self


@final
@dataclass
class ExecutionTree:
    """
    Nexus Algorithm execution tree
    """

    root_node: ExecutionTreeNode

    @classmethod
    def create(cls, root_node_name: str) -> Self:
        """
         Creates a new execution tree node
        :param root_node_name: Name for the node.
        :return:
        """
        return cls(root_node=ExecutionTreeNode(children=set(), class_name=root_node_name))

    def add_child(self, node: ExecutionTreeNode):
        """
         Adds a child node to the execution tree.
        :param node:
        :return:
        """
        self.root_node.children.add(node)
        return self

    def serialize(self) -> str:
        """
         Serialize the execution tree to a string using the given target format.
        :return:
        """
        return "\n".join(["graph TB", self.root_node.serialize()])


def _is_nexus_input_object_annotation(parameter: inspect.Parameter) -> bool:
    if isinstance(parameter.annotation, str):
        return False

    return "processor" in parameter.annotation.__name__.lower() or "reader" in parameter.annotation.__name__.lower()


def _get_parameter_tree(parameter: inspect.Parameter) -> ExecutionTreeNode:
    sig = inspect.signature(parameter.annotation.__init__)
    dependents = list(filter(lambda meta: _is_nexus_input_object_annotation(meta[1]), sig.parameters.items()))
    current_node = ExecutionTreeNode(children=set(), class_name=parameter.annotation.__name__)

    # leaf node
    if len(dependents) == 0:
        return current_node

    for _, dependent in dependents:
        current_node.add_child(_get_parameter_tree(dependent))

    return current_node


def get_tree(algorithm_class: type[BaselineAlgorithm]) -> ExecutionTree:
    """
     Generates a text representation of an execution tree for the provided algorithm class.
    :param algorithm_class: Nexus algorithm class to generate tree for
    :return:
    """
    root_node = inspect.signature(algorithm_class.__init__)
    tree = ExecutionTree.create(root_node_name=algorithm_class.__name__)
    processors = filter(lambda meta: "Processor" in meta[1].annotation.__name__, root_node.parameters.items())
    for _, processor_parameter in processors:
        tree.add_child(_get_parameter_tree(processor_parameter))

    return tree
