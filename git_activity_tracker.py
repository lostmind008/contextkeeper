#!/usr/bin/env python3
"""
git_activity_tracker.py - Git-based activity tracking for ContextKeeper v3.0

Created: 2025-07-24 03:41:27 (Australia/Sydney)
Part of: ContextKeeper v3.0 Sacred Layer Upgrade

Purpose:
Replaces file-watching with more reliable Git-based tracking. Captures actual
commits, analyzes development patterns, and integrates with the RAG agent.

Key Features:
- Track git commits and changes
- Analyze development activity patterns
- Integrate with project knowledge base
- Support multi-project Git tracking

Dependencies:
- GitPython for repository interaction
- Integration with ProjectKnowledgeAgent
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import git

logger = logging.getLogger(__name__)


@dataclass
class GitActivity:
    """Represents git activity analysis results"""
    project_id: str
    commits_count: int
    files_changed: Set[str]
    active_branches: List[str]
    recent_commits: List[Dict]
    activity_summary: str


class GitActivityTracker:
    """
    Tracks Git repository activity for a specific project.
    
    This class monitors git commits, branches, and file changes to provide
    insights into development activity without relying on file system watching.
    """
    
    def __init__(self, project_path: str, project_id: str):
        """
        Initialize Git activity tracker for a project.
        
        Args:
            project_path: Path to the Git repository
            project_id: Unique identifier for the project
        """
        self.project_path = Path(project_path)
        self.project_id = project_id
        self.repo = None
        
        # Initialize Git repository connection
        try:
            # Look for .git directory in project path or parent directories
            git_repo_path = self._find_git_repo(self.project_path)
            if git_repo_path:
                self.repo = git.Repo(git_repo_path)
                logger.info(f"Git repository found for project {project_id}: {git_repo_path}")
            else:
                logger.warning(f"No Git repository found for project {project_id} at {project_path}")
        except Exception as e:
            logger.error(f"Failed to initialize Git repository for {project_id}: {e}")
            self.repo = None
        
    def _find_git_repo(self, path: Path) -> Optional[str]:
        """
        Find the Git repository root by looking for .git directory.
        
        Args:
            path: Starting path to search from
            
        Returns:
            Path to Git repository root or None if not found
        """
        current = path.resolve()
        for parent in [current] + list(current.parents):
            if (parent / ".git").exists():
                return str(parent)
        return None
    
    def analyze_activity(self, hours: int = 24) -> GitActivity:
        """
        Analyze Git activity for the specified time period.
        
        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            GitActivity object with analysis results
        """
        if not self.repo:
            return GitActivity(
                project_id=self.project_id,
                commits_count=0,
                files_changed=set(),
                active_branches=[],
                recent_commits=[],
                activity_summary="No Git repository available"
            )
        
        try:
            # Calculate time threshold
            since_time = datetime.now() - timedelta(hours=hours)

            # Get commits from the specified time period
            recent_commits = []
            files_changed = set()

            # basically, we need to iterate through commits since the time threshold
            for commit in self.repo.iter_commits(since=since_time.strftime('%Y-%m-%d %H:%M:%S')):
                commit_info = {
                    'hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': str(commit.author),
                    'date': commit.committed_datetime.isoformat(),
                    'files_changed': len(commit.stats.files)
                }
                recent_commits.append(commit_info)
                
                # Add changed files to our set
                files_changed.update(commit.stats.files.keys())

            # Get active branches (those with recent activity)
            active_branches = []
            try:
                for branch in self.repo.branches:
                    try:
                        # Check if branch has commits in the time period
                        branch_commits = list(self.repo.iter_commits(
                            branch,
                            since=since_time.strftime('%Y-%m-%d %H:%M:%S'),
                            max_count=1
                        ))
                        if branch_commits:
                            active_branches.append(branch.name)
                    except:
                        # Skip branches that can't be accessed
                        continue
            except:
                # If we can't access branches, just use current branch
                try:
                    if self.repo.active_branch:
                        active_branches = [self.repo.active_branch.name]
                except:
                    active_branches = ["unknown"]

            # Generate activity summary
            if recent_commits:
                activity_summary = f"{len(recent_commits)} commits, {len(files_changed)} files changed, active on {len(active_branches)} branches"
            else:
                activity_summary = f"No commits in the last {hours} hours"

            return GitActivity(
                project_id=self.project_id,
                commits_count=len(recent_commits),
                files_changed=files_changed,
                active_branches=active_branches,
                recent_commits=recent_commits,
                activity_summary=activity_summary
            )

        except Exception as e:
            logger.error(f"Failed to analyze Git activity for {self.project_id}: {e}")
            return GitActivity(
                project_id=self.project_id,
                commits_count=0,
                files_changed=set(),
                active_branches=[],
                recent_commits=[],
                activity_summary=f"Analysis failed: {str(e)}"
            )
    
    def get_uncommitted_changes(self) -> Dict[str, List[str]]:
        """
        Get current uncommitted changes in the repository.
        
        Returns:
            Dictionary with 'modified', 'added', 'deleted' file lists
        """
        if not self.repo:
            return {
                'modified': [],
                'added': [],
                'deleted': []
            }
        
        try:
            # fair warning - GitPython uses different status categories
            modified_files = [item.a_path for item in self.repo.index.diff(None)]
            staged_files = [item.a_path for item in self.repo.index.diff("HEAD")]
            untracked_files = self.repo.untracked_files
            
            # Get deleted files
            deleted_files = []
            for item in self.repo.index.diff(None):
                if item.deleted_file:
                    deleted_files.append(item.a_path)
            
            return {
                'modified': modified_files,
                'added': list(untracked_files) + staged_files,
                'deleted': deleted_files
            }

        except Exception as e:
            logger.error(f"Failed to get uncommitted changes for {self.project_id}: {e}")
            return {
                'modified': [],
                'added': [],
                'deleted': []
            }


class GitIntegratedRAGAgent:
    """
    Integrates Git tracking with the main RAG agent.

    Manages multiple GitActivityTracker instances and provides
    a unified interface for the RAG agent to access Git data.
    """
    
    def __init__(self, rag_agent, project_manager):
        """
        Initialize Git integration for RAG agent.

        Args:
            rag_agent: Reference to ProjectKnowledgeAgent
            project_manager: Reference to ProjectManager
        """
        self.rag_agent = rag_agent
        self.project_manager = project_manager
        self.git_trackers: Dict[str, GitActivityTracker] = {}
        
    def init_git_tracking(self, project_id: str) -> bool:
        """
        Initialize Git tracking for a specific project.
        
        Args:
            project_id: Project identifier

        Returns:
            True if successful, False otherwise
        """
        # TODO: Get project path from project manager
        # TODO: Create GitActivityTracker instance
        # TODO: Store in git_trackers dictionary
        
        logger.info(f"Git tracking initialized for project {project_id}")
        return True
    
    async def update_project_from_git(self, project_id: str):
        """
        Update project knowledge base from Git activity.
        
        Args:
            project_id: Project to update
        """
        # TODO: Get recent Git activity
        # TODO: Extract relevant changes
        # TODO: Update RAG knowledge base with new information
        
        logger.info(f"Updated project {project_id} from Git activity")


# Placeholder functions for integration points
def integrate_with_rag_agent():
    """Integration point with main RAG agent"""
    pass


def add_git_endpoints(app):
    """Add Git-related API endpoints to Flask app"""
    # TODO: Implement endpoints as specified in the upgrade plan
    pass


if __name__ == "__main__":
    # Test code for development
    print("Git Activity Tracker - ContextKeeper v3.0")
    print("This module provides Git-based activity tracking")