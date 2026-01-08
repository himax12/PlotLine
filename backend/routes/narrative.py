import uuid
import asyncio
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.models.schemas import StoryState
from backend.graph.workflow import app_graph

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Async Job Store (Simple In-Memory for Phase 1) ---
# In Phase 3, move this to specific persistence if needed.
# LangGraph's checkpointer handles the *graph state*, but we need to track *job status* (running/done).
JOBS: Dict[str, Dict[str, Any]] = {}

class GenerationRequest(BaseModel):
    input_text: str
    target_genre: str = "General Fiction"
    target_audience: str = "General"
    tone: str = "Neutral"
    words_per_scene: int = 200  # Default 200 words per scene
    safety_level: str = "none"  # Default to no filtering

class JobStatusResponse(BaseModel):
    task_id: str
    status: str # "queued", "processing", "completed", "failed"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- Background Worker ---

async def run_generation_workflow(task_id: str, request: GenerationRequest):
    """
    Executes the LangGraph workflow in the background.
    """
    from backend.utils.event_emitter import event_emitter
    
    # Create event queue for SSE streaming
    event_emitter.create_queue(task_id)
    
    print(f"\n{'='*60}")
    print(f"🚀 BACKGROUND TASK STARTED: {task_id}")
    print(f"{'='*60}")
    print(f"📝 Input Text: {request.input_text[:50]}...")
    print(f"🎭 Genre: {request.target_genre}")
    print(f"👥 Audience: {request.target_audience}")
    print(f"🎨 Tone: {request.tone}")
    print(f"📏 Words/Scene: {request.words_per_scene}")
    print(f"🛡️ Safety Level: {request.safety_level}")
    print(f"{'='*60}\n")
    
    # Emit workflow start event
    await event_emitter.emit(task_id, "workflow_start", {
        "input_text": request.input_text[:100],
        "genre": request.target_genre,
        "words_per_scene": request.words_per_scene,
        "safety_level": request.safety_level
    })
    
    try:
        logger.info(f"Task {task_id}: Starting generation for input '{request.input_text[:20]}...'")
        JOBS[task_id]["status"] = "processing"
        print(f"✅ Job status set to: processing")
        
        # Initialize Context
        print(f"\n🏗️ Building initial state...")
        initial_state = {
            "story_state": StoryState(
                input_text=request.input_text,
                target_genre=request.target_genre,
                target_audience=request.target_audience,
                tone=request.tone,
                words_per_scene=request.words_per_scene,
                safety_level=request.safety_level
            ),
            "current_node_index": 0,
            "task_id": task_id  # NEW: Pass task_id for event emission
        }
        print(f"✅ Initial state created")
        print(f"   - words_per_scene: {initial_state['story_state'].words_per_scene}")
        print(f"   - safety_level: {initial_state['story_state'].safety_level}")
        
        # Run Graph
        # We use aconfig with thread_id for persistence
        config = {"configurable": {"thread_id": task_id}}
        
        # Invoke (this runs until the end or interrupt)
        print(f"\n🔄 Invoking LangGraph workflow...")
        print(f"   Thread ID: {task_id}")
        logger.info(f"Task {task_id}: Invoking LangGraph workflow...")
        final_state = await app_graph.ainvoke(initial_state, config=config)
        print(f"\n✅ Workflow finished!")
        logger.info(f"Task {task_id}: Workflow completed successfully.")
        
        # Update Job
        print(f"\n📦 Packaging results...")
        JOBS[task_id]["status"] = "completed"
        # We return the "rendered_chunks" as the main result for now
        # But we pass the whole story_state usually
        story = final_state["story_state"]
        
        # Construct a simple result format
        full_story = "\n\n".join(story.rendered_chunks.values())
        print(f"   - Generated {len(story.graph.nodes)} scenes")
        print(f"   - Total prose length: {len(full_story)} chars")
        print(f"   - Words/scene config was: {story.words_per_scene}")
        print(f"   - Safety level was: {story.safety_level}")
        
        JOBS[task_id]["result"] = {
            "story_text": full_story, 
            "graph_nodes": len(story.graph.nodes),
            "chunks": story.rendered_chunks
        }
        
        # Emit workflow complete event
        await event_emitter.emit(task_id, "workflow_complete", {
            "total_nodes": len(story.graph.nodes),
            "total_chunks": len(story.rendered_chunks),
            "total_words": len(full_story.split())
        })
        print(f"\n{'='*60

}")
        print(f"✅ TASK COMPLETED: {task_id}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR in task {task_id}: {str(e)}")
        print(f"{'='*60}\n")
        print(f"!!! TASK FAILED: {task_id} !!!")
        print(f"Error: {e}")
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Task {task_id} FAILED: {str(e)}\n{error_trace}")
        JOBS[task_id]["status"] = "failed"
        JOBS[task_id]["error"] = str(e)
        
        # Emit error event
        await event_emitter.emit(task_id, "error", {
            "message": str(e),
            "traceback": error_trace
        })
    
    finally:
        # Always cleanup event queue
        event_emitter.cleanup(task_id)

