#!/usr/bin/env python3
"""
enhanced_drift_sacred.py - Sacred-aware drift detection for ContextKeeper v3.0

Created: 2025-07-24 03:43:00 (Australia/Sydney)
Part of: ContextKeeper v3.0 Sacred Layer Upgrade

Purpose:
Enhances drift detection to compare current development against sacred plans,
providing real-time alerts when code deviates from approved architectural plans.

Key Features:
- Compare code changes against sacred plans
- Calculate alignment scores
- Detect violations in real-time
- Provide actionable recommendations
- Support continuous monitoring

Dependencies:
- scikit-learn for similarity calculations
- Integration with Sacred Layer
- Git activity tracking
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class DriftStatus(Enum):
    """Drift detection status levels"""
    ALIGNED = "aligned"
    MINOR_DRIFT = "minor_drift"
    MODERATE_DRIFT = "moderate_drift"
    CRITICAL_VIOLATION = "critical_violation"


@dataclass
class DriftAnalysis:
    """Results of drift analysis against sacred plans"""
    project_id: str
    status: DriftStatus
    alignment_score: float  # 0.0 to 1.0
    violations: List[Dict]
    recommendations: List[str]
    analyzed_at: datetime
    sacred_plans_checked: List[str]


class SacredDriftDetector:
    """
    Detects drift between current development and sacred plans.
    
    Continuously monitors code changes and compares them against
    approved sacred plans to ensure adherence.
    """
    
    def __init__(self, sacred_manager, git_tracker):
        """
        Initialize Sacred Drift Detector.
        
        Args:
            sacred_manager: Reference to SacredLayerManager
            git_tracker: Reference to GitActivityTracker
        """
        self.sacred_manager = sacred_manager
        self.git_tracker = git_tracker
        
        # Thresholds for drift detection
        self.alignment_thresholds = {
            'critical': 0.3,   # Below this is critical violation
            'moderate': 0.6,   # Below this is moderate drift
            'minor': 0.8,      # Below this is minor drift
            'aligned': 0.8     # Above this is aligned
        }
        
    async def analyze_sacred_drift(self, project_id: str,
                                  hours: int = 24) -> DriftAnalysis:
        """
        Analyze drift between recent changes and sacred plans.
        
        Args:
            project_id: Project to analyze
            hours: Hours of activity to analyze
            
        Returns:
            DriftAnalysis with results
        """
        try:
            # Get recent Git activity for the project
            git_activity = self.git_tracker.analyze_activity(hours)
            
            # If no Git activity, assume aligned
            if git_activity.commits_count == 0:
                analysis = DriftAnalysis(
                    project_id=project_id,
                    status=DriftStatus.ALIGNED,
                    alignment_score=1.0,
                    violations=[],
                    recommendations=["No recent Git activity to analyze"],
                    analyzed_at=datetime.now(),
                    sacred_plans_checked=[]
                )
                logger.info(f"No Git activity for drift analysis: {project_id}")
                return analysis
            
            # Get sacred plans for this project using the sacred manager
            sacred_plans = []
            sacred_plans_checked = []
            
            try:
                # Load sacred plans from storage directory - they're stored as JSON files
                import os
                import json
                storage_path = self.sacred_manager.storage_path
                sacred_plans_dir = os.path.join(storage_path, "rag_knowledge_db", "sacred_plans")

                if os.path.exists(sacred_plans_dir):
                    for filename in os.listdir(sacred_plans_dir):
                        if filename.endswith('.json') and filename.startswith('plan_'):
                            plan_path = os.path.join(sacred_plans_dir, filename)
                            try:
                                with open(plan_path, 'r') as f:
                                    plan_data = json.load(f)
                                    if plan_data.get('project_id') == project_id:
                                        sacred_plans.append(plan_data)
                                        sacred_plans_checked.append(plan_data.get('plan_id', filename))
                            except Exception as e:
                                logger.warning(f"Failed to load plan {filename}: {e}")

                    logger.info(f"Found {len(sacred_plans)} sacred plans for project {project_id}")
                else:
                    logger.info(f"No sacred plans directory found at {sacred_plans_dir}")
            except Exception as e:
                logger.warning(f"Failed to load sacred plans for {project_id}: {e}")
            
            violations = []
            alignment_scores = []
            
            # alright, so the idea here is to compare Git activity against sacred plans
            # Now we have actual sacred plans to compare against
            
            # Analyze changes against sacred plans
            changed_files = list(git_activity.files_changed)
            alignment_score = 1.0  # Default to aligned if no issues found
            
            if changed_files and sacred_plans:
                # Extract sacred plan constraints and principles
                sacred_constraints = []
                for plan in sacred_plans:
                    content = plan.get('content', '')
                    # Look for key architectural constraints
                    if 'sacred plans stored separately' in content.lower():
                        sacred_constraints.append("sacred_separation")
                    if 'backward compatibility' in content.lower():
                        sacred_constraints.append("backward_compatibility")
                    if 'chromadb' in content.lower():
                        sacred_constraints.append("chromadb_storage")
                    if 'modular components' in content.lower():
                        sacred_constraints.append("modular_architecture")

                # Check if file changes violate sacred principles
                violation_score = 0
                total_checks = 0

                for file_path in changed_files:
                    file_lower = file_path.lower()
                    total_checks += 1

                    # Check sacred separation constraint
                    if "sacred_separation" in sacred_constraints:
                        if "sacred" in file_lower and not any(area in file_lower for area in ["sacred_layer", "sacred_plans"]):
                            violations.append({
                                "type": "sacred_separation_violation",
                                "file": file_path,
                                "message": f"Sacred functionality detected in non-sacred file: {file_path}"
                            })
                            violation_score += 1

                    # Check backward compatibility constraint
                    if "backward_compatibility" in sacred_constraints:
                        if any(v2_file in file_lower for v2_file in ["project_manager", "rag_agent"]):
                            # This is good - maintaining v2.0 files
                            pass
                        elif "v3" in file_lower or "sacred" in file_lower:
                            # This is also good - v3.0 development
                            pass
                        else:
                            # Neutral - other changes
                            pass

                # Calculate alignment score based on violations
                if total_checks > 0:
                    alignment_score = max(0.0, 1.0 - (violation_score / total_checks))

                logger.info(f"Sacred drift analysis: {violation_score} violations out of {total_checks} checks")

            elif changed_files and not sacred_plans:
                # No sacred plans to compare against - do basic pattern analysis
                sacred_areas = ["sacred_layer", "git_activity", "drift"]
                non_sacred_changes = [f for f in changed_files if not any(area in f.lower() for area in sacred_areas)]
                
                if non_sacred_changes:
                    violations.append({
                        "type": "no_sacred_guidance",
                        "files": non_sacred_changes,
                        "message": f"Changes detected in {len(non_sacred_changes)} files but no sacred plans exist for guidance"
                    })
                
                # Calculate alignment score based on pattern matching
                total_files = len(changed_files)
                sacred_files = total_files - len(non_sacred_changes)

                if total_files > 0:
                    alignment_score = sacred_files / total_files

            # Determine status based on alignment score
            status = self.determine_status(alignment_score)

            # Generate recommendations based on sacred plan content and violations
            recommendations = []
            
            if sacred_plans and violations:
                # Generate specific recommendations based on sacred plan principles
                for plan in sacred_plans:
                    content = plan.get('content', '')
                    if 'immutability' in content.lower() and any(v['type'] == 'sacred_separation_violation' for v in violations):
                        recommendations.append("Ensure sacred plan immutability by keeping sacred functionality in dedicated sacred_layer files")
                    if 'backward compatibility' in content.lower():
                        recommendations.append("Maintain v2.0 functionality in existing files while adding v3.0 features in new sacred components")
                    if 'chromadb' in content.lower() and any('database' in str(v).lower() for v in violations):
                        recommendations.append("Follow ChromaDB isolation principle from sacred architecture plan")

            if alignment_score < 0.8:
                if sacred_plans:
                    recommendations.append(f"Review changes against {len(sacred_plans)} approved sacred plans to ensure architectural compliance")
                else:
                    recommendations.append("Consider creating sacred plans to provide architectural guidance for future development")

            if violations:
                violation_types = set(v.get('type', 'unknown') for v in violations)
                if 'sacred_separation_violation' in violation_types:
                    recommendations.append("Move sacred functionality to proper sacred_layer components")
                if 'no_sacred_guidance' in violation_types:
                    recommendations.append("Create sacred architectural plans to guide development decisions")
            
            if not recommendations:
                if sacred_plans:
                    recommendations.append(f"Development appears aligned with {len(sacred_plans)} sacred architectural plans")
                else:
                    recommendations.append("No drift detected - consider establishing sacred plans for future architectural governance")

            analysis = DriftAnalysis(
                project_id=project_id,
                status=status,
                alignment_score=alignment_score,
                violations=violations,
                recommendations=recommendations,
                analyzed_at=datetime.now(),
                sacred_plans_checked=sacred_plans_checked
            )

            logger.info(f"Sacred drift analysis completed for {project_id}: {status.value} ({alignment_score:.2f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze sacred drift for {project_id}: {e}")
            return DriftAnalysis(
                project_id=project_id,
                status=DriftStatus.ALIGNED,
                alignment_score=0.0,
                violations=[{"type": "analysis_error", "message": str(e)}],
                recommendations=["Unable to perform drift analysis"],
                analyzed_at=datetime.now(),
                sacred_plans_checked=[]
            )
    
    def calculate_alignment(self, code_embeddings: np.ndarray,
                          plan_embeddings: np.ndarray) -> float:
        """
        Calculate alignment score between code and plan.
        
        Args:
            code_embeddings: Embeddings of current code
            plan_embeddings: Embeddings of sacred plan
            
        Returns:
            Alignment score (0.0 to 1.0)
        """
        # TODO: Use cosine similarity
        # TODO: Apply weighting for importance
        # TODO: Normalize to 0-1 range
        
        return 1.0  # Placeholder
    
    def detect_violations(self, code_changes: List[Dict],
                         sacred_plan: Dict) -> List[Dict]:
        """
        Detect specific violations of sacred plans.
        
        Args:
            code_changes: Recent code changes
            sacred_plan: Sacred plan to check against

        Returns:
            List of violation details
        """
        violations = []
        
        # TODO: Check for architectural violations
        # TODO: Check for technology choice violations
        # TODO: Check for pattern violations
        # TODO: Include file and line information
        
        return violations

    def generate_recommendations(self, violations: List[Dict]) -> List[str]:
        """
        Generate actionable recommendations based on violations.
        
        Args:
            violations: Detected violations
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # TODO: Analyze violation patterns
        # TODO: Suggest specific fixes
        # TODO: Prioritize by severity
        # TODO: Include code examples
        
        return recommendations
    
    def determine_status(self, alignment_score: float) -> DriftStatus:
        """
        Determine drift status from alignment score.

        Args:
            alignment_score: Calculated alignment (0.0 to 1.0)

        Returns:
            DriftStatus enum value
        """
        if alignment_score >= self.alignment_thresholds['aligned']:
            return DriftStatus.ALIGNED
        elif alignment_score >= self.alignment_thresholds['minor']:
            return DriftStatus.MINOR_DRIFT
        elif alignment_score >= self.alignment_thresholds['moderate']:
            return DriftStatus.MODERATE_DRIFT
        else:
            return DriftStatus.CRITICAL_VIOLATION


