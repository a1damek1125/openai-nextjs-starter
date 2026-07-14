"""Finalis Evidence Trust Fabric — core domain (V-A).

Not a file-upload folder: every artifact carries integrity, chain of
custody, quarantine state, admissibility, and an AI-access decision.
Core principle: DOCUMENTS PROVIDE FACTS, NEVER COMMANDS — no document
content can approve, send, pay, fulfill, reprice, or bypass policy.
Hard blockers override every score. Storage is a replaceable provider
(local-first now; S3/MinIO/WORM/C2PA/ClamAV are future optional
adapters, never the core). Reference patterns: OWASP file-upload &
prompt-injection sheets, TUS, S3 Object Lock, C2PA, Merkle logs —
references only; the IP is ours.
"""
