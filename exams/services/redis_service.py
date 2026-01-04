import redis
import time
import logging
import os
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)


class RedisService:
    def __init__(self):
        """Initialize Redis connection for Koyeb deployment."""
        try:
            # Get Redis URL from environment (Koyeb provides REDIS_URL)
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
            
            logger.info(f"🔌 Attempting Redis connection to: {redis_url}")
            
            # Parse connection parameters
            connection_params = {
                'decode_responses': True,
                'socket_connect_timeout': 10,
                'socket_keepalive': True,
                'retry_on_timeout': True,
                'max_connections': 20,
                'health_check_interval': 30,
            }
            
            # Handle SSL for Koyeb Redis
            if redis_url.startswith('rediss://'):
                # SSL connection for Koyeb production Redis
                connection_params['ssl_cert_reqs'] = None  # Accept Koyeb's SSL cert
                connection_params['ssl'] = True
                logger.info("🔐 Using SSL connection for Redis")
            
            # Create Redis connection
            self.redis = redis.from_url(redis_url, **connection_params)
            
            # Test connection with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.redis.ping()
                    logger.info(f"✅ Redis connected successfully on attempt {attempt + 1}")
                    break
                except redis.ConnectionError as e:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        logger.warning(f"Redis connection attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        raise e
            
            # Connection successful, log info
            redis_info = self.redis.info()
            logger.info(f"📊 Redis info - Version: {redis_info.get('redis_version')}, "
                       f"Memory: {redis_info.get('used_memory_human')}, "
                       f"Connections: {redis_info.get('connected_clients')}")
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection failed after all retries: {str(e)}")
            
            # For development mode, create a mock client
            if settings.DEBUG:
                self.redis = None
                logger.warning("⚠️ Using null Redis client (development mode only)")
                logger.warning("⚠️ Real-time exam features will not work in development")
            else:
                # In production, we must have Redis
                logger.critical("🚨 Redis is required for production. Application may fail.")
                raise e
                
        except redis.AuthenticationError as e:
            logger.error(f"❌ Redis authentication failed: {str(e)}")
            raise e
            
        except Exception as e:
            logger.error(f"❌ Unexpected Redis error: {str(e)}", exc_info=True)
            raise e

    # ============================================================================
    # ATTEMPT TRACKING METHODS
    # ============================================================================

    def cache_attempt_state(self, attempt_id, data, ttl=None):
        """Cache exam attempt state in Redis."""
        if not self._check_redis():
            return False
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            result = self.redis.hset(key, mapping=data)
            
            if ttl:
                self.redis.expire(key, ttl)
                logger.debug(f"Cached attempt {attempt_id} with TTL {ttl}s")
            else:
                logger.debug(f"Cached attempt {attempt_id} without TTL")
                
            return result > 0
        except Exception as e:
            logger.error(f"Error caching attempt state for {attempt_id}: {str(e)}")
            return False

    def get_attempt_state(self, attempt_id):
        """Get exam attempt state from Redis."""
        if not self._check_redis():
            return {}
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            data = self.redis.hgetall(key)
            logger.debug(f"Retrieved attempt state for {attempt_id}: {len(data)} fields")
            return data
        except Exception as e:
            logger.error(f"Error getting attempt state for {attempt_id}: {str(e)}")
            return {}

    def delete_attempt_state(self, attempt_id):
        """Delete exam attempt state from Redis."""
        if not self._check_redis():
            return False
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            result = self.redis.delete(key)
            logger.debug(f"Deleted attempt state for {attempt_id}: {result} keys removed")
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting attempt state for {attempt_id}: {str(e)}")
            return False

    # ============================================================================
    # GRADING QUEUE METHODS
    # ============================================================================

    def add_to_grading_queue(self, attempt_id):
        """Add attempt to grading queue."""
        if not self._check_redis():
            return False
            
        try:
            result = self.redis.lpush(settings.REDIS_GRADING_QUEUE_KEY, attempt_id)
            logger.debug(f"Added attempt {attempt_id} to grading queue, position: {result}")
            return result > 0
        except Exception as e:
            logger.error(f"Error adding {attempt_id} to grading queue: {str(e)}")
            return False

    def get_next_grading_task(self):
        """Get next task from grading queue."""
        if not self._check_redis():
            return None
            
        try:
            task = self.redis.rpop(settings.REDIS_GRADING_QUEUE_KEY)
            if task:
                logger.debug(f"Retrieved grading task: {task}")
            return task
        except Exception as e:
            logger.error(f"Error getting next grading task: {str(e)}")
            return None

    # ============================================================================
    # AUTO-SUBMISSION METHODS
    # ============================================================================

    def schedule_auto_submit(self, attempt_id, exam_duration_minutes):
        """Schedule auto-submission for an exam attempt."""
        if not self._check_redis():
            return False
            
        try:
            delay_seconds = exam_duration_minutes * 60
            score = time.time() + delay_seconds
            result = self.redis.zadd(
                settings.REDIS_AUTO_SUBMIT_KEY,
                {attempt_id: score}
            )
            logger.debug(f"Scheduled auto-submit for {attempt_id} in {delay_seconds}s")
            return result > 0
        except Exception as e:
            logger.error(f"Error scheduling auto-submit for {attempt_id}: {str(e)}")
            return False

    def get_due_auto_submits(self):
        """Get all due auto-submissions."""
        if not self._check_redis():
            return []
            
        try:
            now = time.time()
            due_attempts = self.redis.zrangebyscore(
                settings.REDIS_AUTO_SUBMIT_KEY,
                0,
                now
            )
            logger.debug(f"Found {len(due_attempts)} due auto submits")
            return due_attempts
        except Exception as e:
            logger.error(f"Error getting due auto submits: {str(e)}")
            return []

    def clear_auto_submit(self, attempt_id):
        """Clear auto-submission schedule for attempt."""
        if not self._check_redis():
            return False
            
        try:
            result = self.redis.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
            logger.debug(f"Cleared auto-submit for {attempt_id}: {result}")
            return result > 0
        except Exception as e:
            logger.error(f"Error clearing auto submit for {attempt_id}: {str(e)}")
            return False

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def get_first_attempts(self):
        """Get all first attempts from Redis."""
        if not self._check_redis():
            return []
            
        try:
            pattern = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}*"
            keys = self.redis.keys(pattern)
            attempts = []
            
            for key in keys:
                try:
                    data = self.redis.hgetall(key)
                    if data.get('is_first_attempt') == 'True':
                        attempts.append({
                            'attempt_id': key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, ''),
                            'data': data
                        })
                except Exception as e:
                    logger.warning(f"Error processing key {key}: {str(e)}")
                    continue
            
            logger.debug(f"Found {len(attempts)} first attempts in Redis")
            return attempts
        except Exception as e:
            logger.error(f"Error getting first attempts: {str(e)}")
            return []

    def cleanup_old_attempts(self, max_age_hours=24):
        """Clean up old exam attempts to free Redis memory."""
        if not self._check_redis():
            return 0
            
        try:
            pattern = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}*"
            keys = self.redis.keys(pattern)
            deleted_count = 0
            current_time = time.time()
            
            for key in keys:
                try:
                    data = self.redis.hgetall(key)
                    if 'start_time' in data:
                        start_time = float(data['start_time'])
                        age_hours = (current_time - start_time) / 3600
                        
                        if age_hours > max_age_hours:
                            # Also remove from auto-submit queue
                            attempt_id = key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, '')
                            self.redis.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
                            
                            # Delete the attempt
                            self.redis.delete(key)
                            deleted_count += 1
                            logger.debug(f"Cleaned up old attempt: {attempt_id} ({age_hours:.1f} hours old)")
                except Exception as e:
                    logger.warning(f"Error processing cleanup for key {key}: {str(e)}")
                    continue
            
            if deleted_count > 0:
                logger.info(f"🧹 Redis cleanup completed: deleted {deleted_count} old attempts")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Redis cleanup error: {str(e)}")
            return 0

    def get_memory_info(self):
        """Get Redis memory usage information."""
        if not self._check_redis():
            return {"error": "Redis not available", "status": "disabled"}
            
        try:
            info = self.redis.info('memory')
            memory_used = info.get('used_memory', 0)
            memory_max = info.get('maxmemory', 0)
            
            return {
                'status': 'connected',
                'used_memory': memory_used,
                'used_memory_human': info.get('used_memory_human', '0B'),
                'maxmemory': memory_max,
                'maxmemory_human': info.get('maxmemory_human', '0B'),
                'memory_usage_percent': (memory_used / max(memory_max, 1)) * 100 if memory_max > 0 else 0,
                'keys_count': self.redis.dbsize(),
                'connected_clients': info.get('connected_clients', 0),
            }
        except Exception as e:
            logger.error(f"Error getting Redis memory info: {str(e)}")
            return {"error": str(e), "status": "error"}

    def health_check(self):
        """Check Redis health status."""
        if not self._check_redis():
            return {
                'status': 'disabled' if settings.DEBUG else 'error',
                'message': 'Redis not available' if not settings.DEBUG else 'Redis disabled in development'
            }
            
        try:
            # Simple ping test
            self.redis.ping()
            
            # Get basic info
            info = self.redis.info()
            
            return {
                'status': 'healthy',
                'version': info.get('redis_version', 'unknown'),
                'uptime_days': info.get('uptime_in_days', 0),
                'connected_clients': info.get('connected_clients', 0),
                'memory_used': info.get('used_memory_human', '0B'),
                'keys_count': self.redis.dbsize(),
            }
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': time.time()
            }

    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================

    def _check_redis(self):
        """Check if Redis is available."""
        if self.redis is None:
            if settings.DEBUG:
                logger.debug("Redis not available (development mode)")
                return False
            else:
                logger.error("Redis not available in production!")
                return False
        return True

    def _safe_execute(self, func, *args, **kwargs):
        """Safely execute a Redis command with error handling."""
        if not self._check_redis():
            return None
            
        try:
            return func(*args, **kwargs)
        except redis.RedisError as e:
            logger.error(f"Redis error in {func.__name__}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            return None


# Global Redis service instance
redis_service = RedisService()