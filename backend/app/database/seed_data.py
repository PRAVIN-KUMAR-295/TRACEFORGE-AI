import logging
from typing import List, Dict, Any
from backend.app.database.falkordb_client import FalkorDBClient, falkor_client

logger = logging.getLogger("traceforge.seed")


def seed_graph_database(client: FalkorDBClient):
    """
    Seeds the FalkorDB graph with a realistic microservices enterprise topology,
    dependencies, error patterns, deployments, metrics, and historical incidents for memory recall.
    """
    g = client.memory_engine

    # Clear existing state
    g.nodes.clear()
    g.edges.clear()
    g._edge_counter = 1

# 1. SERVICES
SERVICES = [
    {"id": "api-gateway", "label": "Service", "name": "API Gateway", "tier": "edge", "language": "Go", "status": "degraded", "owner": "traffic-eng"},
    {"id": "checkout-service", "label": "Service", "name": "Checkout Service", "tier": "business", "language": "TypeScript", "status": "critical", "owner": "checkout-team"},
    {"id": "auth-service", "label": "Service", "name": "Authentication Service", "tier": "core", "language": "Python", "status": "critical", "owner": "security-team"},
    {"id": "payment-service", "label": "Service", "name": "Payment Service", "tier": "business", "language": "Java", "status": "degraded", "owner": "payments-team"},
    {"id": "order-service", "label": "Service", "name": "Order Management Service", "tier": "business", "language": "Go", "status": "healthy", "owner": "order-team"},
    {"id": "inventory-service", "label": "Service", "name": "Inventory Service", "tier": "business", "language": "Rust", "status": "healthy", "owner": "logistics-team"},
    {"id": "notification-service", "label": "Service", "name": "Notification Dispatcher", "tier": "async", "language": "Python", "status": "healthy", "owner": "comms-team"},
    {"id": "search-service", "label": "Service", "name": "Catalog Search Service", "tier": "read-heavy", "language": "Python", "status": "healthy", "owner": "search-eng"}
]

# 2. DATABASES & QUEUES
INFRASTRUCTURE = [
    {"id": "redis-auth-cache", "label": "Database", "name": "Redis Auth Session Cluster", "type": "redis", "version": "7.2.4", "status": "exhausted"},
    {"id": "postgres-order-db", "label": "Database", "name": "Postgres Orders Primary", "type": "postgres", "version": "16.1", "status": "healthy"},
    {"id": "postgres-payment-db", "label": "Database", "name": "Payment PCI Vault DB", "type": "postgres", "version": "15.4", "status": "healthy"},
    {"id": "kafka-cluster", "label": "Queue", "name": "Core Kafka Event Bus", "type": "kafka", "version": "3.6.0", "status": "healthy"},
    {"id": "elasticsearch-cluster", "label": "Database", "name": "Elasticsearch Search Index", "type": "elasticsearch", "version": "8.11.0", "status": "healthy"}
]

# 3. DEPLOYMENTS
DEPLOYMENTS = [
    {"id": "deploy-auth-v2.4.1", "label": "Deployment", "version": "v2.4.1", "service": "auth-service", "deployed_at": "28 mins ago", "commit": "8f3a19b", "deployed_by": "ci/cd", "change_summary": "Reduced Redis idle connection timeout & pool max size to 50"},
    {"id": "deploy-checkout-v1.8.0", "label": "Deployment", "version": "v1.8.0", "service": "checkout-service", "deployed_at": "3 hours ago", "commit": "c479e2a", "deployed_by": "ci/cd", "change_summary": "Added idempotent checkout retry token"},
    {"id": "deploy-search-v3.0.2", "label": "Deployment", "version": "v3.0.2", "service": "search-service", "deployed_at": "1 day ago", "commit": "e81d77f", "deployed_by": "ci/cd", "change_summary": "Optimized vector search indexing"}
]

