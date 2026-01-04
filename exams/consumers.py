import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .services.redis_service import redis_service

class ExamAttemptConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.attempt_id = self.scope['url_route']['kwargs']['attempt_id']
        await self.channel_layer.group_add(
            f"attempt_{self.attempt_id}",
            self.channel_name
        )
        await self.accept()
        
        # Send initial state from Redis
        attempt_state = redis_service.get_attempt_state(self.attempt_id)
        await self.send(text_data=json.dumps({
            'type': 'initial_state',
            'browser_leaves': int(attempt_state.get('browser_leaves', 0)),
            'time_remaining': calculate_time_remaining(attempt_state)
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            f"attempt_{self.attempt_id}",
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data['type'] == 'browser_leave':
            # Update leave count in Redis
            redis_service.redis.hincrby(
                f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{self.attempt_id}",
                'browser_leaves',
                1
            )
            
            # Check if should auto-submit
            leaves = int(redis_service.redis.hget(
                f"{settings.REDIS_EXAM_ATTEMPTS_PREFIX}{self.attempt_id}",
                'browser_leaves'
            ))
            if leaves >= 3:
                await self.channel_layer.group_send(
                    f"attempt_{self.attempt_id}",
                    {
                        'type': 'auto_submit',
                        'reason': 'excessive_browser_leaves'
                    }
                )