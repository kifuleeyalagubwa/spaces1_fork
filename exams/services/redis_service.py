# exams/services/redis_service.py
import redis
import time
import logging
import os
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self):
        """Initialize Redis service WITHOUT connecting immediately."""
        self._redis_client = None
        self._redis_url = None
        self._initialized = False
        self._connected = False
        logger.info("RedisService initialized (lazy loading enabled)")
    
    def _ensure_connection(self):
        """Establish Redis connection only when needed (lazy loading)."""
        if self._connected:
            return True
        
        if self._initialized and not self._connected:
            return False
        
        self._initialized = True
        self._redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
        
        # Don't try to connect during Django setup/management commands
        import sys
        if 'manage.py' in sys.argv[0] and 'runserver' not in ' '.join(sys.argv):
            logger.info("Skipping Redis connection during Django management commands")
            return False
        
        # Skip if using default localhost URL (means Redis not configured yet)
        if self._redis_url == 'redis://localhost:6379':
            if settings.DEBUG:
                logger.warning("Using default Redis URL, Redis features will work when URL is set")
                return False
            else:
                logger.error("Redis URL not configured in production!")
                return False
        
        try:
            logger.info(f"🔌 Establishing Redis connection to: {self._redis_url}")
            
            connection_params = {
                'decode_responses': True,
                'socket_connect_timeout': 5,
                'socket_keepalive': True,
                'retry_on_timeout': True,
                'max_connections': 10,
                'health_check_interval': 30,
            }
            
            # Handle SSL for production Redis
            if self._redis_url.startswith('rediss://'):
                connection_params['ssl_cert_reqs'] = None
                connection_params['ssl'] = True
                logger.info("Using SSL for Redis connection")
            
            # Create connection with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._redis_client = redis.from_url(self._redis_url, **connection_params)
                    
                    # Test connection with short timeout
                    self._redis_client.ping()
                    self._connected = True
                    logger.info("✅ Redis connected successfully")
                    
                    # Log Redis info
                    try:
                        info = self._redis_client.info()
                        logger.info(f"Redis version: {info.get('redis_version')}, "
                                   f"Memory used: {info.get('used_memory_human')}")
                    except:
                        pass
                    
                    return True
                    
                except redis.ConnectionError as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 * (attempt + 1)
                        logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Redis connection failed after {max_retries} retries: {str(e)}")
                        if settings.DEBUG:
                            logger.warning("Redis connection failed in development mode, continuing without Redis")
                            self._redis_client = None
                            return False
                        else:
                            logger.critical("Redis connection failed in production, but continuing")
                            self._redis_client = None
                            return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected Redis error: {str(e)}")
            self._redis_client = None
            self._connected = False
            return False
    
    def _safe_operation(self, operation, *args, **kwargs):
        """Safely perform a Redis operation with automatic connection."""
        try:
            if not self._ensure_connection() or self._redis_client is None:
                if settings.DEBUG:
                    logger.debug(f"Redis not available for {operation.__name__}")
                return None
            
            return operation(self._redis_client, *args, **kwargs)
        except redis.RedisError as e:
            logger.error(f"Redis error in {operation.__name__}: {str(e)}")
            # Reset connection on error
            self._redis_client = None
            self._connected = False
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {operation.__name__}: {str(e)}")
            return None
    
    # ============================================================================
    # ATTEMPT TRACKING METHODS
    # ============================================================================
    
    def cache_attempt_state(self, attempt_id, data, ttl=None):
        def _op(client):
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            result = client.hset(key, mapping=data)
            if ttl:
                client.expire(key, ttl)
            logger.debug(f"Cached attempt {attempt_id}, TTL: {ttl}s")
            return result
        return self._safe_operation(_op) or 0
    
    def get_attempt_state(self, attempt_id):
        def _op(client):
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            return client.hgetall(key)
        return self._safe_operation(_op) or {}
    
    def delete_attempt_state(self, attempt_id):
        def _op(client):
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            result = client.delete(key)
            logger.debug(f"Deleted attempt {attempt_id}: {result} keys")
            return result
        return self._safe_operation(_op) or 0
    
    # ============================================================================
    # GRADING QUEUE METHODS
    # ============================================================================
    
    def add_to_grading_queue(self, attempt_id):
        def _op(client):
            return client.lpush(settings.REDIS_GRADING_QUEUE_KEY, attempt_id)
        return self._safe_operation(_op) or 0
    
    def get_next_grading_task(self):
        def _op(client):
            return client.rpop(settings.REDIS_GRADING_QUEUE_KEY)
        return self._safe_operation(_op)
    
    # ============================================================================
    # AUTO-SUBMISSION METHODS
    # ============================================================================
    
    def schedule_auto_submit(self, attempt_id, exam_duration_minutes):
        def _op(client):
            delay_seconds = exam_duration_minutes * 60
            score = time.time() + delay_seconds
            return client.zadd(settings.REDIS_AUTO_SUBMIT_KEY, {attempt_id: score})
        return self._safe_operation(_op) or 0
    
    def get_due_auto_submits(self):
        def _op(client):
            now = time.time()
            return client.zrangebyscore(settings.REDIS_AUTO_SUBMIT_KEY, 0, now)
        return self._safe_operation(_op) or []
    
    def clear_auto_submit(self, attempt_id):
        def _op(client):
            return client.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
        return self._safe_operation(_op) or 0
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_first_attempts(self):
        def _op(client):
            pattern = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}*"
            keys = client.keys(pattern)
            attempts = []
            for key in keys:
                data = client.hgetall(key)
                if data.get('is_first_attempt') == 'True':
                    attempts.append({
                        'attempt_id': key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, ''),
                        'data': data
                    })
            return attempts
        return self._safe_operation(_op) or []
    
    def cleanup_old_attempts(self, max_age_hours=24):
        def _op(client):
            pattern = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}*"
            keys = client.keys(pattern)
            deleted_count = 0
            current_time = time.time()
            
            for key in keys:
                data = client.hgetall(key)
                if 'start_time' in data:
                    start_time = float(data['start_time'])
                    age_hours = (current_time - start_time) / 3600
                    if age_hours > max_age_hours:
                        attempt_id = key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, '')
                        client.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
                        client.delete(key)
                        deleted_count += 1
            return deleted_count
        return self._safe_operation(_op) or 0
    
    def health_check(self):
        """Check Redis health status."""
        try:
            if self._ensure_connection() and self._redis_client:
                info = self._redis_client.info()
                return {
                    'status': 'healthy',
                    'url': self._redis_url,
                    'version': info.get('redis_version', 'unknown'),
                    'memory_used': info.get('used_memory_human', '0B'),
                    'connected_clients': info.get('connected_clients', 0),
                    'keys': self._redis_client.dbsize(),
                }
            else:
                return {
                    'status': 'disconnected',
                    'url': self._redis_url,
                    'message': 'Redis not configured or connection failed'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'url': self._redis_url
            }
    
    def is_connected(self):
        """Check if Redis is currently connected."""
        if self._redis_client is None:
            return False
        try:
            self._redis_client.ping()
            return True
        except:
            self._redis_client = None
            self._connected = False
            return False


# Create instance - NO CONNECTION IS MADE HERE!
redis_service = RedisService()