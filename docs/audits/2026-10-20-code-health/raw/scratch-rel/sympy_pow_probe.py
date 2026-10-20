"""Library-only probe: does sympy parse_expr(evaluate=True) evaluate integer power towers eagerly?"""
import sys, time
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
expr = sys.argv[1]
t = time.perf_counter()
r = parse_expr(expr, transformations=standard_transformations + (implicit_multiplication_application,), evaluate=True)
dt = time.perf_counter() - t
s = str(type(r).__name__)
print(expr, "->", s, "digits" if s == "Integer" else "", len(str(r)) if s == "Integer" and dt < 5 else "", f"{dt:.3f}s")
