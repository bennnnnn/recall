"""Email — the connected inbox as chat context.

``context`` decides whether a turn needs the inbox and builds the block for it,
``triage`` ranks what matters, ``sender_templates`` recognizes known senders,
and ``fence`` renders the email fence. Outbound mail is not here: transactional
sends and reminders live in ``app.modules.notifications``.
"""