# 4. ERROR PATTERNS
ERRORS = [
    {"id": "err-redis-timeout", "label": "ErrorPattern", "pattern": "ConnectionPoolExhaustedError: Timeout waiting for free Redis connection (5000ms)", "severity": "CRITICAL", "frequency": 420},
    {"id": "err-auth-503", "label": "ErrorPattern", "pattern": "HTTP 503 Service Unavailable: upstream auth-service non-responsive", "severity": "CRITICAL", "frequency": 1280},
    {"id": "err-circuit-breaker", "label": "ErrorPattern", "pattern": "CircuitBreakerOpenException: Checkout->Auth circuit opened (error_rate=64%)", "severity": "HIGH", "frequency": 850},
    {"id": "err-payment-token-invalid", "label": "ErrorPattern", "pattern": "AuthTokenValidationFailed: Unable to verify caller identity", "severity": "HIGH", "frequency": 310}
]

# 5. METRIC ANOMALIES
METRICS = [
    {"id": "metric-conn-pool-leak", "label": "MetricAnomaly", "name": "Auth Redis Pool Saturation", "metric": "redis_pool_active_connections", "value": "50/50 (100%)", "threshold": "80%", "anomaly_score": 0.98},
    {"id": "metric-checkout-5xx-surge", "label": "MetricAnomaly", "name": "Checkout 5xx Error Surge", "metric": "http_requests_5xx_rate", "value": "48.2%", "threshold": "1.0%", "anomaly_score": 0.95},
    {"id": "metric-gateway-latency", "label": "MetricAnomaly", "name": "API Gateway p99 Latency Surge", "metric": "http_p99_latency_ms", "value": "4850ms", "threshold": "250ms", "anomaly_score": 0.91}
]

# 6. HISTORICAL INCIDENTS (PERSISTENT INCIDENT MEMORY)
HISTORICAL_INCIDENTS = [
    {
        "id": "INC-2026-0814",
        "label": "Incident",
        "title": "Auth Token Cache Starvation Cascade",
        "severity": "CRITICAL",
        "status": "RESOLVED",
        "resolved_at": "2026-08-14T14:32:00Z",
        "affected_service": "auth-service",
        "root_cause_summary": "Misconfigured Redis connection pool max_size caused thread pool starvation under surge traffic. Downstream services cascadingly failed auth checks.",
        "resolution_strategy": "Increased Redis max_connections pool size from 50 to 2000, added connection pool timeout buffer, and flushed stale connection locks.",
        "transferrable_fix": "Rollback deployment deploy-auth-v2.4.1 or apply hotfix configuration to increase connection pool limit to 2000.",
        "impacted_services": ["auth-service", "checkout-service", "payment-service", "api-gateway"]
    },
    {
        "id": "INC-2026-0702",
        "label": "Incident",
        "title": "Order Processing Deadlock During Flash Sale",
        "severity": "HIGH",
        "status": "RESOLVED",
        "resolved_at": "2026-07-02T19:15:00Z",
        "affected_service": "order-service",
        "root_cause_summary": "Postgres row lock contention between inventory reservation and order commit during concurrent transactions.",
        "resolution_strategy": "Switched to optimistic concurrency control with exponential backoff retry and Redis distributed lock.",
        "transferrable_fix": "Enable optimistic locking on inventory stock ledger.",
        "impacted_services": ["order-service", "inventory-service"]
    },
    {
        "id": "INC-2026-0519",
        "label": "Incident",
        "title": "Search Latency Outage & Elasticsearch Node Drop",
        "severity": "MEDIUM",
        "status": "RESOLVED",
        "resolved_at": "2026-05-19T11:40:00Z",
        "affected_service": "search-service",
        "root_cause_summary": "Unbalanced Elasticsearch shard recovery choked node I/O during heavy search queries.",
        "resolution_strategy": "Throttled max concurrent shard migrations and rebalanced memory heap limits.",
        "transferrable_fix": "Tune indices.recovery.max_bytes_per_sec to 100mb.",
        "impacted_services": ["search-service"]
    }
]

