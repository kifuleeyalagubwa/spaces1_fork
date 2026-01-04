from channels.generic.websocket import AsyncWebsocketConsumer

class SignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data="WebSocket connected")
    
    async def receive(self, text_data):
        # For future signaling if needed
        pass