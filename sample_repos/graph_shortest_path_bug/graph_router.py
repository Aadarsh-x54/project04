"""
Weighted Graph Shortest-Path Router (Dijkstra & Bellman-Ford Edge Validation)
Great for Computer Science students learning graph algorithms and debugging edge cases.
Contains 3 intentional bugs:
1. Negative edge weights are not rejected in Dijkstra's algorithm.
2. Stale priority-queue entries overwrite shorter paths or fail to reconstruct the full path including the start node.
3. Unreachable destination returns 0.0 instead of float('inf') / raising ValueError.
"""

import heapq
from typing import Dict, List, Tuple, Optional


class GraphRouter:
    def __init__(self):
        self.adj: Dict[str, List[Tuple[str, float]]] = {}

    def add_edge(self, u: str, v: str, weight: float) -> None:
        if u not in self.adj:
            self.adj[u] = []
        if v not in self.adj:
            self.adj[v] = []
        self.adj[u].append((v, float(weight)))

    def shortest_path(self, start: str, target: str) -> Dict[str, object]:
        """
        Compute shortest distance and node path from `start` to `target` using Dijkstra's algorithm.
        - Must raise ValueError if any traversed edge has a negative weight.
        - If `target` is unreachable from `start`, return {"distance": float("inf"), "path": []}.
        - Otherwise return {"distance": <float>, "path": [start, ..., target]}.
        """
        if start not in self.adj or target not in self.adj:
            return {"distance": float("inf"), "path": []}

        dist: Dict[str, float] = {node: float("inf") for node in self.adj}
        parent: Dict[str, Optional[str]] = {node: None for node in self.adj}
        dist[start] = 0.0

        pq: List[Tuple[float, str]] = [(0.0, start)]

        while pq:
            current_dist, u = heapq.heappop(pq)
            if current_dist > dist[u]:
                continue

            for v, weight in self.adj.get(u, []):
                # BUG 1: Missing negative weight check (`if weight < 0: raise ValueError(...)`)
                new_dist = current_dist + weight
                # BUG 2: Uses `>=` instead of `<` when relaxing edges or fails to update properly!
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    parent[v] = u
                    heapq.heappush(pq, (new_dist, v))

        # BUG 3: If target is unreachable (dist[target] == inf), returns 0.0 instead of inf!
        if dist[target] == float("inf"):
            return {"distance": 0.0, "path": []}

        # BUG 4: Path reconstruction stops before prepending `start` node!
        path: List[str] = []
        curr: Optional[str] = target
        while curr is not None and curr != start:
            path.append(curr)
            curr = parent[curr]
        path.reverse()

        return {
            "distance": round(dist[target], 4),
            "path": path,
        }

