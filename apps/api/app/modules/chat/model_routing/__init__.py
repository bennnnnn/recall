"""Which model a chat turn runs on, and whether it thinks first (code-health audit ARCH-02).

``route`` reads the message: its subject, its length, a code block, a follow-up to a
smart turn. ``choice`` composes that with billing's pool for the user (``billing.plan``
keeps pools and picks by tier or price and reads no message), and ``thinking`` decides
the reasoning pass. ``signals``, ``rate_problems`` and ``physics`` are routing's cues.
"""
