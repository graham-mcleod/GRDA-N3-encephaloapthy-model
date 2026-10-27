#!/bin/bash
#SBATCH --job-name=cutrep-sleep
#SBATCH --partition=m9g
#SBATCH --gpus=1
#SBATCH --cpus-per-task=7
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH --output=/home/%u/cutoff_rep_20261027/log/%x-%j.out
# all four SLEEPPSG shards at once on one GPU (replaces score2 tasks 40-43)
ulimit -c 0
module load python/3.11 >/dev/null 2>&1
module load cuda/12.1.1-2gn2j4j >/dev/null 2>&1
cd $HOME/cutoff_rep_20261027
export PYTHONWARNINGS=ignore TMPDIR=${TMPDIR:-/tmp} OMP_NUM_THREADS=1
PY=$HOME/morgoth-bench/venv311/bin/python
OUT=/nobackup/archive/usr/$USER/cutoff_rep_20261027/scores_v1
for t in 0 1 2 3; do for k in 0 1; do
  $PY score_models.py --mode sleep --data $HOME/n3_vs_grda/data --out $OUT --ntasks 4 --task $t --nsub 2 --sub $k --batch 512 &
done; done
wait
