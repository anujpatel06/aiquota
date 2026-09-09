#!/bin/bash
# Full pre-release verification. Any failure here should block the tag.
set -e
ROOT="$(cd "$ROOT" && pwd)"
cd "$ROOT"
FAIL=0
ok(){ echo "  PASS  $1"; }
bad(){ echo "  FAIL  $1"; FAIL=1; }

echo "=== 1. test suite ==="
if python3 -m unittest discover -s tests -q 2>&1 | tail -1 | grep -q "^OK"; then
  ok "$(python3 -m unittest discover -s tests 2>&1 | grep -o 'Ran [0-9]* tests')"
else bad "tests"; fi

echo
echo "=== 2. version consistency ==="
V1=$(python3 -c "import aiquota; print(aiquota.__version__)")
V2=$(grep '^version = ' pyproject.toml | cut -d'"' -f2)
[ "$V1" = "$V2" ] && ok "version $V1 in both" || bad "version mismatch $V1 vs $V2"

echo
echo "=== 3. shipped widget matches repo ==="
if diff -q aiquota/widgets/aiquota.jsx widgets/ubersicht/aiquota.jsx >/dev/null; then
  ok "packaged widget is current"; else bad "packaged widget is stale"; fi

echo
echo "=== 4. widget compiles ==="
if npx --yes esbuild@0.21.5 --loader:.jsx=jsx --log-level=error \
     widgets/ubersicht/aiquota.jsx --outfile=/dev/null 2>/dev/null; then
  ok "JSX compiles"; else bad "JSX syntax error"; fi

echo
echo "=== 5. build wheel + sdist ==="
rm -rf dist build ./*.egg-info
python3 -m pip wheel . -w dist --no-deps -q 2>/dev/null
WHL=$(ls dist/*.whl 2>/dev/null | head -1)
[ -n "$WHL" ] && ok "wheel: $(basename "$WHL")" || bad "no wheel built"

echo
echo "=== 6. wheel contains widgets + logos ==="
N=$(unzip -l "$WHL" | grep -c "aiquota/widgets/")
[ "$N" -ge 4 ] && ok "$N widget files shipped" || bad "widgets missing from wheel ($N)"
unzip -l "$WHL" | grep -q "assets/logos.json" && ok "logo bundle shipped" || bad "logos missing"

echo
echo "=== 7. clean-venv install, no repo on path ==="
rm -rf /tmp/relcheck && python3 -m venv /tmp/relcheck
/tmp/relcheck/bin/pip install -q --upgrade pip
/tmp/relcheck/bin/pip install -q "$WHL"
cd /tmp
VER=$(/tmp/relcheck/bin/aiquota --version 2>&1)
[ "$VER" = "aiquota $V1" ] && ok "--version: $VER" || bad "--version: $VER"
for b in aiquota aiquota-picker aiquota-remove; do
  [ -x "/tmp/relcheck/bin/$b" ] && ok "binary $b" || bad "binary $b missing"
done
/tmp/relcheck/bin/python -c "
import os, sys
from aiquota import install_widget as iw
sys.exit(0 if os.path.isdir(iw.SRC) and len(os.listdir(iw.SRC))>=4 else 1)
" && ok "widgets findable at runtime" || bad "widgets not findable"

echo
echo "=== 8. no fabricated data in the repo ==="
cd "$ROOT"
# The real risk is a non-live tier rendering as live. A test enforces it;
# confirm that test exists and passes rather than grepping for numbers.
if python3 -m unittest tests.test_aiquota -k tier 2>&1 | tail -1 | grep -q "^OK"; then
  ok "tier-honesty tests pass (no manual value can show as live)"
else bad "tier-honesty tests"; fi

echo
echo "=== 9. README images exist ==="
for f in docs/img/widget.png docs/img/picker.png; do
  [ -s "$f" ] && ok "$f ($(du -h "$f" | cut -f1))" || bad "$f missing"
done

rm -rf /tmp/relcheck
echo
[ $FAIL -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $FAIL
