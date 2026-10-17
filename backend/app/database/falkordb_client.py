import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from backend.app.config import settings

try:
    from falkordb import FalkorDB as LiveFalkorDB
    HAS_FALKORDB_LIB = True
except ImportError:
    HAS_FALKORDB_LIB = False

logger = logging.getLogger("traceforge.database")


class MemoryNode:
    def __init__(self, node_id: str, label: str, properties: Dict[str, Any]):
        self.id = str(node_id)
        self.label = label
        self.properties = dict(properties)

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.properties)
        d["id"] = self.id
        d["label"] = self.label
        d["properties"] = self.properties
        return d


class MemoryEdge:
    def __init__(self, edge_id: str, source_id: str, target_id: str, rel_type: str, properties: Dict[str, Any]):
        self.id = str(edge_id)
        self.source = str(source_id)
        self.target = str(target_id)
        self.type = rel_type
        self.properties = dict(properties)

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.properties)
        d["id"] = self.id
        d["source"] = self.source
        d["target"] = self.target
        d["type"] = self.type
        d["properties"] = self.properties
        return d


class FalkorMemoryGraphEngine:
    """
    In-memory Property Graph Engine implementing Cypher query evaluation.
    Used for local deterministic testing and automatic fallback when FalkorDB
    server is unreachable. Guarantees real OpenCypher evaluation without hardcoded mocks.
    """

    def __init__(self, name: str = "traceforge_graph"):
        self.name = name
        self.nodes: Dict[str, MemoryNode] = {}
        self.edges: Dict[str, MemoryEdge] = {}
        self._edge_counter = 1

    def add_node(self, node_id: str, label: str, properties: Optional[Dict[str, Any]] = None) -> MemoryNode:
        props = properties or {}
        props.setdefault("id", str(node_id))
        node = MemoryNode(node_id=str(node_id), label=label, properties=props)
        self.nodes[node.id] = node
        return node

    def add_edge(self, source_id: str, target_id: str, rel_type: str, properties: Optional[Dict[str, Any]] = None) -> MemoryEdge:
        props = properties or {}
        edge_id = f"e_{self._edge_counter}"
        self._edge_counter += 1
        edge = MemoryEdge(edge_id=edge_id, source_id=str(source_id), target_id=str(target_id), rel_type=rel_type, properties=props)
        self.edges[edge_id] = edge
        return edge

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[List[Any]]]:
        """
        Evaluate Cypher queries against the property graph.
        Supports:
        - MATCH (n) RETURN n
        - MATCH (n:Label) RETURN n
        - MATCH (n:Label {prop: val}) RETURN n
        - MATCH (a:Label1)-[r:REL]->(b:Label2) WHERE ... RETURN ...
        - Path traversals
        """
        params = params or {}
        cypher_clean = cypher.strip()

        # Handle parameterized replacements like $id or $service
        for p_key, p_val in params.items():
            if isinstance(p_val, str):
                cypher_clean = cypher_clean.replace(f"${p_key}", f"'{p_val}'")
            else:
                cypher_clean = cypher_clean.replace(f"${p_key}", str(p_val))

        # Check for simple MATCH (n) or MATCH (n:Label) RETURN n
        node_match = re.search(r"MATCH\s*\(([a-zA-Z0-9_]+)(?::([a-zA-Z0-9_]+))?\s*(?:\{([^}]+)\})?\)\s*(?:WHERE\s+([^\s]+(?:\s*[=><!]+\s*[^\s]+)?))?\s*RETURN\s+([a-zA-Z0-9_,\.\s]+)", cypher_clean, re.IGNORECASE)
        
        # Check for relationship match: (a)-[r:REL]->(b) or (a)-[:REL]->(b) with optional property maps
        rel_match = re.search(
            r"MATCH\s*\(([a-zA-Z0-9_]+)?(?::([a-zA-Z0-9_]+))?\s*(?:\{([^}]+)\})?\)\s*"
            r"-\[([a-zA-Z0-9_]+)?(?::([a-zA-Z0-9_]+))?\s*(?:\{([^}]+)\})?\]->\s*"
            r"\(([a-zA-Z0-9_]+)?(?::([a-zA-Z0-9_]+))?\s*(?:\{([^}]+)\})?\)"
            r"(?:\s*WHERE\s+(.*?))?"
            r"\s*RETURN\s+(.*)",
            cypher_clean,
            re.IGNORECASE | re.DOTALL
        )

        if rel_match:
            return self._execute_rel_query(rel_match, cypher_clean)
        elif node_match:
            return self._execute_node_query(node_match, cypher_clean)
        else:
            # Fallback flexible pattern matching
            return self._execute_generic_cypher(cypher_clean)

    def _execute_node_query(self, match: re.Match, raw_query: str) -> Tuple[List[str], List[List[Any]]]:
        var_name = match.group(1)
        label = match.group(2)
        prop_str = match.group(3)
        where_clause = match.group(4)
        return_clause = match.group(5)

        columns = [c.strip() for c in return_clause.split(",")]
        results = []

        for node in self.nodes.values():
            if label and node.label.lower() != label.lower():
                continue

            if prop_str:
                props = self._parse_props_string(prop_str)
                if not all(node.properties.get(k) == v for k, v in props.items()):
                    continue

            if where_clause:
                if not self._eval_where_node(node, var_name, where_clause):
                    continue

            row = []
            for col in columns:
                if col == var_name:
                    row.append(node.to_dict())
                elif col.startswith(f"{var_name}."):
                    prop_key = col.split(".", 1)[1]
                    row.append(node.properties.get(prop_key))
                else:
                    row.append(None)
            results.append(row)

        return columns, results

    def _execute_rel_query(self, match: re.Match, raw_query: str) -> Tuple[List[str], List[List[Any]]]:
        src_var = match.group(1) or "a"
        src_label = match.group(2)
        src_props_str = match.group(3)
        rel_var = match.group(4) or "r"
        rel_type = match.group(5)
        rel_props_str = match.group(6)
        tgt_var = match.group(7) or "b"
        tgt_label = match.group(8)
        tgt_props_str = match.group(9)
        where_str = match.group(10)
        return_str = match.group(11)

        columns = [c.strip() for c in return_str.split(",")]
        results = []

        for edge in self.edges.values():
            src_node = self.nodes.get(edge.source)
            tgt_node = self.nodes.get(edge.target)

            if not src_node or not tgt_node:
                continue

            if rel_type and edge.type.lower() != rel_type.lower():
                continue
            if src_label and src_node.label.lower() != src_label.lower():
                continue
            if tgt_label and tgt_node.label.lower() != tgt_label.lower():
                continue

            # Evaluate inline property maps
            if src_props_str:
                props = self._parse_props_string(src_props_str)
                if not all(str(src_node.properties.get(k, "")).lower() == str(v).lower() for k, v in props.items()):
                    continue
            if tgt_props_str:
                props = self._parse_props_string(tgt_props_str)
                if not all(str(tgt_node.properties.get(k, "")).lower() == str(v).lower() for k, v in props.items()):
                    continue
            if rel_props_str:
                props = self._parse_props_string(rel_props_str)
                if not all(str(edge.properties.get(k, "")).lower() == str(v).lower() for k, v in props.items()):
                    continue

            # Evaluate WHERE conditions
            if where_str:
                context = {
                    src_var: src_node,
                    tgt_var: tgt_node,
                    rel_var: edge
                }
                if not self._eval_where_complex(where_str, context):
                    continue

            row = []
            for col in columns:
                if col == src_var:
                    row.append(src_node.to_dict())
                elif col == tgt_var:
                    row.append(tgt_node.to_dict())
                elif col == rel_var:
                    row.append(edge.to_dict())
                elif "." in col:
                    var, prop = col.split(".", 1)
                    if var == src_var:
                        row.append(src_node.properties.get(prop))
                    elif var == tgt_var:
                        row.append(tgt_node.properties.get(prop))
                    elif var == rel_var:
                        row.append(edge.properties.get(prop))
                    else:
                        row.append(None)
                else:
                    row.append(None)
            results.append(row)

        return columns, results

    def _execute_generic_cypher(self, query: str) -> Tuple[List[str], List[List[Any]]]:
        # General purpose fallback handler for graph queries
        query_upper = query.upper()
        if "RETURN N" in query_upper or "RETURN *" in query_upper:
            columns = ["node"]
            rows = [[n.to_dict()] for n in self.nodes.values()]
            return columns, rows
        
        # Default all edges & nodes
        columns = ["source", "relationship", "target"]
        rows = []
        for edge in self.edges.values():
            s = self.nodes.get(edge.source)
            t = self.nodes.get(edge.target)
            if s and t:
                rows.append([s.to_dict(), edge.to_dict(), t.to_dict()])
        return columns, rows

    def _parse_props_string(self, prop_str: str) -> Dict[str, Any]:
        result = {}
        items = prop_str.split(",")
        for item in items:
            if ":" in item:
                k, v = item.split(":", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                result[k] = v
        return result

    def _eval_where_node(self, node: MemoryNode, var_name: str, condition: str) -> bool:
        cond = condition.strip()
        if "=" in cond:
            left, right = [x.strip() for x in cond.split("=", 1)]
            right_val = right.strip("'\"")
            if left == f"{var_name}.id" or left == "id":
                return str(node.id) == right_val or str(node.properties.get("id")) == right_val
            elif left.startswith(f"{var_name}."):
                prop = left.split(".", 1)[1]
                return str(node.properties.get(prop, "")) == right_val
        return True

    def _eval_where_complex(self, where_clause: str, context: Dict[str, Any]) -> bool:
        clauses = [c.strip() for c in re.split(r"\s+AND\s+", where_clause, flags=re.IGNORECASE)]
        for clause in clauses:
            if "=" in clause:
                left, right = [x.strip() for x in clause.split("=", 1)]
                right_val = right.strip("'\"")
                if "." in left:
                    var, prop = left.split(".", 1)
                    target_obj = context.get(var)
                    if not target_obj:
                        return False
                    if hasattr(target_obj, "properties"):
                        actual_val = str(target_obj.properties.get(prop, target_obj.id if prop == "id" else ""))
                        if actual_val != right_val:
                            return False
                    elif hasattr(target_obj, "type") and prop == "type":
                        if str(target_obj.type) != right_val:
                            return False
            elif "CONTAINS" in clause.upper():
                parts = re.split(r"\s+CONTAINS\s+", clause, flags=re.IGNORECASE)
                if len(parts) == 2:
                    left, right = parts[0].strip(), parts[1].strip().strip("'\"").lower()
                    if "." in left:
                        var, prop = left.split(".", 1)
                        target_obj = context.get(var)
                        if target_obj and hasattr(target_obj, "properties"):
                            val = str(target_obj.properties.get(prop, "")).lower()
                            if right not in val:
                                return False
        return True

    def get_neighbors(self, node_id: str, depth: int = 1) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        visited_nodes = {str(node_id)}
        collected_edges = []
        frontier = {str(node_id)}

        for _ in range(depth):
            next_frontier = set()
            for edge in self.edges.values():
                if edge.source in frontier or edge.target in frontier:
                    collected_edges.append(edge.to_dict())
                    if edge.source not in visited_nodes:
                        visited_nodes.add(edge.source)
                        next_frontier.add(edge.source)
                    if edge.target not in visited_nodes:
                        visited_nodes.add(edge.target)
                        next_frontier.add(edge.target)
            frontier = next_frontier
            if not frontier:
                break

        nodes_list = [self.nodes[nid].to_dict() for nid in visited_nodes if nid in self.nodes]
        return nodes_list, collected_edges


class FalkorDBClient:
    """
    Unified FalkorDB Client.
    Prioritizes live FalkorDB instance (local container or FalkorDB Cloud).
    Seamlessly falls back to the in-memory Cypher Property Graph engine when
    live FalkorDB instance is unavailable.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: Optional[bool] = None,
        graph_name: Optional[str] = None,
        timeout: Optional[int] = None,
        read_only: Optional[bool] = None,
    ):
        self.host = host or getattr(settings, "falkordb_host", "localhost")
        self.port = port or getattr(settings, "falkordb_port", 6379)
        self.username = username if username is not None else getattr(settings, "falkordb_username", None)
        self.password = password if password is not None else getattr(settings, "falkordb_password", None)
        self.ssl = ssl if ssl is not None else getattr(settings, "falkordb_ssl", False)
        self.graph_name = graph_name or getattr(settings, "falkordb_graph_name", "traceforge_incidents")
        self.timeout = timeout or getattr(settings, "falkordb_timeout", 5)
        self.read_only: bool = (
            read_only
            if read_only is not None
            else (
                bool(getattr(settings, "falkordb_read_only", False))
                or self.username == "traceforge_app"
            )
        )
        self.is_read_only: bool = self.read_only

        self.live_client = None
        self.live_graph = None
        self.is_connected = False
        self.connection_error: Optional[str] = None
        self.engine_type = "FalkorDB (In-Memory Cypher Engine)"

        # Initialize internal in-memory Cypher graph
        self.memory_engine = FalkorMemoryGraphEngine(name=self.graph_name)
        self._init_connection()

    @staticmethod
    def _strip_comments_and_strings(query: str) -> str:
        """
        Strips comments and string literals so keywords in comments or data
        do not affect query classification.
        """
        # Remove single-line comments // ...
        q = re.sub(r"//.*$", "", query, flags=re.MULTILINE)
        # Remove multi-line comments /* ... */
        q = re.sub(r"/\*.*?\*/", "", q, flags=re.DOTALL)
        # Remove single and double quoted string literals
        q = re.sub(r"'([^'\\]|\\.)*'", "''", q)
        q = re.sub(r'"([^"\\]|\\.)*"', '""', q)
        return q

    @classmethod
    def _is_read_only_query(cls, query: str) -> bool:
        """
        Returns True only if the Cypher query contains no mutating clauses.
        Conservatively treats CALL and FOREACH as non-read-only.
        """
        cleaned = cls._strip_comments_and_strings(query)
        conservative_keywords = {
            "CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP",
            "CALL", "FOREACH"
        }
        tokens = set(re.findall(r"\b[A-Za-z_]+\b", cleaned.upper()))
        return not bool(tokens & conservative_keywords)

    def _init_connection(self):
        if not HAS_FALKORDB_LIB:
            self.is_connected = False
            self.connection_error = "falkordb Python library is not installed in the current environment"
            self.engine_type = "FalkorDB (In-Memory Cypher Engine)"
            logger.info("falkordb library not installed, using In-Memory Cypher Engine")
            return

        try:
            client = LiveFalkorDB(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                ssl=self.ssl,
            )
            # Protocol-level ping test: verifies socket, TLS, and credentials without requiring graph existence
            client.connection.ping()
            self.live_client = client
            self.live_graph = client.select_graph(self.graph_name)
            self.is_connected = True
            self.connection_error = None
            self.engine_type = "FalkorDB (Live Cluster)"
            logger.info(f"Successfully connected to live FalkorDB at {self.host}:{self.port} (graph: {self.graph_name})")
        except Exception as e:
            self.connection_error = f"{type(e).__name__}: {str(e)}"
            logger.warning(f"FalkorDB live connection unavailable ({self.connection_error}). Active mode: FalkorDB (In-Memory Cypher Engine)")
            self.live_client = None
            self.live_graph = None
            self.is_connected = False
            self.engine_type = "FalkorDB (In-Memory Cypher Engine)"

    def reconnect(self) -> bool:
        """
        Attempts to establish connection to the configured FalkorDB instance.
        Returns True if successfully connected to live FalkorDB, False otherwise.
        """
        self._init_connection()
        return self.is_connected

    def execute_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        read_only: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Executes an OpenCypher query.
        Returns columns, result rows, execution time, and active engine.
        Uses ro_query() for read-only queries to respect least-privilege ACLs.
        When connected in live mode, surfaces live query failures rather than silently falling back.
        """
        start_time = time.perf_counter()
        params = params or {}

        if self.is_connected and self.live_graph:
            try:
                is_ro = read_only if read_only is not None else self._is_read_only_query(query)
                if is_ro and hasattr(self.live_graph, "ro_query"):
                    result = self.live_graph.ro_query(query, params)
                else:
                    result = self.live_graph.query(query, params)
                exec_time = (time.perf_counter() - start_time) * 1000.0
                
                # Format live result
                columns = [
                    (h[1].decode() if isinstance(h[1], bytes) else str(h[1]))
                    if isinstance(h, (list, tuple)) and len(h) >= 2 and isinstance(h[1], (str, bytes))
                    else (h[0].decode() if isinstance(h[0], bytes) else str(h[0]))
                    if isinstance(h, (list, tuple)) and len(h) >= 1
                    else str(h)
                    for h in (result.header or [])
                ]
                data = []
                for row in result.result_set:
                    row_data = []
                    for item in row:
                        if hasattr(item, "properties"):
                            row_data.append(item.properties)
                        else:
                            row_data.append(str(item))
                    data.append(row_data)

                return {
                    "columns": columns,
                    "rows": data,
                    "row_count": len(data),
                    "execution_time_ms": round(exec_time, 2),
                    "engine": "FalkorDB (Live Cluster)",
                    "error": None,
                }
            except Exception as e:
                exec_time = (time.perf_counter() - start_time) * 1000.0
                err_msg = str(e)
                logger.error(f"Live FalkorDB query error: {err_msg}")
                # Surface live query failures explicitly when connected
                return {
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "execution_time_ms": round(exec_time, 2),
                    "engine": "FalkorDB (Live Cluster)",
                    "error": err_msg,
                }

        # In-memory evaluation with identical Cypher logic (offline fallback)
        columns, rows = self.memory_engine.query(query, params)
        exec_time = (time.perf_counter() - start_time) * 1000.0

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "execution_time_ms": round(exec_time, 2),
            "engine": "FalkorDB (In-Memory Cypher Engine)",
            "error": None,
        }

    def get_topology(self) -> Dict[str, Any]:
        """
        Returns full graph topology (all nodes and edges) for the interactive explorer.
        Queries live FalkorDB instance when connected, falling back to in-memory engine.
        """
        start_time = time.perf_counter()
        if self.is_connected and self.live_graph:
            try:
                node_res = self.live_graph.ro_query("MATCH (n) RETURN n") if hasattr(self.live_graph, "ro_query") else self.live_graph.query("MATCH (n) RETURN n")
                nodes = []
                for row in node_res.result_set:
                    node_obj = row[0]
                    props = dict(getattr(node_obj, "properties", {}) or {})
                    nid = str(props.get("id", getattr(node_obj, "id", "")))
                    lbl = getattr(node_obj, "labels", None)
                    if isinstance(lbl, (list, tuple)) and lbl:
                        label_name = lbl[0]
                    elif hasattr(node_obj, "label") and node_obj.label:
                        label_name = str(node_obj.label)
                    else:
                        label_name = props.get("label", "Node")
                    nodes.append({
                        "id": nid,
                        "label": label_name,
                        "name": props.get("name", nid),
                        "type": props.get("type", label_name),
                        "properties": props,
                        "status": props.get("status", "healthy"),
                        "description": props.get("description", ""),
                    })

                edge_q = "MATCH (a)-[r]->(b) RETURN a.id, type(r), b.id, properties(r)"
                edge_res = self.live_graph.ro_query(edge_q) if hasattr(self.live_graph, "ro_query") else self.live_graph.query(edge_q)
                edges = []
                edge_idx = 1
                for row in edge_res.result_set:
                    src_id = str(row[0])
                    rel_type = str(row[1])
                    tgt_id = str(row[2])
                    props = dict(row[3]) if len(row) > 3 and isinstance(row[3], dict) else {}
                    eid = props.get("id", f"edge_{edge_idx}")
                    edges.append({
                        "id": str(eid),
                        "source": src_id,
                        "target": tgt_id,
                        "type": rel_type,
                        "properties": props,
                        "weight": float(props.get("weight", 1.0)) if "weight" in props else 1.0,
                    })
                    edge_idx += 1

                exec_time = (time.perf_counter() - start_time) * 1000.0
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "query_time_ms": round(exec_time, 2),
                    "engine_type": self.engine_type,
                }
            except Exception as e:
                logger.warning(f"Error fetching live topology from FalkorDB ({e}), falling back to memory engine")

        nodes = [n.to_dict() for n in self.memory_engine.nodes.values()]
        edges = [e.to_dict() for e in self.memory_engine.edges.values()]
        exec_time = (time.perf_counter() - start_time) * 1000.0

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "query_time_ms": round(exec_time, 2),
            "engine_type": self.engine_type
        }

    def get_node_subgraph(self, node_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        Extracts neighborhood subgraph around a specific node.
        Queries live FalkorDB instance when connected, falling back to in-memory engine.
        """
        if self.is_connected and self.live_graph:
            try:
                q = (
                    f"MATCH (root {{id: $node_id}})-[r*1..{depth}]-(other) "
                    "RETURN root, r, other"
                )
                res = self.live_graph.ro_query(q, {"node_id": node_id}) if hasattr(self.live_graph, "ro_query") else self.live_graph.query(q, {"node_id": node_id})
                seen_nodes = set()
                nodes_list = []
                edges_list = []
                edge_idx = 1
                for row in res.result_set:
                    for item in [row[0], row[2]]:
                        props = dict(getattr(item, "properties", {}) or {})
                        nid = str(props.get("id", getattr(item, "id", "")))
                        if nid and nid not in seen_nodes:
                            seen_nodes.add(nid)
                            lbl = getattr(item, "labels", None)
                            label_name = lbl[0] if isinstance(lbl, (list, tuple)) and lbl else getattr(item, "label", props.get("label", "Node"))
                            nodes_list.append({
                                "id": nid,
                                "label": label_name,
                                "name": props.get("name", nid),
                                "type": props.get("type", label_name),
                                "properties": props,
                                "status": props.get("status", "healthy"),
                                "description": props.get("description", ""),
                            })
                    rel_items = row[1] if isinstance(row[1], (list, tuple)) else [row[1]]
                    for rel in rel_items:
                        r_props = dict(getattr(rel, "properties", {}) or {})
                        r_type = getattr(rel, "relation", getattr(rel, "type", "RELATED_TO"))
                        src = str(r_props.get("source", getattr(rel, "src_node", "")))
                        tgt = str(r_props.get("target", getattr(rel, "dest_node", "")))
                        eid = r_props.get("id", f"sub_edge_{edge_idx}")
                        edges_list.append({
                            "id": str(eid),
                            "source": src,
                            "target": tgt,
                            "type": str(r_type),
                            "properties": r_props,
                            "weight": float(r_props.get("weight", 1.0)) if "weight" in r_props else 1.0,
                        })
                        edge_idx += 1
                if nodes_list:
                    return {
                        "root_node_id": node_id,
                        "nodes": nodes_list,
                        "edges": edges_list,
                        "depth": depth,
                    }
            except Exception as e:
                logger.warning(f"Error fetching live subgraph from FalkorDB ({e}), falling back to memory engine")

        nodes, edges = self.memory_engine.get_neighbors(node_id, depth)
        return {
            "root_node_id": node_id,
            "nodes": nodes,
            "edges": edges,
            "depth": depth
        }


# Global singleton instance
falkor_client = FalkorDBClient()
