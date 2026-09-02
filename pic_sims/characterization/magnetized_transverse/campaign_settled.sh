#!/usr/bin/env bash
# The WIDE/LONG 10x follow-up (config_settled.yaml), strictly sequential:
#   b0_control (wide) -> transverse_1x (wide) -> cohort analysis under
#   acceptance_settled.yaml.  Campaign-level resume as campaign.sh: a
#   scenario with a COMPLETE run under THIS variant's study hash is skipped.
#
#   setsid nohup bash campaign_wide.sh > logs/campaign_settled_$(date -u +%Y%m%dT%H%M%SZ).log 2>&1 < /dev/null &
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PIC="$(cd "$HERE/../.." && pwd)"
CFG="$HERE/config_settled.yaml"
POLICY="$HERE/acceptance_settled.yaml"
ENV_NAME=warpx-cpu-mpich-dev
PYBIN="${PYBIN:-$HOME/miniforge3/envs/$ENV_NAME/bin/python}"
SIM="conda run --no-capture-output -n $ENV_NAME python"
MIN_FREE_GB="${MIN_FREE_GB:-12}"
mkdir -p "$HERE/logs"

stamp() { date -u +%Y%m%dT%H%M%SZ; }

check_disk() {
    local free
    free=$(df -BG --output=avail "$HERE" | tail -1 | tr -dc '0-9')
    if (( free < MIN_FREE_GB )); then
        echo "[settled $(stamp)] only ${free} GB free (< ${MIN_FREE_GB} GB): refusing to launch $1" >&2
        exit 3
    fi
}

find_complete() {
    "$PYBIN" - "$HERE" "$1" "$PIC" "$CFG" <<'PY'
import glob, json, os, sys
stage, scn, pic, cfgpath = sys.argv[1:5]
sys.path.insert(0, pic); sys.path.insert(0, stage)
import helpers, ladder_contract as lc
cfg = helpers.load_config(cfgpath, scenario=scn)
study = lc.config_sha256(cfg.study_config())
best = ""
for m in sorted(glob.glob(os.path.join(stage, "outputs", "2*", "manifest.json"))):
    try:
        j = json.load(open(m))
    except Exception:
        continue
    if (j.get("status") == "COMPLETE" and j.get("scenario") == scn
            and j.get("study_sha256") == study):
        best = os.path.dirname(m)
print(best)
PY
}

run_scenario() {
    local scn=$1 existing log rid
    existing=$(find_complete "$scn")
    if [[ -n "$existing" ]]; then
        echo "[settled $(stamp)] $scn: COMPLETE run exists, skipping ($existing)" >&2
        echo "$existing"; return
    fi
    check_disk "$scn"
    log="$HERE/logs/settled_${scn}_$(stamp).log"
    echo "[settled $(stamp)] launching $scn -> $log" >&2
    # The manifest, not the exit code, is the truth (ladder doctrine): a CUDA/
    # HDF5 teardown crash after COMPLETE is recorded must not kill the chain.
    rc=0
    ( cd "$HERE" && $SIM simulation.py --config "$CFG" --scenario "$scn" ) > "$log" 2>&1 || rc=$?
    rid=$(grep -m1 '^RUN_ID=' "$log" | cut -d= -f2 || true)
    if [[ -z "$rid" ]] || ! grep -q '"status": "COMPLETE"' "$HERE/outputs/$rid/manifest.json" 2>/dev/null; then
        echo "[settled $(stamp)] $scn FAILED (exit $rc, run ${rid:-none} not COMPLETE), see $log" >&2; exit 4
    fi
    if (( rc != 0 )); then
        echo "[settled $(stamp)] $scn: manifest COMPLETE but process exited $rc (teardown crash; evidence intact)" >&2
    fi
    echo "[settled $(stamp)] $scn COMPLETE: $rid" >&2
    echo "$HERE/outputs/$rid"
}

b0=$(run_scenario b0_control)
t10=$(run_scenario transverse_1x)
log="$HERE/logs/settled_analysis_$(stamp).log"
echo "[settled $(stamp)] analyzing -> $log" >&2
( cd "$HERE" && $SIM analyze.py --runs "$b0" "$t10" --policy "$POLICY" --config "$CFG" ) > "$log" 2>&1 || true
grep -E '^VERDICT|^ANALYSIS_ID|^\[(PASS|FAIL|ERROR|SKIP)' "$log" >&2 || true
echo "[settled $(stamp)] done" >&2
