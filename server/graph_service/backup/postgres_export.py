"""PostgreSQL data export functionality for auth database."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg.exceptions import PostgresError

logger = logging.getLogger(__name__)


class PostgresExporter:
    """Export data from PostgreSQL for backup purposes."""
    
    def __init__(
        self,
        dsn: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 5432,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize PostgreSQL exporter.
        
        Args:
            dsn: Full database connection string
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
        """
        self.dsn = dsn
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = None
        
    async def connect(self) -> None:
        """Connect to PostgreSQL database."""
        if not self.conn:
            if self.dsn:
                self.conn = await asyncpg.connect(self.dsn)
            else:
                self.conn = await asyncpg.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                )
                
    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self.conn:
            await self.conn.close()
            self.conn = None
            
    async def export_all_data(self) -> Dict[str, Any]:
        """Export all auth-related data from PostgreSQL.
        
        Returns:
            Dictionary containing exported data
        """
        await self.connect()
        
        try:
            # Export users
            users = await self._export_users()
            
            # Export OAuth data
            oauth_data = await self._export_oauth_data()
            
            # Export API keys
            api_keys = await self._export_api_keys()
            
            # Get database statistics
            stats = await self._get_database_stats()
            
            return {
                'users': users,
                'oauth': oauth_data,
                'api_keys': api_keys,
                'statistics': stats,
            }
            
        except PostgresError as e:
            logger.error(f'Failed to export PostgreSQL data: {e}')
            raise
        finally:
            await self.close()
            
    async def _export_users(self) -> List[Dict[str, Any]]:
        """Export user data.
        
        Returns:
            List of user records
        """
        query = """
        SELECT 
            id,
            email,
            created_at,
            updated_at,
            is_active,
            metadata
        FROM users
        ORDER BY id
        """
        
        rows = await self.conn.fetch(query)
        users = []
        
        for row in rows:
            user_data = {
                'id': str(row['id']),
                'email': row['email'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                'is_active': row['is_active'],
                'metadata': row['metadata'] if row['metadata'] else {},
            }
            users.append(user_data)
            
        logger.info(f'Exported {len(users)} users from PostgreSQL')
        return users
        
    async def _export_oauth_data(self) -> List[Dict[str, Any]]:
        """Export OAuth provider data.
        
        Returns:
            List of OAuth records
        """
        # Check if oauth_accounts table exists
        table_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'oauth_accounts'
            )
        """)
        
        if not table_exists:
            logger.info('OAuth accounts table does not exist, skipping')
            return []
            
        query = """
        SELECT 
            id,
            user_id,
            provider,
            provider_user_id,
            access_token,
            refresh_token,
            expires_at,
            created_at,
            updated_at
        FROM oauth_accounts
        ORDER BY id
        """
        
        rows = await self.conn.fetch(query)
        oauth_data = []
        
        for row in rows:
            oauth_record = {
                'id': str(row['id']),
                'user_id': str(row['user_id']),
                'provider': row['provider'],
                'provider_user_id': row['provider_user_id'],
                # Mask sensitive tokens in backup
                'access_token_masked': f"***{row['access_token'][-8:]}" if row['access_token'] else None,
                'refresh_token_masked': f"***{row['refresh_token'][-8:]}" if row['refresh_token'] else None,
                'expires_at': row['expires_at'].isoformat() if row['expires_at'] else None,
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
            }
            oauth_data.append(oauth_record)
            
        logger.info(f'Exported {len(oauth_data)} OAuth records from PostgreSQL')
        return oauth_data
        
    async def _export_api_keys(self) -> List[Dict[str, Any]]:
        """Export API key data.
        
        Returns:
            List of API key records
        """
        # Check if api_keys table exists
        table_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'api_keys'
            )
        """)
        
        if not table_exists:
            logger.info('API keys table does not exist, skipping')
            return []
            
        query = """
        SELECT 
            id,
            user_id,
            name,
            key_prefix,
            is_active,
            expires_at,
            last_used_at,
            created_at,
            updated_at,
            metadata
        FROM api_keys
        ORDER BY id
        """
        
        rows = await self.conn.fetch(query)
        api_keys = []
        
        for row in rows:
            key_data = {
                'id': str(row['id']),
                'user_id': str(row['user_id']),
                'name': row['name'],
                'key_prefix': row['key_prefix'],
                'is_active': row['is_active'],
                'expires_at': row['expires_at'].isoformat() if row['expires_at'] else None,
                'last_used_at': row['last_used_at'].isoformat() if row['last_used_at'] else None,
                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None,
                'metadata': row['metadata'] if row['metadata'] else {},
            }
            api_keys.append(key_data)
            
        logger.info(f'Exported {len(api_keys)} API keys from PostgreSQL')
        return api_keys
        
    async def _get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Database statistics
        """
        stats = {}
        
        # Count users
        user_count = await self.conn.fetchval('SELECT COUNT(*) FROM users')
        stats['user_count'] = user_count
        
        # Count active users
        active_user_count = await self.conn.fetchval(
            'SELECT COUNT(*) FROM users WHERE is_active = true'
        )
        stats['active_user_count'] = active_user_count
        
        # Count OAuth accounts if table exists
        oauth_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'oauth_accounts'
            )
        """)
        
        if oauth_exists:
            oauth_count = await self.conn.fetchval('SELECT COUNT(*) FROM oauth_accounts')
            stats['oauth_account_count'] = oauth_count
            
        # Count API keys if table exists
        api_keys_exists = await self.conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'api_keys'
            )
        """)
        
        if api_keys_exists:
            api_key_count = await self.conn.fetchval('SELECT COUNT(*) FROM api_keys')
            active_key_count = await self.conn.fetchval(
                'SELECT COUNT(*) FROM api_keys WHERE is_active = true'
            )
            stats['api_key_count'] = api_key_count
            stats['active_api_key_count'] = active_key_count
            
        return stats
        
    async def export_by_query(self, query: str) -> List[Dict[str, Any]]:
        """Export data using a custom SQL query.
        
        Args:
            query: Custom SQL query
            
        Returns:
            Query results
        """
        await self.connect()
        
        try:
            rows = await self.conn.fetch(query)
            data = []
            
            for row in rows:
                record = {}
                for key, value in row.items():
                    # Convert datetime objects to ISO format
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
                    else:
                        record[key] = value
                data.append(record)
                
            return data
            
        except PostgresError as e:
            logger.error(f'Failed to execute custom export query: {e}')
            raise
        finally:
            await self.close()