#!/bin/bash
#SBATCH --job-name=cutrep-score
#SBATCH --partition=m9g
#SBATCH --gpus=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=48G
#SBATCH --time=05:00:00
#SBATCH --array=0-43
#SBATCH --output=/home/%u/cutoff_rep_20261027/log/%x-%A_%a.out
# tasks 0-39: SLOWING over the units (40 shards); tasks 40-43: SLEEPPSG over the PSG studies (4 shards)
ulimit -c 0
module load python/3.11 >/dev/null 2>&1
module load cuda/12.1.1-2gn2j4j >/dev/null 2>&1
cd $HOME/cutoff_rep_20261027
export PYTHONWARNINGS=ignore TMPDIR=${TMPDIR:-/tmp}
PY=$HOME/morgoth-bench/venv311/bin/python
OUT=/nobackup/archive/usr/$USER/cutoff_rep_20261027/scores_v1
sha256sum score_models.py
i=$SLURM_ARRAY_TASK_ID
if [ $i -lt 40 ]; then
  $PY score_models.py --mode slowing --data $HOME/n3_vs_grda/data --out $OUT --ntasks 40 --task $i
else
  $PY score_models.py --mode sleep --data $HOME/n3_vs_grda/data --out $OUT --ntasks 4 --task $((i - 40))
fi
