import redis
import time
import logging
import os
from django.conf import settings

# Set up logging
logger = logging.getLogger(__name__)

class RedisService:
    def __init__(self):
        try:
            # Use Railway's REDIS_URL environment variable
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
            
            # Parse URL for additional options
            if redis_url.startswith('rediss://'):  # SSL connection (Railway Production)
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                    ssl_cert_reqs=None,  # Accept Railway's SSL certificate
                    retry_on_timeout=True,
                    max_connections=10
                )
            else:
                # Local development or non-SSL
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=10,
                    socket_keepalive=True,
                    retry_on_timeout=True,
                    max_connections=10
                )
            
            # Test connection
            self.redis.ping()
            logger.info(f"✅ Redis connected successfully to {redis_url}")
            
        except redis.ConnectionError as e:
            logger.error(f"❌ Redis connection failed: {str(e)}")
            if not settings.DEBUG:
                raise e
            # For development only, create a dummy client
            self.redis = None
            logger.warning("⚠️ Using null Redis client (development mode only)")
        except Exception as e:
            logger.error(f"❌ Unexpected Redis error: {str(e)}")
            raise e
    
    # Attempt Tracking
    def cache_attempt_state(self, attempt_id, data, ttl=None):
        if not self.redis:
            logger.warning("Redis not available, skipping cache")
            return
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            self.redis.hset(key, mapping=data)
            if ttl:
                self.redis.expire(key, ttl)
            logger.debug(f"Cached attempt state for {attempt_id}, TTL: {ttl}s")
        except Exception as e:
            logger.error(f"Error caching attempt state: {str(e)}")

    def get_attempt_state(self, attempt_id):
        if not self.redis:
            logger.warning("Redis not available, returning empty state")
            return {}
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            return self.redis.hgetall(key)
        except Exception as e:
            logger.error(f"Error getting attempt state: {str(e)}")
            return {}
    
    def delete_attempt_state(self, attempt_id):
        if not self.redis:
            logger.warning("Redis not available, skipping delete")
            return
            
        try:
            key = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{attempt_id}"
            result = self.redis.delete(key)
            logger.debug(f"Deleted attempt state for {attempt_id}: {result} keys removed")
        except Exception as e:
            logger.error(f"Error deleting attempt state: {str(e)}")
    
    # Grading Queue
    def add_to_grading_queue(self, attempt_id):
        if not self.redis:
            logger.warning("Redis not available, skipping grading queue")
            return
            
        try:
            self.redis.lpush(settings.REDIS_GRADING_QUEUE_KEY, attempt_id)
            logger.debug(f"Added attempt {attempt_id} to grading queue")
        except Exception as e:
            logger.error(f"Error adding to grading queue: {str(e)}")
    
    def get_next_grading_task(self):
        if not self.redis:
            logger.warning("Redis not available, no grading tasks")
            return None
            
        try:
            task = self.redis.rpop(settings.REDIS_GRADING_QUEUE_KEY)
            if task:
                logger.debug(f"Retrieved grading task: {task}")
            return task
        except Exception as e:
            logger.error(f"Error getting next grading task: {str(e)}")
            return None
    
    # Auto-submission
    def schedule_auto_submit(self, attempt_id, exam_duration_minutes):
        if not self.redis:
            logger.warning("Redis not available, skipping auto-submit schedule")
            return
            
        try:
            delay_seconds = exam_duration_minutes * 60
            score = time.time() + delay_seconds
            result = self.redis.zadd(
                settings.REDIS_AUTO_SUBMIT_KEY,
                {attempt_id: score}
            )
            logger.debug(f"Scheduled auto-submit for {attempt_id} in {delay_seconds}s")
            return result
        except Exception as e:
            logger.error(f"Error scheduling auto-submit: {str(e)}")
            return 0
    
    def get_due_auto_submits(self):
        if not self.redis:
            logger.warning("Redis not available, no due auto submits")
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
        if not self.redis:
            logger.warning("Redis not available, skipping auto-submit clear")
            return
            
        try:
            result = self.redis.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
            logger.debug(f"Cleared auto-submit for {attempt_id}: {result}")
            return result
        except Exception as e:
            logger.error(f"Error clearing auto submit: {str(e)}")
            return 0
            
    def get_first_attempts(self):
        if not self.redis:
            logger.warning("Redis not available, no first attempts")
            return []
            
        try:
            pattern = f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}*"
            keys = self.redis.keys(pattern)
            attempts = []
            
            for key in keys:
                data = self.redis.hgetall(key)
                if data.get('is_first_attempt') == 'True':
                    attempts.append({
                        'attempt_id': key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, ''),
                        'data': data
                    })
            
            logger.debug(f"Found {len(attempts)} first attempts in Redis")
            return attempts
        except Exception as e:
            logger.error(f"Error getting first attempts: {str(e)}")
            return []
    
    # Memory management for free tier
    def cleanup_old_attempts(self, max_age_hours=24):
        """Clean up old exam attempts to free Redis memory (for free tier)"""
        if not self.redis:
            logger.warning("Redis not available, skipping cleanup")
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
                            # Also remove from auto-submit queue if exists
                            attempt_id = key.replace(settings.REDIS_EXAM_ATTEMPTS_PREFIX, '')
                            self.redis.zrem(settings.REDIS_AUTO_SUBMIT_KEY, attempt_id)
                            
                            # Delete the attempt
                            self.redis.delete(key)
                            deleted_count += 1
                            logger.debug(f"Cleaned up old attempt: {attempt_id} ({age_hours:.1f} hours old)")
                except Exception as e:
                    logger.warning(f"Error processing key {key}: {str(e)}")
                    continue
            
            logger.info(f"✅ Redis cleanup completed: deleted {deleted_count} old attempts")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Redis cleanup error: {str(e)}")
            return 0
    
    def get_memory_info(self):
        """Get Redis memory usage info (for monitoring)"""
        if not self.redis:
            return {"error": "Redis not available"}
            
        try:
            info = self.redis.info('memory')
            return {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'maxmemory': info.get('maxmemory', 0),
                'maxmemory_human': info.get('maxmemory_human', '0B'),
                'memory_usage_percent': (info.get('used_memory', 0) / max(info.get('maxmemory', 1), 1)) * 100
            }
        except Exception as e:
            logger.error(f"Error getting Redis memory info: {str(e)}")
            return {"error": str(e)}

# Global instance
redis_service = RedisService()