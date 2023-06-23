#!/usr/bin/env python3
import sys
import argparse
import numpy as np
import zipfile
import math
import io
import scipy.spatial
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageOps
from pathlib import Path
from dataset import command_line_dataset_open_helper
from dataset import DMPCIParameter, Dataset

from dataset_extract_snapshot_slice import create_2d_mosaic_from_slice_ids, find_2d_parameter_slice_ids

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "extract_all_snapshot_slices.py",
        description=
"""
Extract all combinations of output snapshot slices.
Files will be of the form:
  {output_prefix}_{param1}_{param2}.png
"""
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("output_prefix", help="Prefix of the image files to create")
    parser.add_argument("width", nargs="?", default=None, help="Number of images along x. Default is max(3, min(10, ceil(pow(nSamples,1.3/d))))")
    parser.add_argument("height", nargs="?", default=None, help="Number of images along y. Default is max(3, min(10, ceil(pow(nSamples,1.3/d))))")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    if dataset.matrix==None:
        sys.stderr.write("Dataset is empty.\n")
        sys.exit(1)

    output_prefix=Path(args.output_prefix)

    time=dataset.matrix.times[-1]

    n=dataset.matrix.nExperiments
    d=dataset.matrix.nParameters

    if args.width is None:
        width = max( 3, min( 10, math.ceil( math.pow(n, 1.3/d) ) ) )
    else:
        width = int( args.width )

    if args.height is None:
        height = max( 3, min( 10, math.ceil( math.pow(n, 1.3/d) ) ) )
    else:
        height = int( args.height )

    sel_scale=d
    sys.stderr.write(f"Scaling up x and y parameters by {sel_scale} for distance search\n")


    for i1 in range(0,d-1):
        x_param = dataset.get_parameter(i1)
        for i2 in range(i1+1,d):
            y_param = dataset.get_parameter(i2)

            #################################################################
            ## Work out samples closest to the target point

            xy_map_to_eid = find_2d_parameter_slice_ids(dataset, sel_scale, x_param, y_param, width, height)


            ################################################################
            ## Extract all the images for the samples and crop them

            res = create_2d_mosaic_from_slice_ids(dataset, time, xy_map_to_eid)

            ###############################################################
            ## Now write it out
                
            res.save( f"{output_prefix}__{x_param.name}__{y_param.name}.png" )
