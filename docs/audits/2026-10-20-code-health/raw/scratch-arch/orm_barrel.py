import ast, sys
from pathlib import Path
APP=Path(sys.argv[1])
owner_of={"TodoItem":"todos","Memory":"memory","MemoryArea":"memory","Attachment":"attachments","AttachmentChunk":"attachments","Suggestion":"suggestions"}
for p in sorted(APP.rglob("*.py")):
    rel=p.relative_to(APP)
    if "tests" in rel.parts or "__pycache__" in p.parts: continue
    t=ast.parse(p.read_text())
    for n in ast.walk(t):
        if isinstance(n,ast.ImportFrom) and n.module in ("app.models.orm","app.models"):
            for a in n.names:
                if a.name in owner_of:
                    own=owner_of[a.name]
                    mine = len(rel.parts)>1 and rel.parts[0]=="modules" and rel.parts[1]==own
                    if not mine:
                        print(f"{rel}:{n.lineno} imports {a.name} (owned by modules/{own}) via {n.module}")
