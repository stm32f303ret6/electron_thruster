#!/bin/bash
# HISTORICAL LAUNCH RECORD -- paths below reflect the pre-2026-08-11 layout
# (variant decks under the anchor stage).  The deck(s) now live in thin_plasma/
# as config.yaml; to re-run today, use that stage folder's simulation.py.
# thin_plasma chain: the pre-registered density-axis run (THIN_PLASMA_PLAN.md),
# analyzed under the exploratory policy on completion.
source /home/rsc/miniforge3/etc/profile.d/conda.sh
conda activate warpx-cpu-mpich-dev
set -u

STAGE=/home/rsc/Desktop/repos/warpequisd/electron_thruster_3/pic_sims/validation_cases/capstone/2_chipsat_thruster
LOG_DIR=$STAGE/variants/thin_plasma_logs
mkdir -p "$LOG_DIR"
log() { echo "[$(date -u +%H:%M:%S)] $*"; }
newest_run() { ls -td "$STAGE"/outputs/*/ 2>/dev/null | head -1 | sed 's:/$::'; }
is_complete() { grep -q '"status": "COMPLETE"' "$1/manifest.json" 2>/dev/null; }

cd "$STAGE"
tag=thin_plasma
log "$tag: starting simulation"
python simulation.py --config "$STAGE/variants/$tag.yaml" > "$LOG_DIR/$tag.log" 2>&1
rc=$?
run=$(newest_run)
log "$tag: exit $rc, run $run"
if [ -n "$run" ] && is_complete "$run"; then
    log "$tag analysis (exploratory policy): starting"
    python analyze.py --run "$run" --policy acceptance_exploratory.yaml \
        > "$LOG_DIR/${tag}_analysis.log" 2>&1
    log "$tag analysis: exit $?"
else
    log "$tag: NOT COMPLETE -- analysis skipped"
fi
log "THIN PLASMA CHAIN DONE"
