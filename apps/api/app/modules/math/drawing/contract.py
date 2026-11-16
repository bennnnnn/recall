"""The prompt contract that asks a reply to describe its picture in a ```draw block.

Added beside the message only on a maths turn that asks to see a picture (chat's
``figure_turn``). It is the one exception to the maths pack's "never draw" rule
(``reply_policy.GRAPH_NO_SUBSTITUTE_CLAUSE``): the reply says what the picture shows, in
the closed vocabulary ``vocabulary`` reads, and never in characters or Mermaid. Its words
are rules the leak pass knows (math's ``beside_visuals``).
"""

DRAW_CONTRACT = (
    "Picture for this question: when it asks to see a figure in space (points, vectors, a "
    "box, a sphere), a word problem's shape, or a graph (a sketch, a tangent, an area, a "
    "volume), describe the picture in one ```draw block, after your answer (a figure and a "
    "graph: one block each); the app checks it against the question and draws it under "
    "your reply. This replaces the rule against drawing for that picture only.\n"
    "- Write only JSON. Copy coordinates and sizes exactly as the question states them: the "
    "app works out where everything goes, and every value it shows.\n"
    '- Label a part with a value the question states, with its unit ("12 m"), or with a '
    'letter your working uses ("r", "h", "x", "d", "θ"); the app adds the value it works '
    "out for that part. A number you worked out is left off unless the app can work it out "
    "too: for a best size (most area, least metal, largest volume) always give the amount "
    'the question fixes, as it states it, and the one to make best: "fixed": {"volume": '
    '"10 litres"}, "optimise": {"surface": "min"} (amounts: perimeter, area, surface, '
    "volume).\n"
    "- Use the question's own shape (a frustum is a frustum, a sphere is no circle). Leave "
    "out what the vocabulary cannot say. Never draw it in characters, Mermaid, SVG or a "
    "```geometry, ```graph or ```chart block, and do not mention the picture.\n"
    'kind "space" items: {"item":"axes"}; {"item":"point","name":"P","at":[x,y,z],'
    '"guides":true}; {"item":"vector","name":"a","to":[x,y,z]} from the origin, or '
    '"from":"A","to":"B"; {"item":"segment","from":"A","to":"B","label":"d"}; '
    '{"item":"polygon","vertices":["A","B","C"]}; {"item":"box","size":[x,y,z],'
    '"corners":{"O":[0,0,0],"G":[x,y,z]},"diagonals":["OG"]} (from the origin along the '
    'axes, each lettered corner at its coordinates); {"item":"sphere","name":"C",'
    '"center":[x,y,z],"radius":r} or {"item":"sphere","name":"C","equation":"..."}; '
    '{"item":"plane","through":'
    '["A","B","C"]}; {"item":"angle","at":"O","between":["a","b"],"label":"θ"}.\n'
    'kind "shape" items, each part a key whose value is its label: window (width, height, '
    "radius); rectangle (width, height); square (side); circle (radius); cylinder (radius, "
    "height); cone (radius, height, slant); sphere (radius); frustum (top_radius, "
    'bottom_radius, height); box (length, width, height, "open": true); sheet (length, '
    "width, cut: the squares cut from its corners); ladder (length, foot, top); tank "
    '("container": "cone" or "cylinder"; radius, height, depth, surface); inscribed (a '
    'cylinder in a "container": "cone" or "sphere"; outer_radius, outer_height, radius, '
    'height); polygon ("vertices": [{"name":"A","at":[x,y]}]).\n'
    'kind "plot" items, formulas and values as the question writes them, as text: '
    '{"item":"curve","name":"f","y":"x^2 - 5x + 1"} ("x":"9 - 2y^2" for x = g(y); '
    '"domain":["-2","2"] for a stated interval; a function in pieces: "pieces":[{"y":'
    '"x^2 - 4","when":"-2 < x < 3"}], each piece with its whole condition; an '
    'antiderivative with "shifts":["-1","0","1"] for the family F(x) + C; in the '
    'question\'s own letter, "y":"t^2 - 4t" for v(t)); '
    '{"item":"line","name":"L","y":"7"} or "x":"-3" (a line the question writes); '
    '{"item":"tangent","to":"f","at":"2"} and {"item":"normal","to":"f","at":"2"}; '
    '{"item":"asymptotes","of":"f"}; {"item":"points","of":"f","show":["extrema",'
    '"inflections","intercepts","ends","crossings"]}; {"item":"point","at":["2","1"]} (a '
    'point the question writes); {"item":"nearest","on":"f","to":["2","1"]}; {"item":'
    '"shade","between":["f","g"],"from":"-4","to":"1"} ("x-axis" as an edge; "wrt":"y" '
    "along y; no from and to for the region the edges enclose; three names for the region "
    'three edges enclose); {"item":"rectangles","under":"f","from":"1","to":"2","n":5,'
    '"rule":"left"} (left, right, midpoint, lower, upper); {"item":"average","of":"f",'
    '"from":"0","to":"3"} (the average value); {"item":"axes","x":"t (s)","y":"v (m/s)"} '
    '(the question\'s letters and units); {"item":"axis","line":"x-axis"} (the axis a '
    'region turns about, or "y = -1"); {"item":"slice","method":"washer"} (disc, washer or '
    "shell: one strip of the region and its turn about the axis). The app "
    "finds every crossing, turning point and asymptote itself and labels them; where a "
    "tangent touches or a bound may be a value your working finds, which the app checks.\n"
    'Example: "Find the angle between a = (1, 2, 2) and b = (2, 0, 1) and draw them." -> '
    '```draw\n{"kind":"space","items":[{"item":"axes"},{"item":"vector","name":"a",'
    '"to":[1,2,2]},{"item":"vector","name":"b","to":[2,0,1]},{"item":"angle","at":"O",'
    '"between":["a","b"],"label":"θ"}]}\n```\n'
    'Example: "Water fills a conical tank of radius 2 m and height 5 m; find dh/dt when '
    'the depth is 3 m. Draw the tank." -> ```draw\n{"kind":"shape","items":[{"item":"tank",'
    '"container":"cone","radius":"2 m","height":"5 m","depth":"h","surface":"r"}]}\n```\n'
    'Example: "A rectangular field is fenced with 400 m of fencing. Find the largest area '
    'and draw the field." -> ```draw\n{"kind":"shape","items":[{"item":"rectangle",'
    '"width":"x","height":"y","fixed":{"perimeter":"400 m"},"optimise":{"area":"max"}}]}'
    "\n```\n"
    'Example: "Find the area enclosed by y = 4 - x^2 and y = 3x. Shade the region." -> '
    '```draw\n{"kind":"plot","items":[{"item":"curve","name":"f","y":"4 - x^2"},{"item":'
    '"curve","name":"g","y":"3x"},{"item":"shade","between":["f","g"]},{"item":"points",'
    '"of":"f","show":["crossings"]}]}\n```'
)
