import sys
from app.core.config import get_settings
from app.modules.physics.prompt import solve_physics_request
for q in sys.argv[1:]:
    o,b=solve_physics_request(q,get_settings(),None)
    print(o, b.display_answer if b else None, '|', q[:80])
