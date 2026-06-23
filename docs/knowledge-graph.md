# Knowledge Graph Design

## Graph Database

Neo4j stores link-analysis optimized data. PostgreSQL remains the system of record. Graph data can be rebuilt from PostgreSQL if needed.

## Node Labels

- `Person`
- `Organization`
- `Location`
- `Event`
- `Document`
- `Image`
- `Video`
- `Audio`
- `Website`
- `SocialProfile`
- `Vehicle`
- `Object`
- `Case`

## Relationship Types

- `ASSOCIATED_WITH`
- `LOCATED_AT`
- `MENTIONED_IN`
- `AUTHORED`
- `APPEARED_IN`
- `CONNECTED_TO`
- `MEMBER_OF`
- `EMPLOYED_BY`
- `OWNS`
- `OPERATES`
- `TRAVELED_TO`
- `POSTED`
- `ATTENDED`
- `REFERENCES`
- `SAME_AS_CANDIDATE`

## Common Edge Properties

```cypher
{
  case_id: "...",
  source_reference_id: "...",
  confidence: 0.82,
  review_status: "candidate",
  extractor: "entity-agent",
  extractor_version: "0.1.0",
  first_seen_at: datetime(),
  last_seen_at: datetime()
}
```

## Graph Algorithms

MVP:

- Ego network expansion.
- Shortest path between entities.
- Degree centrality.
- Connected components.
- Community detection with Louvain.

Production:

- Influence mapping with weighted centrality.
- Temporal graph snapshots.
- Similarity-based duplicate detection.
- Graph anomaly detection.

## Visualization

The dashboard should support:

- Case-scoped graph view.
- Filters by entity type, confidence, review status, source, and date.
- Edge provenance drawer.
- Cluster coloring.
- Timeline scrubber.
- Analyst notes on nodes and edges.

