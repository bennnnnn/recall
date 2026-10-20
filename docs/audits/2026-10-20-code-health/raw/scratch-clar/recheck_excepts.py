import ast, re, sys
rows = [l.rstrip("\n").split("\t") for l in open("py_excepts.tsv")]
STD = re.compile(r"\b(logger|logging|log|_log|LOGGER|_logger)\.(debug|info|warning|warn|error|exception|critical|log)\(|\breport_(exception|message|breadcrumb)\(|sentry_sdk\.capture")
for path, line, tname, kind, first in rows:
    if kind != "log":
        continue
    src = open("/home/user/recall-audit/apps/" + path).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.lineno == int(line):
            body = ast.unparse(ast.Module(body=node.body, type_ignores=[]))
            if not STD.search(body):
                print(f"{path}:{line}\t{body[:200]!r}")
