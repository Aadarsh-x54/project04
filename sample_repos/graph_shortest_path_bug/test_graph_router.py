from graph_router import GraphRouter


def test_graph_edge_insertion():
    g = GraphRouter()
    g.add_edge("A", "B", 4.0)
    assert "A" in g.adj
    assert "B" in g.adj