# 7. ACTIVE LIVE INCIDENT (Primary subject of investigation)
ACTIVE_INCIDENT = {
    "id": "INC-2026-1042",
    "label": "Incident",
    "title": "Payment & Checkout Cascade Outage (HTTP 503 Spike)",
    "severity": "CRITICAL",
    "status": "ACTIVE",
    "affected_service": "checkout-service",
    "created_at": "2026-10-14T16:15:00Z",
    "description": "Checkout failure rate spiked to 48.2% across mobile and web clients. Customers report unable to complete purchase; API Gateway returns 503 Service Unavailable on POST /v1/checkout.",
    "symptoms": ["Checkout 5xx error rate 48.2%", "API Gateway p99 latency 4850ms", "Payment service reporting invalid/empty tokens"],
    "error_logs": [
        "2026-10-14T16:18:12Z [api-gateway] [ERROR] Upstream failure /checkout/pay returned 503 Service Unavailable",
        "2026-10-14T16:18:15Z [checkout-service] [CRITICAL] CircuitBreakerOpenException: Checkout->Auth circuit opened (error_rate=64%)",
        "2026-10-14T16:18:18Z [checkout-service] [ERROR] Auth token validation failed for user_session_4920: Connection timeout",
        "2026-10-14T16:18:22Z [auth-service] [CRITICAL] ConnectionPoolExhaustedError: Timeout waiting for free Redis connection (5000ms)",
        "2026-10-14T16:18:25Z [auth-service] [WARN] Active connection pool 50/50 saturated; 412 caller threads queued"
    ],
    "impacted_services": ["checkout-service", "api-gateway", "payment-service", "auth-service"]
}

# 8. RESOLUTION NODES
RESOLUTIONS = [
    {
        "id": "res-conn-pool-tune",
        "label": "Resolution",
        "title": "Hotfix Redis Connection Pool Tuning",
        "action": "CONFIG_UPDATE",
        "config_diff": "pool_max_size: 50 -> 2000, pool_timeout_ms: 1000 -> 8000",
        "risk": "LOW"
    },
    {
        "id": "res-rollback-auth",
        "label": "Resolution",
        "title": "Rollback Auth Service to v2.4.0",
        "action": "ROLLBACK",
        "target": "deploy-auth-v2.4.1",
        "risk": "MEDIUM"
    }
]

# Combined Seed Nodes Collection
SEED_NODES = (
    SERVICES
    + INFRASTRUCTURE
    + DEPLOYMENTS
    + ERRORS
    + METRICS
    + HISTORICAL_INCIDENTS
    + [ACTIVE_INCIDENT]
    + RESOLUTIONS
)

