# Fazle Agent System — Multi-agent architecture with identity core
from .base import BaseAgent, AgentContext, AgentResult
from .identity_core import IdentityProfile, get_identity, save_identity_overrides
from .conversation import ConversationAgent
from .memory_agent import MemoryAgent
from .research import ResearchAgent
from .task_agent import TaskAgent
from .tool_agent import ToolAgent
from .social_agent import SocialAgent
from .voice_agent import VoiceAgent
from .system_agent import SystemAgent
from .learning_agent import LearningAgent
from .strategy_agent import StrategyAgent, DomainRoute
from .manager import AgentManager

__all__ = [
    # Core
    "BaseAgent",
    "AgentContext",
    "AgentResult",
    # Identity
    "IdentityProfile",
    "get_identity",
    "save_identity_overrides",
    # Domain agents
    "SocialAgent",
    "VoiceAgent",
    "SystemAgent",
    "LearningAgent",
    # Strategy
    "StrategyAgent",
    "DomainRoute",
    # Utility agents
    "ConversationAgent",
    "MemoryAgent",
    "ResearchAgent",
    "TaskAgent",
    "ToolAgent",
    # Manager
    "AgentManager",
]
