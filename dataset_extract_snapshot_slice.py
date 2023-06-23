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

def crop_image_whitespace(img):
    neg=ImageOps.invert(img)
    bbox=neg.getbbox()
    assert(bbox is not None)
    return img.crop(bbox)

def find_2d_parameter_slice_ids(dataset:Dataset, sel_scale:float, x_param:DMPCIParameter, y_param:DMPCIParameter, width:int, height:int):
    """
    sel_scale is a factor that increases the weight of the selected parameters when finding the closest point.
    With many dimensions the closest point can often be somewhere else that is a long way from the
    desired point, so we want to increase the importance of being close to the selected parameters rather
    than the mid-point of the unselected ranges.
    """
    adjusted = dataset.matrix.configurations.copy()
    adjusted[ :, x_param.index ] *= sel_scale
    adjusted[ :, y_param.index ] *= sel_scale

    kd=scipy.spatial.KDTree(adjusted)

    target = np.array( [ (p.minval+p.maxval)/2 for p in dataset.template.parameters.values()  ] , dtype=np.float64)

    x0 = x_param.minval
    dx = (x_param.maxval - x_param.minval) / (width-1)

    y0 = y_param.minval
    dy = (y_param.maxval - y_param.minval) / (height-1)

    xy_map_to_eid = {} # type: Dict[Tuple[int,int],str]
    for xi in range(0,width):
        target[x_param.index] = ( x0 + dx * xi ) * sel_scale
        for yi in range(0,height):
            target[y_param.index] = ( y0 + dy * yi ) * sel_scale
            (_,idx)=kd.query(target)
            pt=dataset.matrix.configurations[idx,:]
            eid=dataset.matrix.experiments[idx]

            real_target=target.copy()
            real_target[x_param.index] /= sel_scale
            real_target[y_param.index] /= sel_scale
            sys.stderr.write(f"({xi},{yi}) -> {real_target} -> {pt} -> {eid}\n")

            xy_map_to_eid[(xi,yi)] = eid
    return xy_map_to_eid

def create_2d_mosaic_from_slice_ids(dataset, time, xy_map_to_eid:Dict[Tuple[int,int],str], width:Optional[int]=None, height:Optional[int]=None):
    if width is None or height is None:
        max_x = -1
        max_y = -1
        for (x,y) in xy_map_to_eid.keys():
            max_x = max(max_x, x)
            max_y = max(max_y, y)
        if width is None:
            width=max_x
        if height is None:
            height=max_y

    max_image_width=0
    max_image_height=0
    xy_map_to_image={} # type: Dict[Tuple[int,int],Image.Image]
    for xi in range(0,width):
        for yi in range(0,height):
            eid = xy_map_to_eid[(xi,yi)]

            with zipfile.ZipFile( dataset.dir / f"{eid}.zip" ) as zip:
                fn = f"dmpccs.{eid}.con.{time}.png"
                image_bytes=zip.read(f"{eid}/{fn}")
                assert len(image_bytes)>0

            image=Image.open( io.BytesIO(image_bytes), formats=("jpeg", "png"))
            image=crop_image_whitespace(image)

            max_image_height=max(max_image_height, image.height)
            max_image_width=max(max_image_width, image.width)

            xy_map_to_image[(xi,yi)] = image

    allw=max_image_width*width
    allh=max_image_height*height
    res=Image.new("RGB", (allw, allh), (255,255,255))

    for ((x,y),img) in xy_map_to_image.items():
        res.paste(img, (x*max_image_width, y*max_image_height))
    return res

if __name__=="__main__":

    parser=argparse.ArgumentParser(
        "extract_snapshots.py",
        description=
"""
Attempt to extract a width x height 2d slice through the parameter space.
It will try to select points in the middle of the parameter range for all
other parameterss.
"""
    )
    parser.add_argument("dataset_dir_or_dmpci_template")
    parser.add_argument("output_file", help="Name of the image file to create")
    parser.add_argument("x_param", help="Name of x parameter")
    parser.add_argument("y_param", help="Name of y parameter")
    parser.add_argument("width", nargs="?", default=None, help="Number of images along x. Default is max(3, min(10, ceil(pow(nSamples,1.3/d))))")
    parser.add_argument("height", nargs="?", default=None, help="Number of images along y. Default is max(3, min(10, ceil(pow(nSamples,1.3/d))))")
    parser.add_argument("--default_dataset_root", nargs="?", default="dpd_datasets", help="Default directory to put datasets in.")
    
    args=parser.parse_args()

    (dataset,dataset_dir)=command_line_dataset_open_helper(args.dataset_dir_or_dmpci_template, args.default_dataset_root)

    if dataset.matrix==None:
        sys.stderr.write("Dataset is empty.\n")
        sys.exit(1)

    output_file=Path(args.output_file)

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

    x_param_name = args.x_param
    if x_param_name not in dataset.matrix.parameters_to_index:
        sys.stderr.write(f"Couldn't find parameter x_param '{x_param_name}' in dataset.\nKnown parameters: {dataset.matrix.parameters} \n")
        sys.exit(1)
    x_param_index = dataset.matrix.parameters_to_index[x_param_name]
    x_param = dataset.template.parameters[x_param_name]
    assert x_param.type=="REAL", "TODO haven't thought about how to handle parameter types other than REAL yet"

    y_param_name = args.y_param
    if y_param_name not in dataset.matrix.parameters_to_index:
        sys.stderr.write(f"Couldn't find parameter y_param '{y_param_name}' in dataset.\nKnown parameters: {dataset.matrix.parameters} \n")
        sys.exit(1)
    y_param_index = dataset.matrix.parameters_to_index[y_param_name]
    y_param = dataset.template.parameters[y_param_name]
    assert y_param.type=="REAL", "TODO haven't thought about how to handle parameter types other than REAL yet"


    #################################################################
    ## Work out samples closest to the target point

    sel_scale=d
    sys.stderr.write(f"Scaling up x and y parameters by {sel_scale} for distance search\n")
    xy_map_to_eid = find_2d_parameter_slice_ids(dataset, sel_scale, x_param, y_param, width, height)


    ################################################################
    ## Extract all the images for the samples and crop them

    res = create_2d_mosaic_from_slice_ids(dataset, time, xy_map_to_eid)

    ###############################################################
    ## Now write it out
        
    res.save(output_file)
