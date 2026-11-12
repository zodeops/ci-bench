#!/usr/bin/env bash
# Mirror one benchmark repository into zodeops/bench-<name> at its pinned
# commit (repos.json), with the measured workflow made benchable
# (scripts/benchify.py) and every other workflow removed.
#
#   scripts/mirror.sh <name>      e.g. scripts/mirror.sh helm
#
# The mirror's history is two commits: the upstream tree unchanged (one root
# commit naming the upstream SHA) and the bench edit, so `git show HEAD` is
# the whole difference from upstream. Branches main, bench-github and
# bench-zode point at the same commit; each provider runs on its own branch,
# so its Actions caches and concurrency group never meet the other's.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
name=$1
read -r upstream commit workflow tag < <(python3 - "$here/repos.json" "$name" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
r = next(r for r in d["repos"] if r["name"] == sys.argv[2])
if r.get("own_workflow"):
    sys.exit("%s is ci-bench's own workflow; nothing to mirror" % r["name"])
print(r["upstream"], r["commit"], r["workflow"], r.get("tag", "-"))
PY
)
mirror="zodeops/bench-$name"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cd "$work"
git init -q -b main
git config user.name "Zode ci-bench"
git config user.email "ci-bench@zode.dev"
git remote add up "https://github.com/$upstream.git"
git fetch -q --depth 1 up "$commit"
tree=$(git rev-parse "FETCH_HEAD^{tree}")
root=$(git commit-tree "$tree" -m "$upstream@$commit, unchanged

Upstream tree at https://github.com/$upstream/commit/$commit.")
git reset -q --hard "$root"
# Builds that run `git describe` (fzf's Makefile) need the upstream release
# tag the commit descends from; it goes on the unchanged upstream tree.
if [ "$tag" != "-" ]; then
  git tag -a "$tag" -m "$tag: nearest upstream release tag of $commit" "$root"
fi
wf=".github/workflows/$workflow"
[ -f "$wf" ] || { echo "no $wf in $upstream@$commit" >&2; exit 1; }
find .github/workflows -maxdepth 1 -type f \( -name '*.yml' -o -name '*.yaml' \) ! -name "$workflow" -print0 | xargs -0r git rm -q
python3 "$here/scripts/benchify.py" "$wf"
git add -A
git commit -q -m "bench: $workflow runs on the runner input, by workflow_dispatch only

Two edits to the upstream workflow: every runs-on takes inputs.runner, and
the trigger is workflow_dispatch. Other workflow files are removed so
nothing else runs. See zodeops/ci-bench."
if ! gh repo view "$mirror" >/dev/null 2>&1; then
  gh repo create "$mirror" --public --disable-wiki --disable-issues \
    --description "ci-bench mirror of $upstream at ${commit:0:12} (Zode CI benchmark)" >/dev/null
fi
git remote add origin "https://github.com/$mirror.git"
git push -q -f origin HEAD:main HEAD:bench-github HEAD:bench-zode
[ "$tag" = "-" ] || git push -q -f origin "refs/tags/$tag"
echo "$mirror $(git rev-parse --short HEAD) $upstream@${commit:0:12}"
