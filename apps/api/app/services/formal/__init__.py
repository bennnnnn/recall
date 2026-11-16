"""A STEM question as a model writes it down, checked and solved by the server.

``problem``: the setup a model writes (givens with units and their words, unknowns, equations).
``solve``: the checks and the solve, run in the SymPy pool. ``constants``: the standard values
a question may rely on without stating them.
"""
