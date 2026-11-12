#!/usr/bin/env bash
# Publish one bundle. Called from publish-npm.yml with DIR and TAG_PREFIX in the
# environment; cwd is the repository root.
#
# Kept deliberately plain: plain `[ ]` tests, one parameter expansion, jq for the
# version. An earlier inline version of this logic died on the runner with bash
# exit code 2 before it could print anything useful.
set -euo pipefail

dir="${DIR:?DIR is required}"
cd "$dir"

name="$(jq -r .name package.json)"
version="$(jq -r .version package.json)"
echo "publishing $name@$version from $dir (event: ${GITHUB_EVENT_NAME:-unknown})"

if [ "${GITHUB_EVENT_NAME:-}" = "push" ]; then
  ref="${GITHUB_REF_NAME:-}"
  prefix="${TAG_PREFIX:?TAG_PREFIX is required}"
  tag_version="${ref#"$prefix"}"
  echo "tag=$ref prefix=$prefix implies=$tag_version"
  if [ "$tag_version" = "$ref" ]; then
    echo "::error::tag $ref does not start with $prefix"
    exit 1
  fi
  if [ "$tag_version" != "$version" ]; then
    echo "::error::tag $ref implies $tag_version but $dir/package.json is $version"
    exit 1
  fi
fi

node --version
npm --version

echo "--- npm publish ---"
npm publish --access public

echo "--- registry check ---"
npm view "$name@$version" version dist-tags dist.attestations --json || true
