"""Finalis Agent Runtime Governance & Observability.

No invisible AI actions: every tool/provider call carries an AgentTrace,
passes the PolicyEnforcementGate, spends from an autonomy budget, and is
watched by failure-aware signals (waste, evidence coverage, tool risk).
Shadow mode computes-but-does-not-execute for risky rollouts. Secrets never
enter traces. Grounded in zero-trust agentic-AI research (arXiv 2605.02682,
2605.27575, 2605.11946, 2606.01365) over OpenTelemetry/OPA/OpenFeature-style
foundations.
"""