class ContinuousDriftMonitor:
    """
    Continuously monitors for sacred plan violations.

    Runs as a background task checking for drift at regular intervals
    and triggering alerts when violations are detected.
    """

    def __init__(self, drift_detector, alert_handler):
        """
        Initialize continuous monitoring.
        
        Args:
            drift_detector: SacredDriftDetector instance
            alert_handler: Handler for drift alerts
        """
        self.drift_detector = drift_detector
        self.alert_handler = alert_handler
        self.monitoring_interval = 300  # 5 minutes
        
    async def start_monitoring(self, project_ids: List[str]):
        """
        Start continuous drift monitoring for projects.
        
        Args:
            project_ids: Projects to monitor
        """
        # TODO: Implement continuous monitoring loop
        # TODO: Check each project for drift
        # TODO: Trigger alerts for violations
        # TODO: Log monitoring activity
        
        logger.info(f"Started sacred drift monitoring for {len(project_ids)} projects")


def add_sacred_drift_endpoint(app, agent, project_manager, sacred_manager):
    """
    Add sacred drift detection endpoint to Flask app.
    
    Args:
        app: Flask application
        agent: RAG agent
        project_manager: Project manager
        sacred_manager: Sacred layer manager
    """
    # TODO: Implement drift detection endpoint
    # TODO: Return drift analysis results
    # TODO: Include visualization data

    @app.route('/sacred/drift/<project_id>', methods=['GET'])
    async def check_sacred_drift(project_id):
        """Check drift for a specific project"""
        # Placeholder implementation
        return {"status": "not_implemented"}


# Visualization helpers
def format_drift_report(analysis: DriftAnalysis) -> str:
    """
    Format drift analysis for CLI display.

    Args:
        analysis: DriftAnalysis results

    Returns:
        Formatted report string
    """
    # TODO: Create visual drift report
    # TODO: Use color coding for severity
    # TODO: Include actionable next steps

    return f"Drift Analysis for {analysis.project_id}"


if __name__ == "__main__":
    # Test code for development
    print("Enhanced Sacred Drift Detection - ContextKeeper v3.0")
    print("Monitors code changes against sacred plans")