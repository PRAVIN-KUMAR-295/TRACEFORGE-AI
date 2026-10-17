import pytest
from backend.app.database.falkordb_client import FalkorMemoryGraphEngine, FalkorDBClient, falkor_client
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


def test_falkordb_connection_status_and_clear_error_reporting():
    """Verify FalkorDB client accurately reports offline/in-memory status with connection error details."""
    client = FalkorDBClient(host="127.0.0.1", port=59999)
    assert client.is_connected is False
    assert client.engine_type == "FalkorDB (In-Memory Cypher Engine)"
    # Connection error should clearly explain failure cause
    assert client.connection_error is not None
    assert any(err in client.connection_error.lower() for err in ("refused", "connection", "error", "installed", "target machine"))


def test_idempotent_graph_seeding_prevents_duplicate_nodes_and_edges():
    """Verify repeated graph seeding is idempotent and never creates duplicate nodes or edges."""
    res1 = seed_graph_database(falkor_client)
    node_count_1 = len(falkor_client.memory_engine.nodes)
    edge_count_1 = len(falkor_client.memory_engine.edges)

    assert node_count_1 == 29
    assert edge_count_1 == 32

    # Run seeding second and third time
    res2 = seed_graph_database(falkor_client)
    res3 = seed_graph_database(falkor_client)

    node_count_3 = len(falkor_client.memory_engine.nodes)
    edge_count_3 = len(falkor_client.memory_engine.edges)

    assert node_count_3 == node_count_1
    assert edge_count_3 == edge_count_1


def test_reconnect_method_attempts_connection():
    """Verify reconnect method returns boolean and updates connection state cleanly."""
    status = falkor_client.reconnect()
    assert isinstance(status, bool)
    assert falkor_client.engine_type in ("FalkorDB (Live Cluster)", "FalkorDB (In-Memory Cypher Engine)")


def test_live_seeding_merge_queries_structure():
    """Verify live FalkorDB seeder uses valid OpenCypher MERGE queries."""
    from unittest.mock import MagicMock
    from backend.app.database.seed_data import seed_live_falkordb

    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_live_graph = MagicMock()
    mock_client.live_graph = mock_live_graph

    res = seed_live_falkordb(mock_client)
    assert res["live_connected"] is True
    assert res["nodes_merged"] == 29
    assert res["edges_merged"] == 32

    # Check queries used MERGE
    calls = mock_live_graph.query.call_args_list
    assert len(calls) == 61  # 29 nodes + 32 edges
    for c in calls:
        query_str = c[0][0]
        assert "MERGE" in query_str


def test_read_only_query_classification():
    """Verify _is_read_only_query accurately identifies read vs write Cypher queries."""
    from backend.app.database.falkordb_client import FalkorDBClient

    # Valid read queries
    assert FalkorDBClient._is_read_only_query("MATCH (n:Service) RETURN n") is True
    assert FalkorDBClient._is_read_only_query("MATCH (s:Service)-[r:DEPENDS_ON]->(d) WHERE s.name = 'Auth' RETURN s, r, d") is True
    assert FalkorDBClient._is_read_only_query("RETURN 1 AS ping") is True

    # Mutating queries
    assert FalkorDBClient._is_read_only_query("CREATE (n:Service {name: 'Test'})") is False
    assert FalkorDBClient._is_read_only_query("MATCH (n:Service) SET n.status = 'down'") is False
    assert FalkorDBClient._is_read_only_query("MATCH (n:Service) DELETE n") is False
    assert FalkorDBClient._is_read_only_query("MERGE (n:Service {name: 'Test'})") is False
    assert FalkorDBClient._is_read_only_query("MATCH (n:Service) REMOVE n.prop") is False
    assert FalkorDBClient._is_read_only_query("DROP INDEX ON :Service(name)") is False

    # Conservative classification for CALL and FOREACH
    assert FalkorDBClient._is_read_only_query("CALL db.labels()") is False
    assert FalkorDBClient._is_read_only_query("MATCH (n) CALL { WITH n DETACH DELETE n }") is False
    assert FalkorDBClient._is_read_only_query("FOREACH (x in [1, 2, 3] | CREATE (:Item {val: x}))") is False

    # Comments containing write keywords must NOT cause false-positive write classification
    assert FalkorDBClient._is_read_only_query("// Please do not DELETE or CREATE anything\nMATCH (n) RETURN n") is True
    assert FalkorDBClient._is_read_only_query("/* Block comment mentioning SET and MERGE */\nMATCH (n) RETURN n") is True

    # String literals containing write keywords must NOT cause false-positive write classification
    assert FalkorDBClient._is_read_only_query("MATCH (s:Service {status: 'DELETE_PENDING'}) RETURN s") is True
    assert FalkorDBClient._is_read_only_query('MATCH (s:Service) WHERE s.action = "CREATE_USER" RETURN s') is True

    # Combined query with keyword in literal AND actual mutation keyword
    assert FalkorDBClient._is_read_only_query("MATCH (s:Service {status: 'DELETE'}) CREATE (s)-[:REL]->(x)") is False


