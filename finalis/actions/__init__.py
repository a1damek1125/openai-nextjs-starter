"""Finalis Action & Communication Engine — the execution layer.

Case Graph knows what happened. Completion Loop knows what should happen
next. This engine executes the next step safely: gate → consent → rate
limit → channel routing → message composition → (approval) → durable
scheduling → delivery → tracking → case update → audit.

Infrastructure (Temporal/Novu/Chatwoot) sits behind adapters; the Finalis
brain — gate, approval, audit — is custom and always in the path.
"""

__version__ = "0.1.0"
