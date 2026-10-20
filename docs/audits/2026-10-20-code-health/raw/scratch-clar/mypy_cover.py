import ast, os, fnmatch, collections
ROOT = "/home/user/recall-audit/apps/api/app"
strict = ["app.core", "app.core.*", "app.exceptions", "app.models.schemas", "app.models.schemas.*",
          "app.modules.attachments.content", "app.modules.attachments.ocr", "app.modules.attachments.upload",
          "app.repositories", "app.repositories.*", "app.services.quota", "app.services.quota.*"]
tot = collections.Counter(); untyped = collections.Counter(); untyped_list = []
for dp, dn, fn in os.walk(ROOT):
    if "__pycache__" in dp or "/tests" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, os.path.dirname(ROOT))[:-3].replace("/", ".")
        if rel.endswith(".__init__"): rel = rel[:-9]
        is_strict = any(fnmatch.fnmatchcase(rel, pat) for pat in strict)
        src = open(p).read()
        n = len(src.splitlines())
        tot["strict" if is_strict else "lax"] += n
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                params = [a for a in args if a.arg not in ("self", "cls")]
                ann_missing = node.returns is None or any(a.annotation is None for a in params)
                fully_untyped = node.returns is None and all(a.annotation is None for a in params)
                if ann_missing:
                    untyped["partial" if not fully_untyped else "untyped"] += 1
                    if fully_untyped and not is_strict:
                        untyped_list.append((rel, node.lineno, node.name))
top = collections.Counter(r[0].split(".")[1] + "." + r[0].split(".")[2] if r[0].count(".")>=2 else r[0] for r in untyped_list)
print(tot, "strict share: %.1f%%" % (100*tot["strict"]/(tot["strict"]+tot["lax"])))
print(untyped)
print("fully untyped (bodies unchecked) outside strict:", len(untyped_list), top.most_common(10))
