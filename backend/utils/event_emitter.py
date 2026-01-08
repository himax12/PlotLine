"""
Event Emitter for streaming real-time thinking process to frontend
Uses asyncio.Queue for thread-safe event passing
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import json

class EventEmitter:
    """Singleton event emitter for streaming thinking process via SSE"""
    
    _instance = None
    _queues: Dict[str, asyncio.Queue] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def create_queue(self, task_id: str) -> asyncio.Queue:
        """Create event queue for a task"""
        print(f"📡 Creating event queue for task: {task_id}")
        queue = asyncio.Queue()
        self._queues[task_id] = queue
        return queue
    
    def get_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        """Get queue for task"""
        return self._queues.get(task_id)
    
    async def emit(self, task_id: str, event_type: str, data: Dict[str, Any]):
        """Emit event to task's queue"""
        queue = self._queues.get(task_id)
        if queue:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            print(f"📤 Emitting event: {event_type} for task {task_id}")
            await queue.put(event)
        else:
            print(f"⚠️ No queue found for task {task_id}")
    
    def cleanup(self, task_id: str):
        """Remove queue after task completes"""
        if task_id in self._queues:
            print(f"🧹 Cleaning up event queue for task: {task_id}")
            del self._queues[task_id]

# Global singleton instance
event_emitter = EventEmitter()
