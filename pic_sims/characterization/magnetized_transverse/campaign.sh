#!/usr/bin/env bash
# The transverse-B campaign, strictly sequential on one GPU:
#   numerics mini-ladder (gyro_1x, gyro_10x, exb_10x) -> analysis
#   measurement (b0_control, transverse_1x, transverse_10x) -> cohort analysis
# Campaign-level resume: a scenario that already has a COMPLETE run under
# outputs/ for the CURRENT study hash is not rerun (runs themselves are never
# resumed -- pic_sims/ARCHITECTURE.md).  Each launch is armed on the previous
# manifest carrying the literal "status": "COMPLETE" and on free disk.
#
#   bash campaign.sh                 # foreground
#   setsid nohup bash campaign.sh > logs/campaign_$(date -u +%Y%m%dT%H%M%SZ).log 2>&1 < /dev/null &
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NUM="$(cd "$HERE/../transverse_b_numerics" && pwd)"
PIC="$(cd "$HERE/../.." && pwd)"
ENV_NAME=warpx-cpu-mpich-dev
PYBIN="${PYBIN:-$HOME/miniforge3/envs/$ENV_NAME/bin/python}"
SIM="conda run --no-capture-output -n $ENV_NAME python"
MIN_FREE_GB="${MIN_FREE_GB:-6}"
mkdir -p "$HERE/logs" "$NUM/logs"

stamp() { date -u +%Y%m%dT%H%M%SZ; }

check_disk() {
    local free
    free=$(df -BG --output=avail "$HERE" | tail -1 | tr -dc '0-9')
    if (( free < MIN_FREE_GB )); then
        echo "[campaign $(stamp)] only ${free} GB free (< ${MIN_FREE_GB} GB): refusing to launch $1" >&2
        exit 3
    fi
}

# newest COMPLETE run of <stage dir> <scenario> under the current study hash, or ""
find_complete() {
    "$PYBIN" - "$1" "$2" "$PIC" <<'PY'
import glob, json, os, sys
stage, scn, pic = sys.argv[1:4]
sys.path.insert(0, pic); sys.path.insert(0, stage)
import helpers, ladder_contract as lc
cfg = helpers.load_config(os.path.join(stage, "config.yaml"), scenario=scn)
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

run_scenario() {   # <stage dir> <scenario>  -> prints the COMPLETE run dir
    local stage=$1 scn=$2 existing log rid
    existing=$(find_complete "$stage" "$scn")
    if [[ -n "$existing" ]]; then
        echo "[campaign $(stamp)] $scn: COMPLETE run exists, skipping ($existing)" >&2
        echo "$existing"; return
    fi
    check_disk "$scn"
    log="$stage/logs/${scn}_$(stamp).log"
    echo "[campaign $(stamp)] launching $scn -> $log" >&2
    # The manifest, not the exit code, is the truth (ladder doctrine): a CUDA/
    # HDF5 teardown crash after COMPLETE is recorded must not kill the chain.
    rc=0
    ( cd "$stage" && $SIM simulation.py --scenario "$scn" ) > "$log" 2>&1 || rc=$?
    rid=$(grep -m1 '^RUN_ID=' "$log" | cut -d= -f2 || true)
    if [[ -z "$rid" ]] || ! grep -q '"status": "COMPLETE"' "$stage/outputs/$rid/manifest.json" 2>/dev/null; then
        echo "[campaign $(stamp)] $scn FAILED (exit $rc, run ${rid:-none} not COMPLETE), see $log" >&2; exit 4
    fi
    if (( rc != 0 )); then
        echo "[campaign $(stamp)] $scn: manifest COMPLETE but process exited $rc (teardown crash; evidence intact)" >&2
    fi
    echo "[campaign $(stamp)] $scn COMPLETE: $rid" >&2
    echo "$stage/outputs/$rid"
}

analyze() {        # <stage dir> <run dirs...>
    local stage=$1; shift
    local log="$stage/logs/analysis_$(stamp).log"
    echo "[campaign $(stamp)] analyzing $(basename "$stage") -> $log" >&2
    ( cd "$stage" && $SIM analyze.py --runs "$@" --policy acceptance.yaml ) > "$log" 2>&1 || true
    grep -E '^VERDICT|^ANALYSIS_ID|^\[(PASS|FAIL|ERROR|SKIP)' "$log" >&2 || true
}

# ---- 1. the numerics mini-ladder ----
g1=$(run_scenario "$NUM" gyro_1x)
g10=$(run_scenario "$NUM" gyro_10x)
ex=$(run_scenario "$NUM" exb_10x)
analyze "$NUM" "$g1" "$g10" "$ex"

# ---- 2. the measurement cohort ----
b0=$(run_scenario "$HERE" b0_control)
analyze "$HERE" "$b0"                       # a look at the control before the field runs
t1=$(run_scenario "$HERE" transverse_1x)
t10=$(run_scenario "$HERE" transverse_10x)
analyze "$HERE" "$b0" "$t1" "$t10"
echo "[campaign $(stamp)] done" >&2
