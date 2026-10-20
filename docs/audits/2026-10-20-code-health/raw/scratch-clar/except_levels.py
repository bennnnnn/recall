import ast, re, collections
rows = [l.rstrip("\n").split("\t") for l in open("py_excepts.tsv")]
levels = collections.Counter()
debug_only = []
for path, line, tname, kind, first in rows:
    if kind != "log":
        continue
    src = open("/home/user/recall-audit/apps/" + path).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.lineno == int(line):
            body = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
            lv = set(re.findall(r"\.(debug|info|warning|warn|error|exception|critical)\(", body))
            if "report_" in body: lv.add("sentry")
            key = ",".join(sorted(lv))
            levels[key] += 1
            if lv <= {"debug"}:
                debug_only.append(f"{path}:{line}\t{body[:160]!r}")
print(levels.most_common())
print("debug-only:", len(debug_only))
print("\n".join(debug_only))