def test_falkordb_client_constructor_args():
    """Verify FalkorDBClient correctly accepts and forwards username and ssl arguments."""
    from unittest.mock import MagicMock, patch
    from backend.app.database.falkordb_client import FalkorDBClient

    with patch("backend.app.database.falkordb_client.LiveFalkorDB") as MockLiveFalkorDB:
        mock_inst = MagicMock()
        mock_inst.connection.ping.return_value = True
        MockLiveFalkorDB.return_value = mock_inst

        client = FalkorDBClient(
            host="custom-cloud-host.falkordb.cloud",
            port=63640,
            username="traceforge_app",
            password="mock_password",
            ssl=False,
            graph_name="traceforge_incidents",
            timeout=10,
        )

        assert client.host == "custom-cloud-host.falkordb.cloud"
        assert client.port == 63640
        assert client.username == "traceforge_app"
        assert client.password == "mock_password"
        assert client.ssl is False
        assert client.graph_name == "traceforge_incidents"
        assert client.timeout == 10

        MockLiveFalkorDB.assert_called_once_with(
            host="custom-cloud-host.falkordb.cloud",
            port=63640,
            username="traceforge_app",
            password="mock_password",
            ssl=False,
        )


def test_empty_graph_protocol_ping_initialization():
    """Verify FalkorDBClient uses client.connection.ping() without querying the graph."""
    from unittest.mock import MagicMock, patch
    from backend.app.database.falkordb_client import FalkorDBClient

    # Successful ping
    with patch("backend.app.database.falkordb_client.LiveFalkorDB") as MockLiveFalkorDB:
        mock_inst = MagicMock()
        mock_inst.connection.ping.return_value = True
        mock_graph = MagicMock()
        mock_inst.select_graph.return_value = mock_graph
        MockLiveFalkorDB.return_value = mock_inst

        client = FalkorDBClient(host="localhost", port=6379)
        assert client.is_connected is True
        assert client.engine_type == "FalkorDB (Live Cluster)"
        assert client.connection_error is None
        mock_inst.connection.ping.assert_called_once()
        # Verify no graph query was executed during healthcheck
        assert mock_graph.query.call_count == 0
        assert mock_graph.ro_query.call_count == 0

    # Failed ping (e.g. auth or network failure)
    with patch("backend.app.database.falkordb_client.LiveFalkorDB") as MockLiveFalkorDB:
        mock_inst = MagicMock()
        mock_inst.connection.ping.side_effect = ConnectionRefusedError("Connection refused")
        MockLiveFalkorDB.return_value = mock_inst

        client = FalkorDBClient(host="localhost", port=6379)
        assert client.is_connected is False
        assert client.live_client is None
        assert client.live_graph is None
        assert client.engine_type == "FalkorDB (In-Memory Cypher Engine)"
        assert "ConnectionRefusedError" in client.connection_error


