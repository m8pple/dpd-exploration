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

from dataset import DMPCITemplate, Dataset

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "dataset_create.py"
    )
    parser.add_argument("dmpci_template")
    parser.add_argument("dataset_dir", nargs="?", default=None, help="Path to new dataset directory. Default is '${default_dataset_root}/${dataset_id}'")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")

    args=parser.parse_args()

    dmpci_template_path=Path(args.dmpci_template)
    template=DMPCITemplate(dmpci_template_path)

    if args.dataset_dir == None:
        dataset_path = Path(args.default_dataset_root) / template.run_id
    else:
        dataset_path = Path(args.dataset_dir)

    Dataset.init_or_open_dataset_from_template(template, dataset_path)

