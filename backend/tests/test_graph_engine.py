import pytest
from backend.app.database.falkordb_client import FalkorMemoryGraphEngine, falkor_client
from backend.app.database.seed_data import seed_graph_database


def test_memory_graph_engine_basic_crud():
    engine = FalkorMemoryGraphEngine(name="test_graph")
    n1 = engine.add_node("svc1", "Service", {"name": "Auth", "tier": "core"})
    n2 = engine.add_node("db1", "Database", {"name": "Redis", "type": "cache"})
    e1 = engine.add_edge("svc1", "db1", "CONNECTS_TO", {"pool": 50})

    assert len(engine.nodes) == 2
    assert len(engine.edges) == 1
    assert n1.id == "svc1"
    assert e1.type == "CONNECTS_TO"


def test_cypher_match_node():
    engine = FalkorMemoryGraphEngine(name="test_graph")
    engine.add_node("auth", "Service", {"name": "Auth Service", "status": "critical"})
    engine.add_node("pay", "Service", {"name": "Pay Service", "status": "healthy"})

    cols, rows = engine.query("MATCH (s:Service) WHERE s.status = 'critical' RETURN s")
    assert len(rows) == 1
    assert rows[0][0]["id"] == "auth"


def test_cypher_match_relationship():
    engine = FalkorMemoryGraphEngine(name="test_graph")
    engine.add_node("checkout", "Service", {"name": "Checkout"})
    engine.add_node("auth", "Service", {"name": "Auth"})
    engine.add_edge("checkout", "auth", "DEPENDS_ON", {"type": "gRPC"})

    cols, rows = engine.query("MATCH (s:Service)-[r:DEPENDS_ON]->(d:Service) RETURN s, r, d")
    assert len(rows) == 1
    assert rows[0][0]["id"] == "checkout"
    assert rows[0][1]["type"] == "DEPENDS_ON"
    assert rows[0][2]["id"] == "auth"


def test_falkordb_client_execute_cypher():
    seed_graph_database(falkor_client)
    res = falkor_client.execute_cypher("MATCH (s:Service) RETURN s")
    assert res["row_count"] >= 5
    assert "columns" in res
    assert res["execution_time_ms"] >= 0.0


def test_subgraph_neighborhood():
    seed_graph_database(falkor_client)
    subgraph = falkor_client.get_node_subgraph("checkout-service", depth=1)
    assert subgraph["root_node_id"] == "checkout-service"
    assert len(subgraph["nodes"]) > 1
    assert len(subgraph["edges"]) > 0
