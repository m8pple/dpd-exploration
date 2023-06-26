#!/usr/bin/env python3
import sys
import argparse
import uuid
from pathlib import Path
import subprocess
import shutil
import random
from dataclasses import dataclass
import multiprocessing
import os
import bz2
import zipfile
import tempfile
import getpass
import datetime
from contextlib import ExitStack

from dataset import DMPCITemplate, Dataset, parse_dmpcas, command_line_dataset_open_helper



if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_run_samples.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("job_run_time", nargs="?", default="2:00:00", help="Time to allocate to the task in dd-HH:MM:SS format.")
    parser.add_argument("num_tasks", nargs="?", default=1, help="Number of tasks to enqueue.")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    parser.add_argument("--dpd-path", default="dpd", type=str, help="Give the path to the osprey dpd executable, or the name of a comand that is accessible on PATH.")
    parser.add_argument("--tags", default="random", type=str, help='List of comma separated tags to assigned to samples.')
    parser.add_argument("--repeats-per-cpu", default=1, type=int, help='Number of random simulation runs to perform per core.')
    parser.add_argument("--render-povray", default=False, action='store_true', help="Render the pov files using povray and then add into the output zip.")
    parser.add_argument("--keep-pov", default=False, action='store_true', help='Store compressed pov files into zip')
    parser.add_argument("--keep-rst", default=False, action='store_true', help='Store compressed rst files into zip')
    parser.add_argument("--keep-dat", default=False, action='store_true', help='Store compressed dat files into zip')
    parser.add_argument("--preserve-working", default=False, action='store_true', help='Dont delete the working directory when the run finishes.')
    parser.add_argument("--working-dir", default=None, help="Directory to create temporary directories in, and aso  If nothing is specified then '/scratch/{USER}/dpd_explore_temp/{RUN_ID}/{DATE}' is used")

    args=parser.parse_args()

    dpd_path=Path(args.dpd_path)
    if dpd_path.exists():
        dpd_path=dpd_path.absolute()
    else:
        p = shutil.which(dpd_path)
        if p is None:
            sys.stderr.write(f"dpd-path of '{dpd_path}' doesn't appear to exist as a file, and doesn't resolve use PATH lookup\n")
            sys.exit(1)
        dpd_path=Path(p).absolute()

    assert dpd_path.is_absolute()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)
    dataset_dir=dataset_dir.resolve()
    assert dataset_dir.is_dir()

    today=datetime.datetime.today()
    today_str=today.strftime("%Y-%m-%d--%H-%M-%S")
    if args.working_dir is None:
        working_dir = Path(f"/scratch/{getpass.getuser()}/dpd_explore_temp/{dataset.id}/{today_str}")
        working_dir.mkdir(exist_ok=False,parents=True)
    else:
        working_dir = Path(args.working_dir)
        working_dir.mkdir(exist_ok=True,parents=True)

    job_run_time=args.job_run_time

    dpd_exploration_dir=os.path.abspath( os.path.dirname(sys.argv[0]) )

    jobfile=working_dir / f"job-{dataset.id}-{today_str}.sh"
    with open(jobfile,"wt") as dst:
        dst.write(
f'''\
#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --exclusive     # Request all cores on the node, without specifying exactly (AMD and Intel nodes have different core count)
#SBATCH --mem=32000      # Can't imagine it taking more than 32GB even with 64 cores (famous last words...)
#SBATCH --time={job_run_time}

>&2 echo "SLURM_CPUS_ON_NODE=$SLURM_CPUS_ON_NODE"

REPEATS=$(( SLURM_CPUS_ON_NODE * {args.repeats_per_cpu} ))
>&2 echo "Requesting $REPEATS samples in total"

cd {dpd_exploration_dir}
python3 dataset_run_samples.py "{dataset_dir}" --dpd-path="{dpd_path}" --tags="{args.tags}" --repeats="$REPEATS" --num-processes="$SLURM_CPUS_ON_NODE" --working-dir="{working_dir}" \
    {"--render-povray" if args.render_povray else "" } \
    {"--keep-pov" if args.keep_pov else "" } \
    {"--keep-rst" if args.keep_rst else "" } \
    {"--keep-dat" if args.keep_dat else "" } \
    {"--preserve-working" if args.preserve_working else "" } \

'''
        )

    for i in range(int(args.num_tasks)):
        os.system(f"sbatch {jobfile}")