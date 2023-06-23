#!/usr/bin/env python3
import sys
import argparse
import numpy as np
import zipfile
from pathlib import Path
from dataset import command_line_dataset_open_helper

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "extract_snapshots.py"
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("output_dir", help="Where to put all the images")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    if dataset.matrix==None:
        sys.stderr.write("Dataset is empty.\n")
        sys.exit(1)

    output_dir=Path(args.output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    time=dataset.matrix.times[-1]

    for ei in np.nditer(dataset.matrix.experiments[0:dataset.matrix.nExperiments], flags=("refs_ok",)):
        with zipfile.ZipFile( dataset.dir / f"{ei}.zip" ) as zip:
            fn = f"dmpccs.{ei}.con.{time}.png"
            bytes=zip.read(f"{ei}/{fn}")
            ( output_dir / fn ).write_bytes(bytes)
