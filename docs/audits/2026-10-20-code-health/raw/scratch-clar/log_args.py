"""List logger calls whose interpolated args look like personal data or content."""
import ast, os, re, sys
ROOT = "/home/user/recall-audit/apps/api/app"
SUSPECT = re.compile(r"(text|content|prompt|query|message|msg|title|name|email|fact|memory|memories|reply|answer|url|uri|filename|file_name|token|ip\b|ip_|addr|device|phone|address|location|body|payload|transcript|question|instruction|summary|snippet|caption|subject|raw|response|resp|detail|data|args|kwargs|input|output|value|expr|expression|user\b|sub\b|identity|claims|headers|exc\b|err\b|error\b|e\b)", re.I)
LEVELS = {"debug","info","warning","warn","error","exception","critical"}
out = []
for dp, dn, fn in os.walk(ROOT):
    if "/tests" in dp or "__pycache__" in dp: continue
    for f in fn:
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f)
        src = open(p).read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LEVELS:
                v = node.func.value
                vname = ast.unparse(v)
                if not re.search(r"log", vname, re.I): continue
                if not node.args: continue
                fmt = node.args[0]
                fmt_s = ast.unparse(fmt)
                is_f = isinstance(fmt, ast.JoinedStr)
                argexprs = [ast.unparse(a) for a in node.args[1:]]
                if is_f:
                    argexprs += [ast.unparse(x.value) for x in fmt.values if isinstance(x, ast.FormattedValue)]
                hits = [a for a in argexprs if SUSPECT.search(a)]
                rel = os.path.relpath(p, "/home/user/recall-audit")
                out.append((rel, node.lineno, node.func.attr, "F" if is_f else "%", fmt_s[:110], ";".join(argexprs)[:150], ";".join(hits)[:120]))
with open("log_calls.tsv","w") as fh:
    for r in out:
        fh.write("\t".join(map(str,r))+"\n")
print(len(out), "log calls;", sum(1 for r in out if r[3]=="F"), "f-string;", sum(1 for r in out if r[6]), "with suspect args")
