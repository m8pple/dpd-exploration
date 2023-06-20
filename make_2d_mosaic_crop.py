#!/usr/bin/env python3

from PIL import Image
import PIL.ImageOps
import sys
import glob
import pathlib
import re
import math

input_pattern=sys.argv[1]

min_x=10000000000
min_y=10000000000
max_x=0
max_y=0
max_w=0
max_h=0

t_values=set()

all=[]

def crop_image_whitespace(img):
    neg=PIL.ImageOps.invert(img)
    bbox=neg.getbbox()
    assert(bbox is not None)
    return img.crop(bbox)

sys.stderr.write(f"input_pattern={input_pattern}\n")
for i in glob.glob(input_pattern):
    p=pathlib.Path(i)
    name=p.name
    sys.stderr.write(f"  name={name}\n")

    img=Image.open(i)
    img=crop_image_whitespace(img)
    max_w=max(max_w,img.width)
    max_h=max(max_h,img.height)

    all.append(img)

assert len(all)>0, "No images found"

nrows = int(math.sqrt(len(all)))
ncols = (len(all)+nrows-1)//nrows

images={}
allw=max_w*ncols
allh=max_h*nrows
res=Image.new("RGB", (allw, allh), (255,255,255))

for (i,img) in enumerate(all):
    x=i%nrows
    y=i%ncols
    res.paste(img, (x*max_w, y*max_h))

res.save("out.png")