def test_execute_cypher_ro_routing_and_live_error_surfacing():
    """Verify ro_query() routing and explicit error surfacing when live cluster fails."""
    from unittest.mock import MagicMock
    from backend.app.database.falkordb_client import FalkorDBClient

    client = FalkorDBClient(host="localhost", port=6379)
    # Manually configure live connected state with mock graph
    client.is_connected = True
    client.live_client = MagicMock()
    mock_live_graph = MagicMock()
    client.live_graph = mock_live_graph

    # 1. Read-only query should route to ro_query
    mock_live_graph.ro_query.return_value = MagicMock(header=[["n"]], result_set=[])
    res_ro = client.execute_cypher("MATCH (n:Service) RETURN n")
    mock_live_graph.ro_query.assert_called_once()
    assert res_ro["error"] is None
    assert res_ro["engine"] == "FalkorDB (Live Cluster)"

    # 2. Mutating query should route to query (not ro_query)
    mock_live_graph.query.return_value = MagicMock(header=[["n"]], result_set=[])
    res_write = client.execute_cypher("CREATE (n:Service {name: 'Test'})")
    mock_live_graph.query.assert_called_once()
    assert res_write["error"] is None

    # 3. Live query error must surface explicitly, not silently fall back to in-memory data
    mock_live_graph.ro_query.side_effect = Exception("NOPERM this user has no permissions to run GRAPH.QUERY")
    res_err = client.execute_cypher("MATCH (s:Service) RETURN s")
    assert res_err["error"] == "NOPERM this user has no permissions to run GRAPH.QUERY"
    assert res_err["engine"] == "FalkorDB (Live Cluster)"
    assert res_err["row_count"] == 0
    assert res_err["rows"] == []

    # 4. Offline mode gracefully falls back to in-memory engine without error
    client.is_connected = False
    client.live_graph = None
    res_offline = client.execute_cypher("MATCH (s:Service) RETURN s")
    assert res_offline["error"] is None
    assert res_offline["engine"] == "FalkorDB (In-Memory Cypher Engine)"


def test_read_only_live_mode_skips_seeding():
    """Verify live seeding is skipped and executes zero writes when client is configured for read-only access."""
    from unittest.mock import MagicMock
    from backend.app.database.seed_data import seed_graph_database, seed_live_falkordb
    from backend.app.database.falkordb_client import FalkorMemoryGraphEngine

    # Mock client connected in read-only mode
    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.read_only = True
    mock_live_graph = MagicMock()
    mock_client.live_graph = mock_live_graph

    # Test seed_live_falkordb directly
    res_live = seed_live_falkordb(mock_client)
    assert res_live["skipped"] is True
    assert res_live["reason"] == "client_read_only"
    assert res_live["nodes_merged"] == 0
    assert res_live["edges_merged"] == 0
    # Ensure NO query was executed on the live graph
    assert mock_live_graph.query.call_count == 0

    # Test seed_graph_database master procedure
    mock_client.memory_engine = FalkorMemoryGraphEngine(name="test_graph")
    res_master = seed_graph_database(mock_client)
    assert res_master["live_status"]["skipped"] is True
    assert res_master["live_status"]["reason"] == "client_read_only"
    # Verify in-memory graph is still initialized for deterministic fallback
    assert res_master["in_memory_nodes"] == 29
    assert res_master["in_memory_edges"] == 32
    assert mock_live_graph.query.call_count == 0


def test_demo_mode_initializes_in_memory_graph_without_live_writes():
    """Verify demo mode initializes in-memory graph and does not attempt live writes."""
    from backend.app.database.seed_data import seed_graph_database
    from backend.app.database.falkordb_client import FalkorDBClient

    client = FalkorDBClient(host="127.0.0.1", port=59999)
    assert client.is_connected is False

    res = seed_graph_database(client)
    assert res["in_memory_nodes"] == 29
    assert res["in_memory_edges"] == 32
    assert res["live_status"] == {"live_connected": False}
    assert len(client.memory_engine.nodes) == 29
    assert len(client.memory_engine.edges) == 32


def test_falkordb_client_read_only_detection():
    """Verify FalkorDBClient auto-detects read-only user and accepts explicit read_only flag."""
    from backend.app.database.falkordb_client import FalkorDBClient

    # Default client with demo settings
    c_default = FalkorDBClient(host="localhost", port=6379)
    assert c_default.read_only is False

    # Dedicated app user is recognized as read-only
    c_app = FalkorDBClient(host="localhost", port=6379, username="traceforge_app")
    assert c_app.read_only is True
    assert c_app.is_read_only is True

    # Explicit read_only=True flag
    c_explicit_ro = FalkorDBClient(host="localhost", port=6379, read_only=True)
    assert c_explicit_ro.read_only is True

    # Explicit read_only=False overrides username if needed
    c_explicit_rw = FalkorDBClient(host="localhost", port=6379, username="traceforge_app", read_only=False)
    assert c_explicit_rw.read_only is False


