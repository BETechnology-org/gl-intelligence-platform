"""Agent registry — maps agent_type strings to BaseAgent instances."""

from __future__ import annotations

from typing import Dict

from .base import BaseAgent


class AgentRegistry:
    _instances: Dict[str, BaseAgent] = {}

    @classmethod
    def get_agent(cls, agent_type: str) -> BaseAgent:
        if agent_type in cls._instances:
            return cls._instances[agent_type]

        # Lazy-import to avoid pulling in claude_agent_sdk at import time
        if agent_type == "tax_classifier":
            from .tax.classifier_agent import TaxClassifierAgent
            cls._instances[agent_type] = TaxClassifierAgent()
        elif agent_type == "tax_etr_bridge":
            from .tax.etr_bridge_agent import ETRBridgeAgent
            cls._instances[agent_type] = ETRBridgeAgent()
        elif agent_type == "tax_disclosure":
            from .tax.disclosure_agent import TaxDisclosureAgent
            cls._instances[agent_type] = TaxDisclosureAgent()
        elif agent_type == "dise_mapping":
            from .dise.mapping_agent import DISEMappingAgent
            cls._instances[agent_type] = DISEMappingAgent()
        elif agent_type == "dise_recon":
            from .dise.recon_agent import DISEReconAgent
            cls._instances[agent_type] = DISEReconAgent()
        elif agent_type == "dise_anomaly":
            from .dise.anomaly_agent import DISEAnomalyAgent
            cls._instances[agent_type] = DISEAnomalyAgent()
        elif agent_type == "dise_disclosure":
            from .dise.disclosure_agent import DISEDisclosureAgent
            cls._instances[agent_type] = DISEDisclosureAgent()
        else:
            raise ValueError(f"Unknown agent_type: {agent_type}")

        return cls._instances[agent_type]


def get_agent(agent_type: str) -> BaseAgent:
    return AgentRegistry.get_agent(agent_type)
