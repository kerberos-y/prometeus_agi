import networkx as nx

class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_concept(self, name, properties={}):
        self.graph.add_node(name, **properties)

    def add_relation(self, from_node, to_node, relation, weight=1.0):
        self.graph.add_edge(from_node, to_node, relation=relation, weight=weight)

    def find(self, concept):
        if concept not in self.graph:
            return None

        results = []

        # Исходящие связи (что концепт делает/имеет)
        for u, v, data in self.graph.edges(concept, data=True):
            results.append((u, data['relation'], v))

        # Входящие связи (кто связан с концептом)
        for u, v, data in self.graph.in_edges(concept, data=True):
            results.append((u, data['relation'], v))

        return {"concept": concept, "relations": results} if results else None

    def related(self, concept, depth=2):
        if concept not in self.graph:
            return []
        nodes = nx.ego_graph(self.graph, concept, radius=depth)
        return list(nodes.nodes())