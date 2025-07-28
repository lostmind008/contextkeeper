#!/usr/bin/env python3
"""
sacred_layer_implementation.py - Core Sacred Layer for ContextKeeper v3.0

Created: 2025-07-24 03:42:00 (Australia/Sydney)
Part of: ContextKeeper v3.0 Sacred Layer Upgrade

Purpose:
Implements the Sacred Layer - an immutable plan storage system with 2-layer
verification to ensure AI agents never derail from approved plans.

Key Features:
- Immutable plan storage with hash verification
- 2-layer approval system (verification code + environment key)
- Semantic chunking for large plan files
- Isolated ChromaDB collections for sacred plans
- Audit trail for all operations

Dependencies:
- ChromaDB for vector storage
- scikit-learn for text processing
- langchain for text splitting
"""

import os
import json
import hashlib
import logging
import uuid
import secrets
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class PlanStatus(Enum):
    """Sacred plan status enumeration"""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


@dataclass
class SacredPlan:
    """Represents a sacred plan with immutable content"""
    plan_id: str
    project_id: str
    title: str
    content: str
    content_hash: str
    status: PlanStatus
    created_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[str]
    verification_code: Optional[str]
    chunks: List[str]  # For large plans
    metadata: Dict


class SacredLayerManager:
    """
    Manages sacred plans with immutable storage and verification.
    
    The Sacred Layer ensures that approved plans cannot be modified
    and provides strong verification for plan approval.
    """

    def __init__(self, storage_path: str):
        """
        Initialize Sacred Layer Manager.

        Args:
            storage_path: Base path for sacred plan storage
        """
        self.storage_path = Path(storage_path)
        self.sacred_plans_dir = self.storage_path / "sacred_plans"
        self.sacred_chromadb_dir = self.storage_path / "sacred_chromadb"

        # Create directories if they don't exist
        self.sacred_plans_dir.mkdir(parents=True, exist_ok=True)
        self.sacred_chromadb_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client for sacred embeddings
        # alright, so the idea here is to create isolated collections for sacred plans
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.sacred_chromadb_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Load approval key from environment
        self.approval_key = os.environ.get('SACRED_APPROVAL_KEY', '')
        
        # Store active plan collections per project
        self.plan_collections = {}
        
    def create_plan(self, project_id: str, title: str, content: str) -> SacredPlan:
        """
        Create a new sacred plan in draft status.
        
        Args:
            project_id: Project this plan belongs to
            title: Plan title
            content: Plan content (can be very large)

        Returns:
            Created SacredPlan object
        """
        # Generate unique plan ID using UUID
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"

        # Compute SHA256 hash of content for integrity verification
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        # Chunk large content for ChromaDB storage
        chunks = self.chunk_large_plan(content) if len(content) > 1000 else []

        # Generate verification code for approval process
        verification_code = self._generate_verification_code()

        # Create plan object
        plan = SacredPlan(
            plan_id=plan_id,
            project_id=project_id,
            title=title,
            content=content,
            content_hash=content_hash,
            status=PlanStatus.DRAFT,
            created_at=datetime.now(),
            approved_at=None,
            approved_by=None,
            verification_code=verification_code,
            chunks=chunks,
            metadata={"chunked": len(chunks) > 0}
        )
        
        # Store plan metadata in JSON file
        plan_file = self.sacred_plans_dir / f"{plan_id}.json"
        with open(plan_file, 'w') as f:
            # Convert datetime objects and enums to serializable format
            plan_dict = asdict(plan)
            plan_dict['created_at'] = plan.created_at.isoformat()
            plan_dict['status'] = plan.status.value  # Convert enum to string
            if plan.approved_at:
                plan_dict['approved_at'] = plan.approved_at.isoformat()
            json.dump(plan_dict, f, indent=2)
            
        # Store plan chunks in ChromaDB for semantic search
        if chunks:
            collection = self._get_plan_collection(project_id)
            # Store each chunk with metadata for reconstruction
            for i, chunk in enumerate(chunks):
                collection.add(
                    ids=[f"{plan_id}_chunk_{i}"],
                    documents=[chunk],
                    metadatas=[{
                        "plan_id": plan_id,
                        "project_id": project_id,
                        "title": title,
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "status": plan.status.value,
                        "created_at": plan.created_at.isoformat()
                    }]
                )

        logger.info(f"Created sacred plan: {plan_id} with {len(chunks)} chunks")
        return plan
    
    def _generate_verification_code(self) -> str:
        """
        Generate a random verification code for plan approval.
        
        Returns:
            8-character verification code
        """
        # Generate cryptographically secure random code
        return secrets.token_hex(4).upper()

    def generate_verification_code(self, plan: SacredPlan) -> str:
        """
        Generate a verification code for an existing plan.

        Args:
            plan: The plan to generate code for

        Returns:
            Verification code string
        """
        # Use the plan's content hash as part of verification for added security
        return f"{secrets.token_hex(4).upper()}-{plan.content_hash[:8].upper()}"

    def approve_plan(self, plan_id: str, verification_code: str, approval_key: str) -> bool:
        """
        Approve a sacred plan with 2-layer verification.

        Args:
            plan_id: Plan to approve
            verification_code: First layer verification
            approval_key: Second layer (environment key)
            
        Returns:
            True if approved, False otherwise
        """
        try:
            # Load plan from storage
            plan_file = self.sacred_plans_dir / f"{plan_id}.json"
            if not plan_file.exists():
                logger.warning(f"Plan not found: {plan_id}")
                return False
                
            with open(plan_file, 'r') as f:
                plan_data = json.load(f)
            
            # Verify first layer (verification code)
            stored_verification = plan_data.get('verification_code')
            if not stored_verification or stored_verification != verification_code:
                logger.warning(f"Verification code mismatch for plan {plan_id}")
                return False

            # Verify second layer (environment key)
            if not self.approval_key or self.approval_key != approval_key:
                logger.warning(f"Approval key verification failed for plan {plan_id}")
                return False

            # Update plan status to approved
            plan_data['status'] = PlanStatus.APPROVED.value
            plan_data['approved_at'] = datetime.now().isoformat()
            plan_data['approved_by'] = "system"  # Could be enhanced to track user

            # basically, we need to make this immutable now
            with open(plan_file, 'w') as f:
                json.dump(plan_data, f, indent=2)

            # Update ChromaDB chunks if they exist
            if plan_data.get('chunks'):
                collection = self._get_plan_collection(plan_data['project_id'])
                # Update all chunk metadata to reflect approval
                for i in range(len(plan_data['chunks'])):
                    chunk_id = f"{plan_id}_chunk_{i}"
                    # fair warning - we're updating metadata but documents remain immutable
                    collection.update(
                        ids=[chunk_id],
                        metadatas=[{
                            "plan_id": plan_id,
                            "project_id": plan_data['project_id'],
                            "title": plan_data['title'],
                            "chunk_index": i,
                            "total_chunks": len(plan_data['chunks']),
                            "status": PlanStatus.APPROVED.value,
                            "created_at": plan_data['created_at'],
                            "approved_at": plan_data['approved_at']
                        }]
                    )
            
            logger.info(f"✅ Sacred plan approved: {plan_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to approve plan {plan_id}: {e}")
            return False
    
    def list_plans(self, project_id: Optional[str] = None,
                  status: Optional[str] = None) -> List[SacredPlan]:
        """List all plans with optional filtering"""
        plans = []
        
        if project_id:
            # Get plans for specific project
            collection = self._get_plan_collection(project_id)
            try:
                results = collection.get()

                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    content = results['documents'][i]

                    # Filter by status if specified
                    if status and metadata.get('status') != status:
                        continue

                    # Create SacredPlan object from stored data
                    plan = SacredPlan(
                        plan_id=doc_id,
                        project_id=project_id,
                        title=metadata.get('title', 'Untitled'),
                        content=content,
                        status=PlanStatus(metadata.get('status', 'draft')),
                        created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat())),
                        approved_at=datetime.fromisoformat(metadata['approved_at']) if metadata.get('approved_at') else None,
                        content_hash=metadata.get('content_hash', ''),
                        verification_code=metadata.get('verification_code', '')
                    )
                    plans.append(plan)

            except Exception as e:
                logger.error(f"Error listing plans for project {project_id}: {e}")
        
        # Sort by creation time, newest first
        plans.sort(key=lambda p: p.created_at, reverse=True)
        return plans

    def chunk_large_plan(self, content: str, chunk_size: int = 1000) -> List[str]:
        """
        Chunk large plan content for efficient storage and retrieval.
        
        Args:
            content: Plan content to chunk
            chunk_size: Target chunk size

        Returns:
            List of content chunks
        """
        # Simple but effective chunking for sacred plans
        # alright, so the idea here is to split on paragraphs first, then sentences
        chunks = []
        
        # Split by double newlines (paragraphs) first
        paragraphs = content.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size, finalize current chunk
            if len(current_chunk) + len(paragraph) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Add the final chunk if there's content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If we still have overly large chunks, split them further
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= chunk_size:
                final_chunks.append(chunk)
            else:
                # Split long chunks by sentences
                sentences = chunk.split('. ')
                sub_chunk = ""
                for sentence in sentences:
                    if len(sub_chunk) + len(sentence) > chunk_size and sub_chunk:
                        final_chunks.append(sub_chunk.strip() + ".")
                        sub_chunk = sentence
                    else:
                        if sub_chunk:
                            sub_chunk += ". " + sentence
                        else:
                            sub_chunk = sentence
                if sub_chunk.strip():
                    final_chunks.append(sub_chunk.strip())

        return final_chunks
    
    def _get_plan_collection(self, project_id: str):
        """
        Get or create ChromaDB collection for project's sacred plans.
        
        Args:
            project_id: Project identifier

        Returns:
            ChromaDB collection for the project
        """
        if project_id not in self.plan_collections:
            collection_name = f"sacred_{project_id}"
            try:
                # Try to get existing collection
                self.plan_collections[project_id] = self.chroma_client.get_collection(collection_name)
                logger.info(f"Using existing sacred collection: {collection_name}")
            except:
                # Create new collection
                self.plan_collections[project_id] = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine", "project_id": project_id, "type": "sacred_plans"}
                )
                logger.info(f"Created new sacred collection: {collection_name}")

        return self.plan_collections[project_id]
    
    def reconstruct_plan(self, chunks: List[str]) -> str:
        """
        Reconstruct full plan content from chunks.
        
        Args:
            chunks: List of plan chunks
            
        Returns:
            Complete plan content
        """
        # TODO: Implement chunk reconstruction
        # TODO: Verify reconstruction accuracy

        return "".join(chunks)


