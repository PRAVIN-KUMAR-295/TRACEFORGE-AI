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
    services = [
        {"id": "api-gateway", "label": "Service", "name": "API Gateway", "tier": "edge", "language": "Go", "status": "degraded", "owner": "traffic-eng"},
        {"id": "checkout-service", "label": "Service", "name": "Checkout Service", "tier": "business", "language": "TypeScript", "status": "critical", "owner": "checkout-team"},
        {"id": "auth-service", "label": "Service", "name": "Authentication Service", "tier": "core", "language": "Python", "status": "critical", "owner": "security-team"},
        {"id": "payment-service", "label": "Service", "name": "Payment Service", "tier": "business", "language": "Java", "status": "degraded", "owner": "payments-team"},
        {"id": "order-service", "label": "Service", "name": "Order Management Service", "tier": "business", "language": "Go", "status": "healthy", "owner": "order-team"},
        {"id": "inventory-service", "label": "Service", "name": "Inventory Service", "tier": "business", "language": "Rust", "status": "healthy", "owner": "logistics-team"},
        {"id": "notification-service", "label": "Service", "name": "Notification Dispatcher", "tier": "async", "language": "Python", "status": "healthy", "owner": "comms-team"},
        {"id": "search-service", "label": "Service", "name": "Catalog Search Service", "tier": "read-heavy", "language": "Python", "status": "healthy", "owner": "search-eng"}
    ]
    for s in services:
        g.add_node(s["id"], s["label"], s)

    # 2. DATABASES & QUEUES
    infrastructure = [
        {"id": "redis-auth-cache", "label": "Database", "name": "Redis Auth Session Cluster", "type": "redis", "version": "7.2.4", "status": "exhausted"},
        {"id": "postgres-order-db", "label": "Database", "name": "Postgres Orders Primary", "type": "postgres", "version": "16.1", "status": "healthy"},
        {"id": "postgres-payment-db", "label": "Database", "name": "Payment PCI Vault DB", "type": "postgres", "version": "15.4", "status": "healthy"},
        {"id": "kafka-cluster", "label": "Queue", "name": "Core Kafka Event Bus", "type": "kafka", "version": "3.6.0", "status": "healthy"},
        {"id": "elasticsearch-cluster", "label": "Database", "name": "Elasticsearch Search Index", "type": "elasticsearch", "version": "8.11.0", "status": "healthy"}
    ]
    for infra in infrastructure:
        g.add_node(infra["id"], infra["label"], infra)

    # 3. DEPLOYMENTS
    deployments = [
        {"id": "deploy-auth-v2.4.1", "label": "Deployment", "version": "v2.4.1", "service": "auth-service", "deployed_at": "28 mins ago", "commit": "8f3a19b", "deployed_by": "ci/cd", "change_summary": "Reduced Redis idle connection timeout & pool max size to 50"},
        {"id": "deploy-checkout-v1.8.0", "label": "Deployment", "version": "v1.8.0", "service": "checkout-service", "deployed_at": "3 hours ago", "commit": "c479e2a", "deployed_by": "ci/cd", "change_summary": "Added idempotent checkout retry token"},
        {"id": "deploy-search-v3.0.2", "label": "Deployment", "version": "v3.0.2", "service": "search-service", "deployed_at": "1 day ago", "commit": "e81d77f", "deployed_by": "ci/cd", "change_summary": "Optimized vector search indexing"}
    ]
    for d in deployments:
        g.add_node(d["id"], d["label"], d)

    # 4. ERROR PATTERNS
    errors = [
        {"id": "err-redis-timeout", "label": "ErrorPattern", "pattern": "ConnectionPoolExhaustedError: Timeout waiting for free Redis connection (5000ms)", "severity": "CRITICAL", "frequency": 420},
        {"id": "err-auth-503", "label": "ErrorPattern", "pattern": "HTTP 503 Service Unavailable: upstream auth-service non-responsive", "severity": "CRITICAL", "frequency": 1280},
        {"id": "err-circuit-breaker", "label": "ErrorPattern", "pattern": "CircuitBreakerOpenException: Checkout->Auth circuit opened (error_rate=64%)", "severity": "HIGH", "frequency": 850},
        {"id": "err-payment-token-invalid", "label": "ErrorPattern", "pattern": "AuthTokenValidationFailed: Unable to verify caller identity", "severity": "HIGH", "frequency": 310}
    ]
    for e in errors:
        g.add_node(e["id"], e["label"], e)

    # 5. METRIC ANOMALIES
    metrics = [
        {"id": "metric-conn-pool-leak", "label": "MetricAnomaly", "name": "Auth Redis Pool Saturation", "metric": "redis_pool_active_connections", "value": "50/50 (100%)", "threshold": "80%", "anomaly_score": 0.98},
        {"id": "metric-checkout-5xx-surge", "label": "MetricAnomaly", "name": "Checkout 5xx Error Surge", "metric": "http_requests_5xx_rate", "value": "48.2%", "threshold": "1.0%", "anomaly_score": 0.95},
        {"id": "metric-gateway-latency", "label": "MetricAnomaly", "name": "API Gateway p99 Latency Surge", "metric": "http_p99_latency_ms", "value": "4850ms", "threshold": "250ms", "anomaly_score": 0.91}
    ]
    for m in metrics:
        g.add_node(m["id"], m["label"], m)

    # 6. HISTORICAL INCIDENTS & RESOLUTIONS (PERSISTENT INCIDENT MEMORY)
    historical_incidents = [
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
    for hi in historical_incidents:
        g.add_node(hi["id"], hi["label"], hi)

    # 7. ACTIVE LIVE INCIDENT (Primary subject of investigation)
    active_incident = {
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
    g.add_node(active_incident["id"], active_incident["label"], active_incident)

    # 8. RESOLUTION NODES
    resolutions = [
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
    for r in resolutions:
        g.add_node(r["id"], r["label"], r)

    # 9. GRAPH RELATIONSHIPS (EDGES)
    # Service dependencies
    g.add_edge("api-gateway", "checkout-service", "DEPENDS_ON", {"type": "REST", "critical": True, "timeout_ms": 3000})
    g.add_edge("api-gateway", "search-service", "DEPENDS_ON", {"type": "REST", "critical": False, "timeout_ms": 1500})
    g.add_edge("checkout-service", "auth-service", "DEPENDS_ON", {"type": "gRPC", "critical": True, "timeout_ms": 1000})
    g.add_edge("checkout-service", "payment-service", "DEPENDS_ON", {"type": "REST", "critical": True, "timeout_ms": 4000})
    g.add_edge("checkout-service", "inventory-service", "DEPENDS_ON", {"type": "gRPC", "critical": True, "timeout_ms": 2000})
    g.add_edge("checkout-service", "order-service", "DEPENDS_ON", {"type": "REST", "critical": True, "timeout_ms": 3000})
    g.add_edge("order-service", "notification-service", "DEPENDS_ON", {"type": "Async", "critical": False, "timeout_ms": 5000})
    g.add_edge("payment-service", "auth-service", "DEPENDS_ON", {"type": "gRPC", "critical": True, "timeout_ms": 1000})

    # Infrastructure connections
    g.add_edge("auth-service", "redis-auth-cache", "CONNECTS_TO", {"protocol": "RESP", "pool_size": 50, "max_conns": 50})
    g.add_edge("order-service", "postgres-order-db", "CONNECTS_TO", {"protocol": "TCP", "pool_size": 100})
    g.add_edge("payment-service", "postgres-payment-db", "CONNECTS_TO", {"protocol": "TCP", "pool_size": 80})
    g.add_edge("order-service", "kafka-cluster", "CONNECTS_TO", {"topic": "orders.v1"})
    g.add_edge("notification-service", "kafka-cluster", "CONNECTS_TO", {"topic": "orders.v1"})
    g.add_edge("search-service", "elasticsearch-cluster", "CONNECTS_TO", {"port": 9200})

    # Deployment edges
    g.add_edge("deploy-auth-v2.4.1", "auth-service", "DEPLOYED_TO", {"timestamp": "2026-10-14T15:47:00Z"})
    g.add_edge("deploy-checkout-v1.8.0", "checkout-service", "DEPLOYED_TO", {"timestamp": "2026-10-14T13:15:00Z"})

    # Error and Anomaly associations
    g.add_edge("deploy-auth-v2.4.1", "err-redis-timeout", "CAUSED_BY", {"evidence": "Pool limit decreased in commit 8f3a19b"})
    g.add_edge("err-redis-timeout", "metric-conn-pool-leak", "PROPAGATES_TO", {"weight": 0.98})
    g.add_edge("metric-conn-pool-leak", "auth-service", "AFFECTS", {"metric_severity": "CRITICAL"})
    g.add_edge("err-redis-timeout", "err-auth-503", "TRIGGERED_BY", {"weight": 0.94})
    g.add_edge("err-auth-503", "err-circuit-breaker", "PROPAGATES_TO", {"service": "checkout-service"})
    g.add_edge("err-circuit-breaker", "metric-checkout-5xx-surge", "PROPAGATES_TO", {"weight": 0.95})
    g.add_edge("metric-checkout-5xx-surge", "checkout-service", "AFFECTS", {"metric_severity": "CRITICAL"})
    g.add_edge("metric-checkout-5xx-surge", "api-gateway", "AFFECTS", {"metric_severity": "HIGH"})

    # Active Incident relationship linkages
    g.add_edge("INC-2026-1042", "checkout-service", "AFFECTS", {"impact_level": "PRIMARY"})
    g.add_edge("INC-2026-1042", "err-circuit-breaker", "TRIGGERED_BY", {"observed_at": "16:18:15Z"})
    g.add_edge("INC-2026-1042", "err-redis-timeout", "TRIGGERED_BY", {"observed_at": "16:18:22Z"})
    g.add_edge("INC-2026-1042", "deploy-auth-v2.4.1", "CAUSED_BY", {"confidence": 0.94})

    # Historical Incident memory linkages
    g.add_edge("INC-2026-0814", "auth-service", "AFFECTS", {"impact_level": "PRIMARY"})
    g.add_edge("INC-2026-0814", "redis-auth-cache", "AFFECTS", {"component": "pool"})
    g.add_edge("INC-2026-0814", "res-conn-pool-tune", "RESOLVED_BY", {"duration_mins": 14})
    g.add_edge("INC-2026-1042", "INC-2026-0814", "SIMILAR_TO", {"similarity": 0.94, "pattern": "Redis connection pool exhaustion in auth-service"})

    logger.info(f"Seeded graph: {len(g.nodes)} nodes, {len(g.edges)} edges.")


# Auto seed on module load
seed_graph_database(falkor_client)
