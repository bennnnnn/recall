"""Verdict per jscpd clone group (index = order in jscpd-report.json), and totals."""
import json, collections
V = {
 1:"data", 2:"style", 3:"real-cross", 4:"real-cross", 5:"real-cross", 6:"real-intra", 7:"real-intra",
 8:"real-cross", 9:"style", 10:"real-cross", 11:"style", 12:"facade", 13:"lookalike", 14:"signature",
 15:"lookalike", 16:"lookalike", 17:"lookalike", 18:"lookalike", 19:"lookalike", 20:"imports",
 21:"artifact", 22:"data", 23:"data", 24:"lookalike", 25:"lookalike", 26:"style", 27:"artifact",
 28:"real-cross", 29:"lookalike", 30:"real-cross", 31:"imports", 32:"imports", 33:"data", 34:"lookalike",
 35:"lookalike", 36:"signature", 37:"imports", 38:"lookalike", 39:"real-intra", 40:"real-intra",
 41:"imports", 42:"data", 43:"imports", 44:"data", 45:"data", 46:"data", 47:"data", 48:"data", 49:"data",
 50:"data", 51:"data", 52:"data", 53:"data", 54:"data", 55:"data", 56:"data", 57:"real-intra",
 58:"real-cross", 59:"real-intra", 60:"real-intra", 61:"imports", 62:"real-intra", 63:"real-cross",
 64:"facade", 65:"real-intra", 66:"facade", 67:"facade", 68:"data", 69:"signature", 70:"signature",
 71:"signature", 72:"signature", 73:"real-intra", 74:"imports", 75:"signature", 76:"signature",
 77:"real-cross", 78:"signature",
}
rep = json.load(open("/home/user/recall/tmp/code-audit/raw/jscpd/jscpd-report.json"))["duplicates"]
assert len(rep) == len(V) == 78
by = collections.Counter(V.values()); lines = collections.Counter()
side = collections.Counter()
for i, d in enumerate(rep, 1):
    lines[V[i]] += d["lines"]
    side[(V[i], "api" if d["firstFile"]["name"].startswith("apps/api") else "phone")] += 1
for k in sorted(by): print(f"{k:12s} groups={by[k]:3d} lines={lines[k]:4d}  api={side[(k,'api')]} phone={side[(k,'phone')]}")
print("total groups", sum(by.values()), "lines", sum(lines.values()))
