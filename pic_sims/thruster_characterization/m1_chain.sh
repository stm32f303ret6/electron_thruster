#!/bin/bash
# HISTORICAL LAUNCH RECORD -- paths below reflect the pre-2026-08-11 layout
# (variant decks under the anchor stage).  The deck(s) now live in magnetized_1x/ and magnetized_10x/
# as config.yaml; to re-run today, use that stage folder's simulation.py.
# M1 chain: two field-aligned magnetized variants of the 200 V anchor,
# strictly sequential (one GPU), analyzed under the exploratory policy.
source /home/rsc/miniforge3/etc/profile.d/conda.sh
conda activate warpx-cpu-mpich-dev
set -u

STAGE=/home/rsc/Desktop/repos/warpequisd/electron_thruster_3/pic_sims/validation_cases/capstone/2_chipsat_thruster
LOG_DIR=/home/rsc/Desktop/repos/warpequisd/electron_thruster_3/pic_sims/validation_cases/capstone/2_chipsat_thruster/variants/m1_logs
mkdir -p "$LOG_DIR"
log() { echo "[$(date -u +%H:%M:%S)] $*"; }
newest_run() { ls -td "$STAGE"/outputs/*/ 2>/dev/null | head -1 | sed 's:/$::'; }
is_complete() { grep -q '"status": "COMPLETE"' "$1/manifest.json" 2>/dev/null; }

cd "$STAGE"
for tag in m1a_bz_1x m1b_bz_10x; do
    log "$tag: starting simulation"
    python simulation.py --config "/home/rsc/Desktop/repos/warpequisd/electron_thruster_3/pic_sims/validation_cases/capstone/2_chipsat_thruster/variants/$tag.yaml" > "$LOG_DIR/$tag.log" 2>&1
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
done
log "M1 CHAIN DONE"
