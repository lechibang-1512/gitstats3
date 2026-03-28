"""
API module for Gitstats3.
Provides a FastAPI server to run and serve git repository statistics.
"""

import os
import sys
import shutil
import tempfile
import threading
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from .gitstats_cli import GitStats
from .gitstats_config import conf

app = FastAPI(
    title="Gitstats3 API",
    description="API for generating and serving Git repository statistics",
    version="3.0.0"
)

# In-memory task tracking
tasks = {}

class AnalysisRequest(BaseModel):
    path: str
    output_dir: Optional[str] = None
    options: Optional[Dict[str, str]] = None

class AnalysisStatus(BaseModel):
    task_id: str
    status: str
    repo_path: str
    output_path: Optional[str] = None
    error: Optional[str] = None

def run_analysis_task(task_id: str, repo_path: str, output_path: str, options: Dict):
    """Background task to run gitstats analysis."""
    try:
        tasks[task_id]["status"] = "processing"
        
        # Apply options to global config if provided
        if options:
            for k, v in options.items():
                if k in conf:
                    # Basic type conversion
                    if isinstance(conf[k], bool):
                        conf[k] = str(v).lower() in ('true', '1', 'yes')
                    elif isinstance(conf[k], int):
                        conf[k] = int(v)
                    else:
                        conf[k] = v
        
        # Run GitStats
        gs = GitStats()
        # Ensure we pass the arguments as a list of strings
        gs.run([repo_path, output_path])
        
        tasks[task_id]["status"] = "completed"
    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)
        import traceback
        traceback.print_exc()

@app.get("/")
async def root():
    return {
        "message": "Gitstats3 API is running",
        "endpoints": {
            "POST /analyze": "Trigger analysis for a repository",
            "GET /status/{task_id}": "Check status of an analysis task",
            "GET /reports/{repo_name}": "View generated report",
            "GET /docs": "API documentation"
        }
    }

@app.post("/analyze", response_model=AnalysisStatus)
async def analyze(request: AnalysisRequest, background_tasks: BackgroundTasks):
    repo_path = os.path.abspath(request.path)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail=f"Repository path not found: {repo_path}")
    
    repo_name = os.path.basename(repo_path)
    task_id = f"{repo_name}_{threading.get_ident()}_{len(tasks)}"
    
    # Determine output directory
    if request.output_dir:
        output_path = os.path.abspath(request.output_dir)
    else:
        # Default to a subfolder in the current working directory or system temp
        output_path = os.path.join(os.getcwd(), "reports", f"{repo_name}_report")
    
    os.makedirs(output_path, exist_ok=True)
    
    tasks[task_id] = {
        "task_id": task_id,
        "status": "queued",
        "repo_path": repo_path,
        "output_path": output_path
    }
    
    background_tasks.add_task(run_analysis_task, task_id, repo_path, output_path, request.options or {})
    
    return tasks[task_id]

@app.get("/status/{task_id}", response_model=AnalysisStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/reports/{repo_name}")
async def get_report(repo_name: str):
    # Try to find the report in the standard location
    report_path = os.path.join(os.getcwd(), "reports", f"{repo_name}_report", "index.html")
    
    # Check if we generated it with a nested _report structure (depends on how gitstats CLI behaves)
    nested_path = os.path.join(os.getcwd(), "reports", f"{repo_name}_report", f"{repo_name}_report", "index.html")
    if os.path.exists(nested_path):
        report_path = nested_path

    # Also check if it was a task output
    for task in tasks.values():
        if os.path.basename(task["repo_path"]) == repo_name and task["status"] == "completed":
            task_path = os.path.join(task["output_path"], "index.html")
            task_nested_path = os.path.join(task["output_path"], f"{repo_name}_report", "index.html")
            if os.path.exists(task_nested_path):
                report_path = task_nested_path
            elif os.path.exists(task_path):
                report_path = task_path
            break
            
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail=f"Report not found for {repo_name} at {report_path}. Have you run /analyze?")
        
    return FileResponse(report_path)

def start_api(host: str = "0.0.0.0", port: int = 8080):
    import uvicorn
    print(f"Starting Gitstats3 API on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
