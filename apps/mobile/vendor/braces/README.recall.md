Vendored `braces` for Metro and Jest (`micromatch` → `braces@3.0.3`).

Upstream has no release past 3.0.3 that limits brace nesting (GHSA-vfj7-8cjw-p6xm).
This copy is 3.0.3 plus the depth guard from micromatch/braces#72, and reports
version 3.0.4 so Dependabot’s `<= 3.0.3` range clears.

Remove when upstream publishes a patched release and Metro adopts it.