def test_admin_seeder_validation_and_existing_graph_guard():
    """Verify admin seeder pre-flight validation and strict existing-graph guard."""
    from scripts.seed_cloud_admin import validate_seed_data, check_existing_graph
    from backend.app.database.seed_data import SEED_NODES, SEED_EDGES

    # 1. Valid seed data
    valid, msg = validate_seed_data(SEED_NODES, SEED_EDGES)
    assert valid is True
    assert "integrity verified" in msg.lower()

    # 2. Defective seed data detection
    valid_bad, msg_bad = validate_seed_data(SEED_NODES[:-1], SEED_EDGES)
    assert valid_bad is False
    assert "mismatch" in msg_bad.lower()

    # 3. Clean cluster (target graph does not exist) -> proceeds
    can_proceed, msg = check_existing_graph([], "traceforge_incidents", allow_existing=False)
    assert can_proceed is True
    assert "pristine" in msg.lower()

    # 4. Target graph already exists, allow_existing=False -> aborts by default
    can_proceed, msg = check_existing_graph(["traceforge_incidents"], "traceforge_incidents", allow_existing=False)
    assert can_proceed is False
    assert "aborted" in msg.lower()

    # 5. Target graph exists, explicit override allow_existing=True -> proceeds
    can_proceed, msg = check_existing_graph(["traceforge_incidents"], "traceforge_incidents", allow_existing=True)
    assert can_proceed is True
    assert "override is enabled" in msg.lower()


def test_admin_seeder_node_and_edge_mutation_verification():
    """Verify that node and edge seeding requires confirmed return values and endpoint resolution."""
    from unittest.mock import MagicMock
    from scripts.seed_cloud_admin import seed_nodes, seed_edges, verify_cloud_graph

    mock_graph = MagicMock()

    # 1. Successful node merge with returned node ID
    mock_graph.query.return_value = MagicMock(result_set=[["auth-service"]])
    confirmed, errors = seed_nodes(mock_graph, [{"id": "auth-service", "label": "Service"}])
    assert confirmed == 1
    assert len(errors) == 0

    # 2. Failed node merge (result_set empty)
    mock_graph.query.return_value = MagicMock(result_set=[])
    confirmed, errors = seed_nodes(mock_graph, [{"id": "auth-service", "label": "Service"}])
    assert confirmed == 0
    assert len(errors) == 1
    assert "did not return confirmed node ID" in errors[0]

    # 3. Successful edge merge with confirmed resolved endpoints
    mock_graph.query.return_value = MagicMock(result_set=[["checkout-service", "auth-service"]])
    edge = {"source": "checkout-service", "target": "auth-service", "type": "DEPENDS_ON", "properties": {}}
    confirmed, errors = seed_edges(mock_graph, [edge])
    assert confirmed == 1
    assert len(errors) == 0

    # 4. Edge merge where MATCH matched 0 endpoints (missing node in graph)
    mock_graph.query.return_value = MagicMock(result_set=[])
    confirmed, errors = seed_edges(mock_graph, [edge])
    # Must NOT count as a successful edge
    assert confirmed == 0
    assert len(errors) == 1
    assert "Endpoint resolution failed" in errors[0]

    # 5. verify_cloud_graph checks expected counts
    mock_graph.query.side_effect = [
        MagicMock(result_set=[[29]]),  # node count query
        MagicMock(result_set=[[32]]),  # edge count query
    ]
    is_verified, actual_n, actual_e, errs = verify_cloud_graph(mock_graph, expected_nodes=29, expected_edges=32)
    assert is_verified is True
    assert actual_n == 29
    assert actual_e == 32
    assert len(errs) == 0

    # 6. verify_cloud_graph flags discrepancy
    mock_graph.query.side_effect = [
        MagicMock(result_set=[[20]]),  # incomplete node count
        MagicMock(result_set=[[32]]),  # edge count
    ]
    is_verified, actual_n, actual_e, errs = verify_cloud_graph(mock_graph, expected_nodes=29, expected_edges=32)
    assert is_verified is False
    assert actual_n == 20
    assert any("mismatch" in e.lower() for e in errs)


