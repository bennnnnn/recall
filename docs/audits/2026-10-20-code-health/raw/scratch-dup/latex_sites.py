"""List API/phone lines that rewrite LaTeX commands (\\frac, \\sqrt, \\text, \\mathrm, \\left, \\times, \\cdot) — read-only scan."""
import os, re, sys, collections
root = sys.argv[1]
exts = tuple(sys.argv[2].split(","))
cmd = re.compile(r"\\\\+(?:d|t)?frac|\\\\+sqrt|\\\\+text\b|\\\\+mathrm|\\\\+left|\\\\+right|\\\\+times|\\\\+cdot|\\\\+operatorname")
op = re.compile(r"re\.(?:sub|compile)|\.replace\(|replaceAll\(|new RegExp|/[^/\n]*\\\\(?:frac|sqrt|text|mathrm|left|times|cdot)")
per = collections.Counter(); ex = collections.defaultdict(list)
for dp, dn, fn in os.walk(root):
    if any(p in dp for p in ("/tests", "__tests__", "node_modules", "/vendor", "__pycache__")):
        continue
    for f in fn:
        if not f.endswith(exts): continue
        p = os.path.join(dp, f)
        for i, line in enumerate(open(p, errors="ignore"), 1):
            if cmd.search(line) and op.search(line):
                per[p] += 1; ex[p].append(i)
for p, c in per.most_common(80):
    print(c, p.replace(root, ""), ex[p][:6])
