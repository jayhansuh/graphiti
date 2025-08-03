"""Neo4j data export functionality."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError
from neo4j.time import DateTime as Neo4jDateTime

logger = logging.getLogger(__name__)


class Neo4jExporter:
    """Export data from Neo4j for backup purposes."""
    
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = 'neo4j',
    ):
        """Initialize Neo4j exporter.
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            database: Database name
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        
    async def connect(self) -> None:
        """Connect to Neo4j database."""
        if not self.driver:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
    async def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            
    async def export_all_data(self) -> Dict[str, Any]:
        """Export all nodes and relationships from Neo4j.
        
        Returns:
            Dictionary containing nodes and edges data
        """
        await self.connect()
        
        try:
            async with self.driver.session(database=self.database) as session:
                # Export all nodes
                nodes = await self._export_nodes(session)
                
                # Export all relationships
                edges = await self._export_edges(session)
                
                # Get database statistics
                stats = await self._get_database_stats(session)
                
                return {
                    'nodes': nodes,
                    'edges': edges,
                    'statistics': stats,
                }
                
        except Neo4jError as e:
            logger.error(f'Failed to export Neo4j data: {e}')
            raise
        finally:
            await self.close()
            
    def _convert_neo4j_types(self, value: Any) -> Any:
        """Convert Neo4j types to JSON-serializable types."""
        if isinstance(value, Neo4jDateTime):
            return value.to_native().isoformat()
        elif isinstance(value, dict):
            return {k: self._convert_neo4j_types(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._convert_neo4j_types(v) for v in value]
        return value
        
    async def _export_nodes(self, session) -> List[Dict[str, Any]]:
        """Export all nodes from Neo4j.
        
        Args:
            session: Neo4j session
            
        Returns:
            List of node dictionaries
        """
        query = """
        MATCH (n)
        RETURN 
            id(n) as id,
            labels(n) as labels,
            properties(n) as properties
        ORDER BY id(n)
        """
        
        result = await session.run(query)
        nodes = []
        
        async for record in result:
            node_data = {
                'id': record['id'],
                'labels': record['labels'],
                'properties': self._convert_neo4j_types(dict(record['properties'])) if record['properties'] else {}
            }
            nodes.append(node_data)
            
        logger.info(f'Exported {len(nodes)} nodes from Neo4j')
        return nodes
        
    async def _export_edges(self, session) -> List[Dict[str, Any]]:
        """Export all relationships from Neo4j.
        
        Args:
            session: Neo4j session
            
        Returns:
            List of relationship dictionaries
        """
        query = """
        MATCH (n)-[r]->(m)
        RETURN 
            id(r) as id,
            type(r) as type,
            id(n) as source_id,
            id(m) as target_id,
            properties(r) as properties
        ORDER BY id(r)
        """
        
        result = await session.run(query)
        edges = []
        
        async for record in result:
            edge_data = {
                'id': record['id'],
                'type': record['type'],
                'source_id': record['source_id'],
                'target_id': record['target_id'],
                'properties': self._convert_neo4j_types(dict(record['properties'])) if record['properties'] else {}
            }
            edges.append(edge_data)
            
        logger.info(f'Exported {len(edges)} relationships from Neo4j')
        return edges
        
    async def _get_database_stats(self, session) -> Dict[str, Any]:
        """Get database statistics.
        
        Args:
            session: Neo4j session
            
        Returns:
            Database statistics
        """
        # Count nodes by label
        node_count_query = """
        MATCH (n)
        RETURN labels(n) as labels, count(n) as count
        """
        
        result = await session.run(node_count_query)
        node_counts = {}
        
        async for record in result:
            label_key = ':'.join(sorted(record['labels'])) if record['labels'] else 'unlabeled'
            node_counts[label_key] = record['count']
            
        # Count relationships by type
        edge_count_query = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        """
        
        result = await session.run(edge_count_query)
        edge_counts = {}
        
        async for record in result:
            edge_counts[record['type']] = record['count']
            
        return {
            'node_counts_by_label': node_counts,
            'edge_counts_by_type': edge_counts,
            'total_nodes': sum(node_counts.values()),
            'total_edges': sum(edge_counts.values()),
        }
        
    async def export_by_query(self, cypher_query: str) -> List[Dict[str, Any]]:
        """Export data using a custom Cypher query.
        
        Args:
            cypher_query: Custom Cypher query
            
        Returns:
            Query results
        """
        await self.connect()
        
        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run(cypher_query)
                data = []
                
                async for record in result:
                    data.append(dict(record))
                    
                return data
                
        except Neo4jError as e:
            logger.error(f'Failed to execute custom export query: {e}')
            raise
        finally:
            await self.close()