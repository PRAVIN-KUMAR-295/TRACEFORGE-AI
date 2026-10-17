import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from backend.app.database.falkordb_client import falkor_client

logger = logging.getLogger("traceforge.memory")


class PersistentMemoryService:
    """
    Manages persistent incident memory inside FalkorDB.
    Stores past postmortems, proven resolution strategies, and error patterns.
    Enables historical recall and transfer of verified operational resolutions.
    """

    def __init__(self):
        self.client = falkor_client

    def get_all_historical_incidents(self) -> List[Dict[str, Any]]:
        """
        Retrieves all past incidents and their resolution relationships from FalkorDB.
        """
        query = "MATCH (i:Incident) RETURN i"
        res = self.client.execute_cypher(query)
        incidents = []
        for row in res["rows"]:
            node = row[0]
            if isinstance(node, dict):
                incidents.append(node)
        return incidents

    def search_memory(self, search_term: str, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Queries FalkorDB for historical incidents matching symptoms or services.
        """
        all_incidents = self.get_all_historical_incidents()
        results = []
        term = search_term.lower()

        for inc in all_incidents:
            title = str(inc.get("title", "")).lower()
            desc = str(inc.get("description", "")).lower()
            root_cause = str(inc.get("root_cause_summary", "")).lower()
            svc = str(inc.get("affected_service", "")).lower()

            matches_svc = True if not service else (service.lower() in svc)
            matches_term = (term in title or term in desc or term in root_cause or term in svc)

            if matches_svc and matches_term:
                results.append(inc)

        return results

    def store_postmortem(
        self,
        incident_id: str,
        title: str,
        affected_service: str,
        root_cause_summary: str,
        resolution_strategy: str,
        transferrable_fix: str,
        impacted_services: List[str]
    ) -> Dict[str, Any]:
        """
        Saves a resolved incident into FalkorDB graph memory with its resolution node and relationships.
        """
        g = self.client.memory_engine

        incident_props = {
            "id": incident_id,
            "title": title,
            "severity": "RESOLVED_CASE",
            "status": "RESOLVED",
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "affected_service": affected_service,
            "root_cause_summary": root_cause_summary,
            "resolution_strategy": resolution_strategy,
            "transferrable_fix": transferrable_fix,
            "impacted_services": impacted_services
        }

        # Add node to FalkorDB graph
        g.add_node(incident_id, "Incident", incident_props)

        # Create resolution node
        res_id = f"res_{incident_id.lower().replace('-', '_')}"
        g.add_node(res_id, "Resolution", {
            "id": res_id,
            "title": f"Resolution for {incident_id}",
            "strategy": resolution_strategy,
            "fix": transferrable_fix
        })

        # Create edges in FalkorDB
        g.add_edge(incident_id, affected_service, "AFFECTS", {"status": "historical"})
        g.add_edge(incident_id, res_id, "RESOLVED_BY", {"applied": True})

        # Sync to live FalkorDB if connected and not read-only
        if self.client.is_connected and self.client.live_graph and not getattr(self.client, "read_only", False):
            try:
                live_props = {k: v for k, v in incident_props.items() if k != "impacted_services"}
                self.client.live_graph.query(
                    "MERGE (i:Incident {id: $id}) SET i += $props",
                    {"id": incident_id, "props": live_props}
                )
                self.client.live_graph.query(
                    "MERGE (r:Resolution {id: $id}) SET r += $props",
                    {"id": res_id, "props": {"id": res_id, "title": f"Resolution for {incident_id}", "strategy": resolution_strategy, "fix": transferrable_fix}}
                )
                self.client.live_graph.query(
                    "MATCH (i:Incident {id: $iid}), (s:Service {id: $sid}) MERGE (i)-[rel:AFFECTS]->(s) SET rel.status = 'historical'",
                    {"iid": incident_id, "sid": affected_service}
                )
                self.client.live_graph.query(
                    "MATCH (i:Incident {id: $iid}), (r:Resolution {id: $rid}) MERGE (i)-[rel:RESOLVED_BY]->(r) SET rel.applied = true",
                    {"iid": incident_id, "rid": res_id}
                )
            except Exception as e:
                logger.warning(f"Failed to sync postmortem to live FalkorDB: {e}")

        logger.info(f"Stored incident {incident_id} and resolution {res_id} in FalkorDB persistent memory.")

        return {
            "incident_id": incident_id,
            "status": "STORED",
            "resolution_id": res_id,
            "node_count": len(g.nodes),
            "edge_count": len(g.edges)
        }


memory_service = PersistentMemoryService()
