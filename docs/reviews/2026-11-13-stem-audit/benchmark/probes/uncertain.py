import asyncio
from app.core.config import Settings
from app.gateways import mathpix_gateway
from app.modules.math import ocr, image_extract as mie
from app.modules.math.schemas import MathImageExtract
s = Settings(_env_file=None, database_url="postgresql+asyncpg://x/x", jwt_secret="x"*40, mock_llm_enabled=False, mathpix_app_id="a", mathpix_app_key="b")
async def fake_mathpix(settings, *, content_type, data):
    return mathpix_gateway.MathpixOcrResult(text="2x + 3 = 1", latex="2x + 3 = 1", confidence=0.31)
async def fake_vision(settings, **kw):
    return MathImageExtract(kind="equation", lhs="2*x+3", rhs="1", variables=["x"], found=True, source_text="2x + 3 = 1")
mathpix_gateway.ocr_image = fake_mathpix
mie.vision_extract_equation = fake_vision
async def main():
    r = await ocr.extract_math_from_image(s, content_type="image/jpeg", data=b"x")
    print("ocr result: source=", r.source, "confidence=", r.confidence, "uncertain=", r.uncertain)
    e = await mie.extract_equation_from_image(s, content_type="image/jpeg", data=b"x")
    print("turn-path extract:", e and (e.lhs, e.rhs), "-> uncertainty is not carried (", type(e).__name__, ")")
    print("suffix sent to the turn:", mie.camera_math_user_suffix(e))
asyncio.run(main())