# 9. GRAPH RELATIONSHIPS (EDGES)
SEED_EDGES = [
    # Service dependencies
    {"source": "api-gateway", "target": "checkout-service", "type": "DEPENDS_ON", "properties": {"type": "REST", "critical": True, "timeout_ms": 3000}},
    {"source": "api-gateway", "target": "search-service", "type": "DEPENDS_ON", "properties": {"type": "REST", "critical": False, "timeout_ms": 1500}},
    {"source": "checkout-service", "target": "auth-service", "type": "DEPENDS_ON", "properties": {"type": "gRPC", "critical": True, "timeout_ms": 1000}},
    {"source": "checkout-service", "target": "payment-service", "type": "DEPENDS_ON", "properties": {"type": "REST", "critical": True, "timeout_ms": 4000}},
    {"source": "checkout-service", "target": "inventory-service", "type": "DEPENDS_ON", "properties": {"type": "gRPC", "critical": True, "timeout_ms": 2000}},
    {"source": "checkout-service", "target": "order-service", "type": "DEPENDS_ON", "properties": {"type": "REST", "critical": True, "timeout_ms": 3000}},
    {"source": "order-service", "target": "notification-service", "type": "DEPENDS_ON", "properties": {"type": "Async", "critical": False, "timeout_ms": 5000}},
    {"source": "payment-service", "target": "auth-service", "type": "DEPENDS_ON", "properties": {"type": "gRPC", "critical": True, "timeout_ms": 1000}},

    # Infrastructure connections
    {"source": "auth-service", "target": "redis-auth-cache", "type": "CONNECTS_TO", "properties": {"protocol": "RESP", "pool_size": 50, "max_conns": 50}},
    {"source": "order-service", "target": "postgres-order-db", "type": "CONNECTS_TO", "properties": {"protocol": "TCP", "pool_size": 100}},
    {"source": "payment-service", "target": "postgres-payment-db", "type": "CONNECTS_TO", "properties": {"protocol": "TCP", "pool_size": 80}},
    {"source": "order-service", "target": "kafka-cluster", "type": "CONNECTS_TO", "properties": {"topic": "orders.v1"}},
    {"source": "notification-service", "target": "kafka-cluster", "type": "CONNECTS_TO", "properties": {"topic": "orders.v1"}},
    {"source": "search-service", "target": "elasticsearch-cluster", "type": "CONNECTS_TO", "properties": {"port": 9200}},

    # Deployment edges
    {"source": "deploy-auth-v2.4.1", "target": "auth-service", "type": "DEPLOYED_TO", "properties": {"timestamp": "2026-10-14T15:47:00Z"}},
    {"source": "deploy-checkout-v1.8.0", "target": "checkout-service", "type": "DEPLOYED_TO", "properties": {"timestamp": "2026-10-14T13:15:00Z"}},

    # Error and Anomaly associations
    {"source": "deploy-auth-v2.4.1", "target": "err-redis-timeout", "type": "CAUSED_BY", "properties": {"evidence": "Pool limit decreased in commit 8f3a19b"}},
    {"source": "err-redis-timeout", "target": "metric-conn-pool-leak", "type": "PROPAGATES_TO", "properties": {"weight": 0.98}},
    {"source": "metric-conn-pool-leak", "target": "auth-service", "type": "AFFECTS", "properties": {"metric_severity": "CRITICAL"}},
    {"source": "err-redis-timeout", "target": "err-auth-503", "type": "TRIGGERED_BY", "properties": {"weight": 0.94}},
    {"source": "err-auth-503", "target": "err-circuit-breaker", "type": "PROPAGATES_TO", "properties": {"service": "checkout-service"}},
    {"source": "err-circuit-breaker", "target": "metric-checkout-5xx-surge", "type": "PROPAGATES_TO", "properties": {"weight": 0.95}},
    {"source": "metric-checkout-5xx-surge", "target": "checkout-service", "type": "AFFECTS", "properties": {"metric_severity": "CRITICAL"}},
    {"source": "metric-checkout-5xx-surge", "target": "api-gateway", "type": "AFFECTS", "properties": {"metric_severity": "HIGH"}},

    # Active Incident relationship linkages
    {"source": "INC-2026-1042", "target": "checkout-service", "type": "AFFECTS", "properties": {"impact_level": "PRIMARY"}},
    {"source": "INC-2026-1042", "target": "err-circuit-breaker", "type": "TRIGGERED_BY", "properties": {"observed_at": "16:18:15Z"}},
    {"source": "INC-2026-1042", "target": "err-redis-timeout", "type": "TRIGGERED_BY", "properties": {"observed_at": "16:18:22Z"}},
    {"source": "INC-2026-1042", "target": "deploy-auth-v2.4.1", "type": "CAUSED_BY", "properties": {"confidence": 0.94}},

    # Historical Incident memory linkages
    {"source": "INC-2026-0814", "target": "auth-service", "type": "AFFECTS", "properties": {"impact_level": "PRIMARY"}},
    {"source": "INC-2026-0814", "target": "redis-auth-cache", "type": "AFFECTS", "properties": {"component": "pool"}},
    {"source": "INC-2026-0814", "target": "res-conn-pool-tune", "type": "RESOLVED_BY", "properties": {"duration_mins": 14}},
    {"source": "INC-2026-1042", "target": "INC-2026-0814", "type": "SIMILAR_TO", "properties": {"similarity": 0.94, "pattern": "Redis connection pool exhaustion in auth-service"}},
]