def test_admin_seeder_help_flag_clean_exit():
    """Verify --help flag exits immediately with 0 before backend imports or connection attempts."""
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "scripts/seed_cloud_admin.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "usage: seed_cloud_admin.py" in res.stdout
    # Proves backend singleton / connection was NOT imported or initiated
    assert "FalkorDB live connection unavailable" not in res.stdout
    assert "FalkorDB live connection unavailable" not in res.stderr
    assert "Enter password" not in res.stdout


def test_admin_seeder_main_flow_failure_exit_codes():
    """Verify main() returns exit code 1 on existing graph, missing endpoints, or count mismatches."""
    from unittest.mock import MagicMock, patch
    from scripts.seed_cloud_admin import main

    # Case A: Target graph exists without override -> returns 1
    with patch("sys.argv", ["seed_cloud_admin.py"]):
        with patch("getpass.getpass", return_value="mock_password"):
            with patch("falkordb.FalkorDB") as MockFalkorDB:
                mock_client = MagicMock()
                MockFalkorDB.return_value = mock_client
                mock_client.connection.execute_command.return_value = [b"traceforge_incidents"]

                exit_code = main()
                assert exit_code == 1

    # Case B: Edge endpoints fail to match -> returns 1
    with patch("sys.argv", ["seed_cloud_admin.py"]):
        with patch("getpass.getpass", return_value="mock_password"):
            with patch("falkordb.FalkorDB") as MockFalkorDB:
                with patch("builtins.input", return_value="yes"):
                    mock_client = MagicMock()
                    MockFalkorDB.return_value = mock_client
                    # Clean cluster
                    mock_client.connection.execute_command.return_value = []
                    mock_graph = MagicMock()
                    mock_client.select_graph.return_value = mock_graph

                    # Nodes succeed, but edge query returns empty result set (endpoint missing)
                    mock_graph.query.side_effect = (
                        [MagicMock(result_set=[["mock-node"]])] * 29  # 29 nodes
                        + [MagicMock(result_set=[])] * 32             # 32 edges fail to resolve
                        + [MagicMock(result_set=[[29]])]              # count nodes
                        + [MagicMock(result_set=[[0]])]               # count edges
                    )

                    exit_code = main()
                    assert exit_code == 1


def test_live_get_topology_and_subgraph():
    """Verify get_topology and get_node_subgraph query live_graph via Cypher when connected."""
    from unittest.mock import MagicMock
    from backend.app.database.falkordb_client import FalkorDBClient

    client = FalkorDBClient(host="localhost", port=6379)
    client.is_connected = True
    client.live_client = MagicMock()
    mock_live_graph = MagicMock()
    client.live_graph = mock_live_graph

    # Mock node object
    mock_node = MagicMock()
    mock_node.properties = {"id": "service-auth", "name": "Auth Service", "status": "critical"}
    mock_node.labels = ["Service"]

    mock_live_graph.ro_query.side_effect = [
        # Call 1: MATCH (n) RETURN n
        MagicMock(result_set=[[mock_node]]),
        # Call 2: MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id, properties(r)
        MagicMock(result_set=[["service-auth", "DEPENDS_ON", "redis-auth", {"weight": 1.0}]]),
    ]

    topo = client.get_topology()
    assert topo["total_nodes"] == 1
    assert topo["nodes"][0]["id"] == "service-auth"
    assert topo["nodes"][0]["label"] == "Service"
    assert topo["total_edges"] == 1
    assert topo["edges"][0]["source"] == "service-auth"
    assert topo["edges"][0]["type"] == "DEPENDS_ON"
    assert topo["edges"][0]["target"] == "redis-auth"

    # Test live subgraph
    mock_rel = MagicMock()
    mock_rel.properties = {"source": "service-auth", "target": "redis-auth", "weight": 1.0}
    mock_rel.relation = "DEPENDS_ON"
    mock_target_node = MagicMock()
    mock_target_node.properties = {"id": "redis-auth", "name": "Redis"}
    mock_target_node.labels = ["Database"]

    mock_live_graph.ro_query.side_effect = [
        MagicMock(result_set=[[mock_node, [mock_rel], mock_target_node]])
    ]

    sub = client.get_node_subgraph("service-auth", depth=1)
    assert sub["root_node_id"] == "service-auth"
    assert len(sub["nodes"]) == 2
    assert len(sub["edges"]) == 1
