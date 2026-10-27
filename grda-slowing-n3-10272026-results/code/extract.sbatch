#!/bin/bash
#SBATCH --job-name=cutrep-extract
#SBATCH --cpus-per-task=64
#SBATCH --mem=200G
#SBATCH --time=04:00:00
#SBATCH --output=/home/%u/cutoff_rep_20261027/log/%x-%j.out
# usage: sbatch extract.sbatch <scores dir name under cutoff_rep_20261027> <new output dir name>
module load python/3.11 >/dev/null 2>&1
cd $HOME/cutoff_rep_20261027
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=$HOME/morgoth-bench/venv311/bin/python
B=/nobackup/archive/usr/$USER/cutoff_rep_20261027
sha256sum extract_minutes.py
$PY extract_minutes.py --data $HOME/n3_vs_grda/data --scores $B/$1 --out $B/$2 --workers 64 --sides "${3:-GN}"
