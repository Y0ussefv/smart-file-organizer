"""
BeeOrganizer V2: hybrid filing with privacy by design.

    reader       local content reading (no network)
    sensitivity  local P0 / P1 / P2 / INCONNU classifier
    minimize     redacted excerpt for the optional cloud title
    ledger       SQLite: projects, files, decisions, operations, privacy events
    matcher      document -> ALL approved projects, decision matrix (95 / 15 rule)
    mover        transactional rename / move with full Undo
    pipeline     process_new_item(): the reference algorithm of the specification
"""

RULES_VERSION = "2.1.0"