# --- Endpoints ---

@router.post("/generate", response_model=JobStatusResponse, status_code=202)
async def start_generation(req: GenerationRequest, background_tasks: BackgroundTasks):
    """
    Starts an async story generation task. Returns immediately with task_id.
    """
    task_id = str(uuid.uuid4())
    JOBS[task_id] = {"status": "queued", "task_id": task_id}
    
    logger.info(f"Received generation request. Task ID: {task_id}")

    # Schedule background execution
    background_tasks.add_task(run_generation_workflow, task_id, req)
    
    return JobStatusResponse(task_id=task_id, status="queued")

@router.get("/status/{task_id}", response_model=JobStatusResponse)
async def get_generation_status(task_id: str):
    """
    Check the status of an async generation task.
    """
    job = JOBS.get(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return JobStatusResponse(
        task_id=task_id,
        status=job["status"],
        result=job.get("result"),
        error=job.get("error")
    )

@router.get("/stream/{task_id}")
async def stream_thinking(task_id: str):
    """
    Stream real-time thinking process via Server-Sent Events (SSE)
    """
    from fastapi.responses import StreamingResponse
    from backend.utils.event_emitter import event_emitter
    import json
    import asyncio
    
    async def event_generator():
        """Generate SSE events from the task's queue"""
        print(f"\n🌊 SSE Stream opened for task: {task_id}")
        
        queue = event_emitter.get_queue(task_id)
        if not queue:
            # Task not found or already completed
            error_event = {
                "type": "error",
                "data": {"message": "Task not found or already completed"},
                "timestamp": datetime.now().isoformat() 
            }
            yield f"data: {json.dumps(error_event)}\n\n"
            return
        
        try:
            while True:
                # Wait for event with 30s timeout (keeps connection alive)
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    # Send event in SSE format: "data: {json}\n\n"
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    print(f"📡 Streamed: {event['type']}")
                    
                    # If workflow complete, close stream
                    if event['type'] in ['workflow_complete', 'error']:
                        print(f"🏁 Closing stream for task: {task_id}")
                        break
                        
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat = {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                    
        except asyncio.CancelledError:
            print(f"❌ SSE Stream cancelled for task: {task_id}")
        except Exception as e:
            print(f"❌ SSE Stream error: {e}")
            error_event = {"type": "error", "data": {"message": str(e)}}
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )

@router.get("/state/{task_id}")
async def get_state(task_id: str):
    """
    Getting raw implementation state (for debugging).
    Uses LangGraph checkpoint access.
    """
    config = {"configurable": {"thread_id": task_id}}
    state = await app_graph.aget_state(config)
    if not state:
        raise HTTPException(status_code=404, detail="State not found")
    return state.values

# --- Phase 2: Intelligence Endpoints ---

@router.get("/mapping/{task_id}")
async def get_analogical_mapping(task_id: str):
    """
    Get the analogical mapping (4-layer decomposition) for a generated story.
    Returns entity archetypes, action patterns, structure type, and emotional arc.
    """
    if task_id not in JOBS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    config = {"configurable": {"thread_id": task_id}}
    state = await app_graph.aget_state(config)
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="State not found")
    
    story_state = state.values.get("story_state")
    if not story_state or not story_state.analogical_mapping:
        raise HTTPException(status_code=404, detail="Analogical mapping not yet generated")
    
    return story_state.analogical_mapping

@router.get("/validation/{task_id}")
async def get_validation_results(task_id: str):
    """
    Get validation results (symbolic + commonsense) for a generated story.
    Returns list of validation results with violations and suggestions.
    """
    if task_id not in JOBS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    config = {"configurable": {"thread_id": task_id}}
    state = await app_graph.aget_state(config)
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="State not found")
    
    story_state = state.values.get("story_state")
    if not story_state:
        raise HTTPException(status_code=404, detail="Story state not found")
    
    return {
        "validation_results": story_state.validation_results,
        "overall_valid": all(r.is_valid for r in story_state.validation_results) if story_state.validation_results else True
    }
