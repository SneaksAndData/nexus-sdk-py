import inspect
from dataclasses import dataclass
from typing import Self, final
from nexus_client_sdk.nexus.algorithms import BaselineAlgorithm


@final
@dataclass
class ExecutionTreeNode:
    """
    Nexus execution tree node
    """

    children: dict[str, Self]
    class_name: str

    def _as_mermaid_node(self) -> str:
        return f'{self.class_name.upper()}["{self.class_name}"]'

    def serialize(self) -> str:
        """
          Serializes this node to a Mermaid Flowchart.
        :return:
        """
        result_lines = []
        for _, child in self.children.items():
            result_lines.append(f"{self._as_mermaid_node()} --> {child._as_mermaid_node()}")
            result_lines.append(child.serialize())

        if len(self.children) == 0:
            return self._as_mermaid_node()

        return "\n".join(set(result_lines))

    def add_child(self, child: Self) -> Self:
        """
         Adds a child node
        :param child:
        :return:
        """
        self.children |= {child.class_name.lower(): child}
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
        return cls(root_node=ExecutionTreeNode(children={}, class_name=root_node_name))

    def add_child(self, node: ExecutionTreeNode):
        """
         Adds a child node to the execution tree.
        :param node:
        :return:
        """
        self.root_node.add_child(node)
        return self

    def serialize(self, sort_nodes=False) -> str:
        """
         Serialize the execution tree to a string using the given target format.
        :return:
        """
        mermaid_nodes = filter(lambda ser_node: " --> " in ser_node, set(self.root_node.serialize().split("\n")))
        if sort_nodes:
            mermaid_nodes = sorted(mermaid_nodes)
        return "\n".join(["graph TB", "\n".join(mermaid_nodes)])


def _is_nexus_input_object_annotation(parameter: inspect.Parameter) -> bool:
    if isinstance(parameter.annotation, str):
        return False

    return "processor" in parameter.annotation.__name__.lower() or "reader" in parameter.annotation.__name__.lower()


def _get_parameter_tree(parameter: inspect.Parameter, node_cache: dict[str, ExecutionTreeNode]) -> ExecutionTreeNode:
    sig = inspect.signature(parameter.annotation.__init__)
    dependents = list(filter(lambda meta: _is_nexus_input_object_annotation(meta[1]), sig.parameters.items()))
    cached_node = node_cache.get(parameter.annotation.__name__, None)
    current_node = cached_node or ExecutionTreeNode(children={}, class_name=parameter.annotation.__name__)
    if cached_node is None:
        node_cache[parameter.annotation.__name__] = current_node

    # leaf node
    if len(dependents) == 0:
        return current_node

    for _, dependent in dependents:
        current_node.add_child(_get_parameter_tree(dependent, node_cache))

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
    node_cache: dict[str, ExecutionTreeNode] = {}
    for _, processor_parameter in processors:
        tree.add_child(_get_parameter_tree(processor_parameter, node_cache))

    return tree
