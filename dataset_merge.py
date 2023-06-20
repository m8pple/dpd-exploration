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
from contextlib import ExitStack

from dataset import command_line_dataset_open_helper

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_merge.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    if dataset.matrix_dirty_count==0:
        sys.stderr.write("Dataset is already merged\n")    
    else:
        sys.stderr.write(f"Flushing merged dataset to disk. New = {dataset.matrix_dirty_count}, Total = {dataset.matrix.nExperiments}\n")

    dataset.flush()
