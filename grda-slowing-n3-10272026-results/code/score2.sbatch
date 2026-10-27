#!/bin/bash
#SBATCH --job-name=cutrep-score2
#SBATCH --partition=m9g
#SBATCH --gpus=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --array=28-43
#SBATCH --output=/home/%u/cutoff_rep_20261027/log/%x-%A_%a.out
# The shards of score.sbatch that never started (28-39 SLOWING, 40-43 SLEEPPSG), each split over 3 processes on its GPU
# (the per-unit time is mostly CPU preprocessing and .mat I/O, so the GPU was idle most of the time).
ulimit -c 0
module load python/3.11 >/dev/null 2>&1
module load cuda/12.1.1-2gn2j4j >/dev/null 2>&1
cd $HOME/cutoff_rep_20261027
export PYTHONWARNINGS=ignore TMPDIR=${TMPDIR:-/tmp} OMP_NUM_THREADS=2
PY=$HOME/morgoth-bench/venv311/bin/python
OUT=/nobackup/archive/usr/$USER/cutoff_rep_20261027/scores_v1
sha256sum score_models.py
i=$SLURM_ARRAY_TASK_ID
for k in 0 1 2; do
  if [ $i -lt 40 ]; then
    $PY score_models.py --mode slowing --data $HOME/n3_vs_grda/data --out $OUT --ntasks 40 --task $i --nsub 3 --sub $k --batch 768 &
  else
    $PY score_models.py --mode sleep --data $HOME/n3_vs_grda/data --out $OUT --ntasks 4 --task $((i - 40)) --nsub 3 --sub $k --batch 768 &
  fi
done
wait
