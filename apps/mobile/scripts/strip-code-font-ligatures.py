"""Strip the substitutions that change what code says from the code face (Space Mono).

React Native's new architecture drops `fontVariant` ligature and contextual settings on iOS
(`attributedstring/conversions.h` returns nullopt for them), so `no-common-ligatures` never
reached the font: `fib` drew as "ﬁb" and Space Mono's `calt` drew `->` as an arrow, so
`def f(s: str) -> str:` read "s: str) → str" (iOS Simulator, 2026-11-07). The font itself now
carries no `liga`, `dlig` or `calt`, on every platform. Space Mono is SIL OFL 1.1 with no
Reserved Font Name; the license travels with it (assets/fonts/SpaceMono-OFL.txt).

Run from apps/mobile: python3 scripts/strip-code-font-ligatures.py
"""

from fontTools.ttLib import TTFont

PATH = "assets/fonts/SpaceMono-Regular.ttf"
DROPPED = {"liga", "dlig", "calt", "clig", "rlig"}

font = TTFont(PATH)
gsub = font["GSUB"].table
kept = [i for i, rec in enumerate(gsub.FeatureList.FeatureRecord) if rec.FeatureTag not in DROPPED]
remap = {old: new for new, old in enumerate(kept)}
gsub.FeatureList.FeatureRecord = [gsub.FeatureList.FeatureRecord[i] for i in kept]
gsub.FeatureList.FeatureCount = len(kept)
for script in gsub.ScriptList.ScriptRecord:
    langs = [script.Script.DefaultLangSys] + [rec.LangSys for rec in script.Script.LangSysRecord]
    for lang in filter(None, langs):
        lang.FeatureIndex = [remap[i] for i in lang.FeatureIndex if i in remap]
        lang.FeatureCount = len(lang.FeatureIndex)
# The signature covered the font as shipped; edited, it no longer holds, so it goes.
if "DSIG" in font:
    del font["DSIG"]
font.save(PATH)
print("kept features:", sorted({rec.FeatureTag for rec in gsub.FeatureList.FeatureRecord}))
