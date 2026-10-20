"""Size of one 1536-dim embedding as stored by the app (json.dumps) and as pgvector text."""
import json, random, math, zlib, array
random.seed(7)
vec = [random.gauss(0, 1 / math.sqrt(1536)) for _ in range(1536)]
norm = math.sqrt(sum(v * v for v in vec))
vec = [v / norm for v in vec]
as_json = json.dumps(vec)
f32 = array.array("f", vec)
as_pgvector_text = "[" + ",".join(repr(float(f"{v:.9g}")) for v in f32) + "]"  # float4 text ~ 9 sig digits
print("json.dumps chars:", len(as_json))
print("json.dumps zlib-compressed bytes (pglz is weaker):", len(zlib.compress(as_json.encode())))
print("pgvector text chars (approx float4 repr):", len(as_pgvector_text))
print("pgvector binary bytes:", 4 + 4 * 1536)
