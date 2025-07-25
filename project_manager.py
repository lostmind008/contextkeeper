#!/usr/bin/env python3
"""
Project Manager for Multi-Project RAG Agent
Handles project lifecycle, configuration, and metadata management
"""

import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class ProjectStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    
@dataclass
class Decision:
    """Represents an architectural decision"""
    id: str
    decision: str
    reasoning: str
    timestamp: str
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass 
class Objective:
    """Represents a project objective/goal"""
    id: str
    title: str
    description: str
    created_at: str
    completed_at: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed
    priority: str = "medium"  # low, medium, high

@dataclass
class ProjectConfig:
    """Configuration for a single project"""
    project_id: str
    name: str
    root_path: str
    watch_dirs: List[str]
    status: ProjectStatus
    created_at: str
    last_active: str
    description: str = ""
    file_extensions: List[str] = None
    decisions: List[Decision] = None
    objectives: List[Objective] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.file_extensions is None:
            self.file_extensions = [".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".json", ".yaml"]
        if self.decisions is None:
            self.decisions = []
        if self.objectives is None:
            self.objectives = []
        if self.metadata is None:
            self.metadata = {}
            
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['status'] = self.status.value
        data['decisions'] = [asdict(d) for d in self.decisions]
        data['objectives'] = [asdict(o) for o in self.objectives]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectConfig':
        """Create from dictionary"""
        data = data.copy()
        data['status'] = ProjectStatus(data['status'])
        data['decisions'] = [Decision(**d) for d in data.get('decisions', [])]
        data['objectives'] = [Objective(**o) for o in data.get('objectives', [])]
        return cls(**data)

class ProjectManager:
    """Manages multiple project configurations and lifecycles"""
    
    def __init__(self, config_dir: str = None):
        """Initialize project manager
        
        Args:
            config_dir: Directory to store project configurations
        """
        self.config_dir = Path(config_dir or os.path.expanduser("~/.rag_projects"))
        self.config_dir.mkdir(exist_ok=True)
        self.projects: Dict[str, ProjectConfig] = {}
        self.focused_project_id: Optional[str] = None
        self.load_all_projects()
        
    def load_all_projects(self):
        """Load all project configurations from disk"""
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    project = ProjectConfig.from_dict(data)
                    self.projects[project.project_id] = project
                    logger.info(f"Loaded project: {project.name} ({project.project_id})")
            except Exception as e:
                logger.error(f"Error loading project config {config_file}: {e}")
                
        # Set focused project if none set
        if not self.focused_project_id and self.projects:
            active_projects = [p for p in self.projects.values() if p.status == ProjectStatus.ACTIVE]
            if active_projects:
                self.focused_project_id = active_projects[0].project_id
                
    def save_project(self, project: ProjectConfig):
        """Save project configuration to disk"""
        config_file = self.config_dir / f"{project.project_id}.json"
        with open(config_file, 'w') as f:
            json.dump(project.to_dict(), f, indent=2)
        logger.info(f"Saved project config: {project.name}")
        
    def create_project(self, name: str, root_path: str, watch_dirs: List[str] = None,
                      description: str = "") -> ProjectConfig:
        """Create a new project
        
        Args:
            name: Project name
            root_path: Root directory of the project
            watch_dirs: Directories to watch (defaults to root_path)
            description: Project description
            
        Returns:
            Created project configuration
        """
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        
        # Default watch dirs to root path if not specified
        if watch_dirs is None:
            watch_dirs = [root_path]
            
        # Ensure absolute paths
        root_path = os.path.abspath(root_path)
        watch_dirs = [os.path.abspath(d) for d in watch_dirs]
        
        project = ProjectConfig(
            project_id=project_id,
            name=name,
            root_path=root_path,
            watch_dirs=watch_dirs,
            status=ProjectStatus.ACTIVE,
            created_at=datetime.now().isoformat(),
            last_active=datetime.now().isoformat(),
            description=description
        )
        
        self.projects[project_id] = project
        self.save_project(project)
        
        # Set as focused if it's the first project
        if len(self.projects) == 1:
            self.focused_project_id = project_id
            
        logger.info(f"Created project: {name} ({project_id})")
        return project
        
    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """Get project by ID"""
        return self.projects.get(project_id)
        
    def get_focused_project(self) -> Optional[ProjectConfig]:
        """Get the currently focused project"""
        if self.focused_project_id:
            return self.projects.get(self.focused_project_id)
        return None
        
    def set_focus(self, project_id: str) -> bool:
        """Set the focused project"""
        if project_id in self.projects:
            self.focused_project_id = project_id
            project = self.projects[project_id]
            project.last_active = datetime.now().isoformat()
            self.save_project(project)
            logger.info(f"Focused on project: {project.name}")
            return True
        return False
        
    def update_status(self, project_id: str, status: ProjectStatus) -> bool:
        """Update project status"""
        if project_id in self.projects:
            project = self.projects[project_id]
            project.status = status
            project.last_active = datetime.now().isoformat()
            self.save_project(project)
            logger.info(f"Updated project {project.name} status to: {status.value}")
            return True
        return False
        
    def pause_project(self, project_id: str) -> bool:
        """Pause a project"""
        return self.update_status(project_id, ProjectStatus.PAUSED)
        
    def resume_project(self, project_id: str) -> bool:
        """Resume a paused project"""
        return self.update_status(project_id, ProjectStatus.ACTIVE)
        
    def archive_project(self, project_id: str) -> bool:
        """Archive a project"""
        return self.update_status(project_id, ProjectStatus.ARCHIVED)
        
    def add_decision(self, project_id: str, decision: str, reasoning: str, 
                    tags: List[str] = None) -> Optional[Decision]:
        """Add a decision to a project"""
        if project_id not in self.projects:
            return None
            
        project = self.projects[project_id]
        decision_obj = Decision(
            id=f"dec_{uuid.uuid4().hex[:8]}",
            decision=decision,
            reasoning=reasoning,
            timestamp=datetime.now().isoformat(),
            tags=tags or []
        )
        
        project.decisions.append(decision_obj)
        project.last_active = datetime.now().isoformat()
        self.save_project(project)
        
        logger.info(f"Added decision to project {project.name}: {decision}")
        return decision_obj
        
    def add_objective(self, project_id: str, title: str, description: str = "",
                     priority: str = "medium") -> Optional[Objective]:
        """Add an objective to a project"""
        if project_id not in self.projects:
            return None
            
        project = self.projects[project_id]
        objective = Objective(
            id=f"obj_{uuid.uuid4().hex[:8]}",
            title=title,
            description=description,
            created_at=datetime.now().isoformat(),
            priority=priority
        )
        
        project.objectives.append(objective)
        project.last_active = datetime.now().isoformat()
        self.save_project(project)
        
        logger.info(f"Added objective to project {project.name}: {title}")
        return objective
        
    def complete_objective(self, project_id: str, objective_id: str) -> bool:
        """Mark an objective as completed"""
        if project_id not in self.projects:
            return False
            
        project = self.projects[project_id]
        for obj in project.objectives:
            if obj.id == objective_id:
                obj.status = "completed"
                obj.completed_at = datetime.now().isoformat()
                project.last_active = datetime.now().isoformat()
                self.save_project(project)
                logger.info(f"Completed objective in project {project.name}: {obj.title}")
                return True
        return False
        
    def get_active_projects(self) -> List[ProjectConfig]:
        """Get all active projects"""
        return [p for p in self.projects.values() if p.status == ProjectStatus.ACTIVE]
        
    def get_all_watch_dirs(self) -> List[str]:
        """Get all watch directories from active projects"""
        watch_dirs = []
        for project in self.get_active_projects():
            watch_dirs.extend(project.watch_dirs)
        return list(set(watch_dirs))  # Remove duplicates
        
    def export_context(self, project_id: str) -> Dict[str, Any]:
        """Export project context for AI agents"""
        if project_id not in self.projects:
            return {}
            
        project = self.projects[project_id]
        
        # Get recent decisions and pending objectives
        recent_decisions = sorted(project.decisions, 
                                key=lambda d: d.timestamp, 
                                reverse=True)[:10]
        pending_objectives = [o for o in project.objectives if o.status != "completed"]
        
        context = {
            "project": {
                "id": project.project_id,
                "name": project.name,
                "description": project.description,
                "root_path": project.root_path,
                "status": project.status.value,
                "last_active": project.last_active
            },
            "recent_decisions": [
                {
                    "decision": d.decision,
                    "reasoning": d.reasoning,
                    "timestamp": d.timestamp,
                    "tags": d.tags
                } for d in recent_decisions
            ],
            "pending_objectives": [
                {
                    "title": o.title,
                    "description": o.description,
                    "priority": o.priority,
                    "created_at": o.created_at
                } for o in pending_objectives
            ],
            "statistics": {
                "total_decisions": len(project.decisions),
                "total_objectives": len(project.objectives),
                "completed_objectives": len([o for o in project.objectives if o.status == "completed"]),
                "watch_directories": len(project.watch_dirs)
            }
        }
        
        return context
        
    def get_project_summary(self) -> Dict[str, Any]:
        """Get summary of all projects"""
        summary = {
            "total_projects": len(self.projects),
            "active_projects": len([p for p in self.projects.values() if p.status == ProjectStatus.ACTIVE]),
            "paused_projects": len([p for p in self.projects.values() if p.status == ProjectStatus.PAUSED]),
            "archived_projects": len([p for p in self.projects.values() if p.status == ProjectStatus.ARCHIVED]),
            "focused_project": self.focused_project_id,
            "projects": []
        }
        
        for project in self.projects.values():
            summary["projects"].append({
                "id": project.project_id,
                "name": project.name,
                "status": project.status.value,
                "last_active": project.last_active,
                "objectives_pending": len([o for o in project.objectives if o.status != "completed"]),
                "total_decisions": len(project.decisions)
            })
            
        return summary