"""Restore service for recovering data from S3 backups."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import asyncpg
from neo4j import AsyncGraphDatabase
from neo4j.exceptions import Neo4jError

from .s3_service import S3BackupService

logger = logging.getLogger(__name__)


class RestoreService:
    """Service for restoring data from S3 backups."""
    
    def __init__(
        self,
        s3_service: S3BackupService,
        neo4j_uri: str,
        neo4j_username: str,
        neo4j_password: str,
        neo4j_database: str = 'neo4j',
        postgres_dsn: Optional[str] = None,
    ):
        """Initialize restore service.
        
        Args:
            s3_service: S3 backup service instance
            neo4j_uri: Neo4j connection URI
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            neo4j_database: Neo4j database name
            postgres_dsn: PostgreSQL connection string
        """
        self.s3_service = s3_service
        self.neo4j_uri = neo4j_uri
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database
        self.postgres_dsn = postgres_dsn
        
    async def restore_from_backup(
        self,
        backup_key: str,
        restore_neo4j: bool = True,
        restore_postgres: bool = True,
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """Restore data from a specific backup.
        
        Args:
            backup_key: S3 object key of the backup
            restore_neo4j: Whether to restore Neo4j data
            restore_postgres: Whether to restore PostgreSQL data
            clear_existing: Whether to clear existing data before restore
            
        Returns:
            Restore operation results
        """
        logger.info(f'Starting restore from backup: {backup_key}')
        
        # Download backup from S3
        backup_data = await self.s3_service.download_backup(backup_key)
        
        results = {
            'backup_key': backup_key,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': backup_data.get('metadata', {}),
        }
        
        # Restore Neo4j data
        if restore_neo4j and 'neo4j' in backup_data:
            neo4j_result = await self._restore_neo4j(
                backup_data['neo4j'],
                clear_existing=clear_existing
            )
            results['neo4j'] = neo4j_result
            
        # Restore PostgreSQL data
        if restore_postgres and 'postgres' in backup_data:
            postgres_result = await self._restore_postgres(
                backup_data['postgres'],
                clear_existing=clear_existing
            )
            results['postgres'] = postgres_result
            
        logger.info('Restore operation completed')
        return results
        
    async def _restore_neo4j(
        self,
        neo4j_data: Dict[str, Any],
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """Restore Neo4j data.
        
        Args:
            neo4j_data: Neo4j backup data
            clear_existing: Whether to clear existing data
            
        Returns:
            Restore results
        """
        driver = AsyncGraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_username, self.neo4j_password)
        )
        
        try:
            async with driver.session(database=self.neo4j_database) as session:
                # Clear existing data if requested
                if clear_existing:
                    await self._clear_neo4j_data(session)
                    
                # Create ID mapping for nodes
                node_id_mapping = {}
                
                # Restore nodes
                nodes_restored = 0
                for node in neo4j_data.get('nodes', []):
                    new_id = await self._restore_node(session, node)
                    node_id_mapping[node['id']] = new_id
                    nodes_restored += 1
                    
                # Restore relationships
                edges_restored = 0
                for edge in neo4j_data.get('edges', []):
                    await self._restore_edge(session, edge, node_id_mapping)
                    edges_restored += 1
                    
                return {
                    'nodes_restored': nodes_restored,
                    'edges_restored': edges_restored,
                    'statistics': neo4j_data.get('statistics', {}),
                }
                
        except Neo4jError as e:
            logger.error(f'Failed to restore Neo4j data: {e}')
            raise
        finally:
            await driver.close()
            
    async def _clear_neo4j_data(self, session) -> None:
        """Clear all data from Neo4j database.
        
        Args:
            session: Neo4j session
        """
        logger.warning('Clearing all data from Neo4j database')
        
        # Delete all relationships first
        await session.run('MATCH ()-[r]->() DELETE r')
        
        # Delete all nodes
        await session.run('MATCH (n) DELETE n')
        
        logger.info('Neo4j database cleared')
        
    async def _restore_node(self, session, node_data: Dict[str, Any]) -> int:
        """Restore a single node to Neo4j.
        
        Args:
            session: Neo4j session
            node_data: Node data from backup
            
        Returns:
            New node ID
        """
        # Build CREATE query with labels and properties
        labels = ':'.join(node_data['labels']) if node_data['labels'] else ''
        
        if labels:
            query = f'CREATE (n:{labels} $properties) RETURN id(n) as id'
        else:
            query = 'CREATE (n $properties) RETURN id(n) as id'
            
        result = await session.run(query, properties=node_data['properties'])
        record = await result.single()
        
        return record['id']
        
    async def _restore_edge(
        self,
        session,
        edge_data: Dict[str, Any],
        node_id_mapping: Dict[int, int],
    ) -> None:
        """Restore a single relationship to Neo4j.
        
        Args:
            session: Neo4j session
            edge_data: Edge data from backup
            node_id_mapping: Mapping from old to new node IDs
        """
        # Get new node IDs
        source_id = node_id_mapping.get(edge_data['source_id'])
        target_id = node_id_mapping.get(edge_data['target_id'])
        
        if source_id is None or target_id is None:
            logger.warning(
                f"Skipping edge {edge_data['type']} - missing node mapping"
            )
            return
            
        # Create relationship
        query = f"""
        MATCH (n) WHERE id(n) = $source_id
        MATCH (m) WHERE id(m) = $target_id
        CREATE (n)-[r:{edge_data['type']} $properties]->(m)
        """
        
        await session.run(
            query,
            source_id=source_id,
            target_id=target_id,
            properties=edge_data['properties']
        )
        
    async def _restore_postgres(
        self,
        postgres_data: Dict[str, Any],
        clear_existing: bool = False,
    ) -> Dict[str, Any]:
        """Restore PostgreSQL data.
        
        Args:
            postgres_data: PostgreSQL backup data
            clear_existing: Whether to clear existing data
            
        Returns:
            Restore results
        """
        if not self.postgres_dsn:
            logger.warning('PostgreSQL DSN not configured, skipping restore')
            return {'error': 'PostgreSQL not configured'}
            
        conn = await asyncpg.connect(self.postgres_dsn)
        
        try:
            # Restore users
            users_restored = 0
            for user in postgres_data.get('users', []):
                if await self._restore_user(conn, user, clear_existing):
                    users_restored += 1
                    
            return {
                'users_restored': users_restored,
                'statistics': postgres_data.get('statistics', {}),
            }
            
        except Exception as e:
            logger.error(f'Failed to restore PostgreSQL data: {e}')
            raise
        finally:
            await conn.close()
            
    async def _restore_user(
        self,
        conn: asyncpg.Connection,
        user_data: Dict[str, Any],
        update_existing: bool = False,
    ) -> bool:
        """Restore a single user to PostgreSQL.
        
        Args:
            conn: PostgreSQL connection
            user_data: User data from backup
            update_existing: Whether to update existing users
            
        Returns:
            Whether the user was restored
        """
        # Check if user exists
        existing = await conn.fetchval(
            'SELECT id FROM users WHERE email = $1',
            user_data['email']
        )
        
        if existing and not update_existing:
            logger.info(f"User {user_data['email']} already exists, skipping")
            return False
            
        if existing:
            # Update existing user
            await conn.execute("""
                UPDATE users 
                SET 
                    is_active = $2,
                    metadata = $3,
                    updated_at = NOW()
                WHERE email = $1
            """, 
                user_data['email'],
                user_data['is_active'],
                json.dumps(user_data.get('metadata', {}))
            )
        else:
            # Insert new user
            await conn.execute("""
                INSERT INTO users (id, email, is_active, metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    is_active = EXCLUDED.is_active,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
            """,
                UUID(user_data['id']),
                user_data['email'],
                user_data['is_active'],
                json.dumps(user_data.get('metadata', {})),
                datetime.fromisoformat(user_data['created_at']) if user_data['created_at'] else datetime.utcnow(),
                datetime.fromisoformat(user_data['updated_at']) if user_data['updated_at'] else datetime.utcnow(),
            )
            
        return True
        
    async def initialize_from_latest_backup(self) -> Optional[Dict[str, Any]]:
        """Initialize the system from the latest available backup.
        
        This is called on server startup to restore from S3 if needed.
        
        Returns:
            Restore results or None if no backups available
        """
        logger.info('Checking for latest backup to initialize from')
        
        # List available backups
        backups = await self.s3_service.list_backups(limit=1)
        
        if not backups:
            logger.info('No backups available for initialization')
            return None
            
        latest_backup = backups[0]
        logger.info(f"Found latest backup: {latest_backup['key']}")
        
        # Check if database is empty (needs initialization)
        needs_init = await self._check_needs_initialization()
        
        if not needs_init:
            logger.info('Database already contains data, skipping initialization')
            return None
            
        # Restore from latest backup
        logger.info('Initializing from latest backup')
        return await self.restore_from_backup(
            latest_backup['key'],
            restore_neo4j=True,
            restore_postgres=True,
            clear_existing=False
        )
        
    async def _check_needs_initialization(self) -> bool:
        """Check if the database needs initialization.
        
        Returns:
            True if database is empty and needs initialization
        """
        # Check Neo4j
        driver = AsyncGraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_username, self.neo4j_password)
        )
        
        try:
            async with driver.session(database=self.neo4j_database) as session:
                result = await session.run('MATCH (n) RETURN count(n) as count LIMIT 1')
                record = await result.single()
                
                if record['count'] > 0:
                    return False
                    
        except Neo4jError:
            # If we can't connect, assume we need initialization
            pass
        finally:
            await driver.close()
            
        return True