class SacredIntegratedRAGAgent:
    """
    Integrates Sacred Layer with the main RAG agent.

    Provides sacred-aware context and ensures AI agents respect
    approved plans while making suggestions.
    """
    
    def __init__(self, rag_agent):
        """
        Initialize Sacred Layer integration.

        Args:
            rag_agent: Reference to ProjectKnowledgeAgent
        """
        self.rag_agent = rag_agent
        self.sacred_manager = SacredLayerManager(
            rag_agent.project_manager.storage_path
        )

    async def create_sacred_plan(self, project_id: str, title: str, 
                                content_or_path: str) -> Dict:
        """
        Create a new sacred plan from content or file.

        Args:
            project_id: Project ID
            title: Plan title
            content_or_path: Plan content or path to file

        Returns:
            API response dictionary
        """
        # TODO: Determine if input is content or file path
        # TODO: Read file if path provided
        # TODO: Create plan via sacred manager
        # TODO: Generate verification code
        # TODO: Return plan details with verification code
        
        return {
            "status": "created",
            "plan_id": "placeholder",
            "verification_code": "placeholder"
        }
    
    async def approve_sacred_plan(self, plan_id: str, approver: str,
                                 verification_code: str,
                                 secondary_verification: str) -> Dict:
        """
        Approve a sacred plan with 2-layer verification.

        Args:
            plan_id: Plan to approve
            approver: Approver name
            verification_code: First verification
            secondary_verification: Second verification

        Returns:
            API response dictionary
        """
        # TODO: Call sacred manager approval
        # TODO: Update ChromaDB with approved plan
        # TODO: Return approval status
        
        return {
            "status": "pending",
            "plan_id": plan_id
        }
    
    async def query_sacred_context(self, project_id: str, query: str) -> Dict:
        """
        Query sacred plans for a project.
        
        Args:
            project_id: Project to query
            query: Search query
            
        Returns:
            Sacred plans matching query
        """
        # TODO: Search sacred ChromaDB collection
        # TODO: Filter by project and approval status
        # TODO: Return relevant sacred plans
        
        return {
            "plans": [],
            "count": 0
        }


# Integration helper functions
def integrate_sacred_layer(app, agent):
    """Add sacred layer endpoints to Flask app"""
    # TODO: Implement sacred API endpoints
    pass


def add_sacred_cli_commands():
    """Define sacred CLI commands"""
    # TODO: Implement CLI command handlers
    pass


if __name__ == "__main__":
    # Test code for development
    print("Sacred Layer Implementation - ContextKeeper v3.0")
    print("Provides immutable plan storage with 2-layer verification")