def seed_in_memory_graph(client: FalkorDBClient):
    """Populates the in-memory graph engine for fast fallback and testing."""
    g = client.memory_engine
    g.nodes.clear()
    g.edges.clear()
    g._edge_counter = 1

    for node in SEED_NODES:
        g.add_node(node["id"], node["label"], node)

    for edge in SEED_EDGES:
        g.add_edge(edge["source"], edge["target"], edge["type"], edge.get("properties", {}))

    logger.info(f"Seeded in-memory graph: {len(g.nodes)} nodes, {len(g.edges)} edges.")


def seed_live_falkordb(client: FalkorDBClient) -> Dict[str, Any]:
    """
    Safely and idempotently initializes the live FalkorDB instance using OpenCypher MERGE.
    Guarantees no duplicate nodes or relationships on repeated startup.
    Skips seeding when client is configured for read-only access.
    """
    if not client.is_connected or not client.live_graph:
        return {"live_connected": False, "nodes_merged": 0, "edges_merged": 0}

    if getattr(client, "read_only", False) is True or getattr(client, "is_read_only", False) is True:
        logger.info("Skipping live FalkorDB seeding: client is configured for read-only access.")
        return {
            "live_connected": True,
            "skipped": True,
            "reason": "client_read_only",
            "nodes_merged": 0,
            "edges_merged": 0,
        }

    nodes_merged = 0
    edges_merged = 0

    try:
        # 1. Idempotently MERGE all nodes
        for node in SEED_NODES:
            nid = node["id"]
            lbl = node["label"]
            props = {k: v for k, v in node.items() if k not in ("label",)}
            q = f"MERGE (n:{lbl} {{id: $id}}) SET n += $props"
            client.live_graph.query(q, {"id": nid, "props": props})
            nodes_merged += 1

        # 2. Idempotently MERGE all relationships
        for edge in SEED_EDGES:
            src = edge["source"]
            tgt = edge["target"]
            rtype = edge["type"]
            props = edge.get("properties", {})
            q = (
                f"MATCH (a {{id: $src}}), (b {{id: $tgt}}) "
                f"MERGE (a)-[r:{rtype}]->(b) "
                f"SET r += $props"
            )
            client.live_graph.query(q, {"src": src, "tgt": tgt, "props": props})
            edges_merged += 1

        logger.info(f"Seeded live FalkorDB graph: {nodes_merged} nodes, {edges_merged} relationships merged.")
        return {"live_connected": True, "nodes_merged": nodes_merged, "edges_merged": edges_merged}
    except Exception as e:
        logger.error(f"Failed to seed live FalkorDB: {e}")
        return {"live_connected": True, "error": str(e), "nodes_merged": nodes_merged, "edges_merged": edges_merged}


def seed_graph_database(client: FalkorDBClient) -> Dict[str, Any]:
    """
    Master graph seeding procedure.
    Always initializes in-memory fallback, and idempotently syncs to live FalkorDB if connected and not read-only.
    """
    seed_in_memory_graph(client)
    live_status = {"live_connected": False}
    if client.is_connected:
        if getattr(client, "read_only", False) is True or getattr(client, "is_read_only", False) is True:
            logger.info("Skipping live FalkorDB seeding: client is configured for read-only access.")
            live_status = {
                "live_connected": True,
                "skipped": True,
                "reason": "client_read_only",
                "nodes_merged": 0,
                "edges_merged": 0,
            }
        else:
            live_status = seed_live_falkordb(client)
    return {
        "in_memory_nodes": len(client.memory_engine.nodes),
        "in_memory_edges": len(client.memory_engine.edges),
        "live_status": live_status
    }


# Auto seed on module load
seed_graph_database(falkor_client)
