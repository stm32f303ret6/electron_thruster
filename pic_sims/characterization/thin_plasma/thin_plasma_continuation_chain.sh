#!/bin/bash
# thin_plasma continuation chain (2026-08-11): the 2.4 us run of
# THIN_PLASMA_PLAN.md "CONTINUATION" section.  Runs the stage deck
# (config.yaml, already carrying t_end 2.4e-6 / max_steps 480000 /
# phi_ceiling 180) from scratch, then analyzes under acceptance.yaml.
source /home/rsc/miniforge3/etc/profile.d/conda.sh
conda activate warpx-cpu-mpich-dev
set -u

STAGE=/home/rsc/Desktop/repos/warpequisd/electron_thruster_3/pic_sims/characterization/thin_plasma
LOG_DIR=$STAGE/logs
mkdir -p "$LOG_DIR"
log() { echo "[$(date -u +%H:%M:%S)] $*"; }
newest_run() { ls -td "$STAGE"/outputs/*/ 2>/dev/null | head -1 | sed 's:/$::'; }
is_complete() { grep -q '"status": "COMPLETE"' "$1/manifest.json" 2>/dev/null; }

cd "$STAGE"
tag=thin_plasma_continuation
log "$tag: starting simulation (t_end 2.4 us)"
python simulation.py > "$LOG_DIR/$tag.log" 2>&1
rc=$?
run=$(newest_run)
log "$tag: exit $rc, run $run"
if [ -n "$run" ] && is_complete "$run"; then
    log "$tag analysis (exploratory policy): starting"
    python analyze.py --run "$run" --policy acceptance.yaml \
        > "$LOG_DIR/${tag}_analysis.log" 2>&1
    log "$tag analysis: exit $?"
else
    log "$tag: NOT COMPLETE -- analysis skipped"
fi
log "THIN PLASMA CONTINUATION CHAIN DONE"
