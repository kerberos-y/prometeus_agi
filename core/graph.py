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
        for u, v, data in self.graph.edges(concept, data=True):
            results.append((u, data['relation'], v))
        for u, v, data in self.graph.in_edges(concept, data=True):
            results.append((u, data['relation'], v))
        
        # Возвращаем свойства узла
        properties = dict(self.graph.nodes[concept])
        return {"concept": concept, "relations": results, "properties": properties}

    def related(self, concept, depth=2):
        if concept not in self.graph:
            return []
        nodes = nx.ego_graph(self.graph, concept, radius=depth)
        return list(nodes.nodes())