Parameter space exploration using Osprey DPD
============================================

This repo provides infrastructure for performing parameter
space exploration over a parameter space. Currently this
exploration is random and simple, but hopefully it could
grow into something more automated.

Pre-requisites
--------------

This repo assumes that you have at least the following:

- python3
- A compiled [Osprey DPD](https://github.com/Osprey-DPD/osprey-dpd) binary. It doesn't need to be on the path.

Certain optional features rely on:

- [povray](http://www.povray.org/) : assumed to be available as `povray` in the environment
- [Pillow](pillow.readthedocs.io) : installed and available in python3

Terminology
-----------

- "DMPCI template" : A templatised DMPCI file that defines a parameter space 
    - "parameters" : A set of named values defining the search space, each with data-types and lower/upper bounds
- "sample" : The parameters and results of one specific osprey run within the search space
    - "configuration" : The set of values bound to each parameter
    - "DMPCI instance" : A concrete instance of the DMPCI template, where the parameters have been replaced with the configuration
    - "observables" : The output values from running the simulation (e.g. pressure, temperature, ...)
    - "snapshots" : Discrete samples/snapshots from running this instance
- "tag" : Each sample can be tagged with zero or more identifiers, which can be used to identify sub-sets of samples
- "dataset" : A collection of 0 or more samples from a single template


Parameterised DMPCI template files
-------------------------

A parameter space is defined by a dmpci file which has been extended to:

1. Define a set of parameters and their ranges
2. Identify where in the dmpci body these parameters should be inserted

Parameters are defined using lines within the Comment section that begin
with `EXPLORER-PARAMETER`. Currently they must have the format:
```
EXPLORE-PARAMETER  <parameter-name> <parameter-type> <lower-bound> <upper-bound>
```
where the components are:

- `<parameter-name>` : a C identifier
- `<parameter-type>` : either `INTEGER` or `REAL`
- `<lower-bound>` and `<upper-bound>` : the numeric inclusive range the parameter can vary over

The parameters can then be used anywhere after the Comment section, by using
`${parameter-name}` syntax (the same as bash/shellscript).

A really dumb example of using this is available in [`examples/dmpci.water.template`](examples/dmpci.water.template).
Just the start of the file is shown here, where we can see two parameters being
defined in the Comment then used in the body:
```
dpd

Title	" Really simple example of parameters "
Date    05/06/23    
Comment	"
EXPLORE-PARAMETER  CON_STRENGTH REAL 25 75
EXPLORE-PARAMETER  POLY_LENGTH INTEGER 1 10
"

State	random
Bead  S 0.5 ${CON_STRENGTH} 4.5 
Bond  S S  100  0.5
Polymer Polys      1.0   " (S ( ${POLY_LENGTH} S ) S) "
```
This will vary the conservative strength between 25 and 75, and
choose and vary the length of the polymer from 3 to 12 (as there
are two pre-existing end-cap beads on top of the 1..10 middle beads).


Running an exploration
----------------------

The script `sample_exploration.py` will take a template dmpci file and
run some number of random instances of the template. Assuming
that `dpd` is on the path, we could run 4 instances using:
```
$ ./run_exploration.py examples/dmpci.water.template --repeats=4
```

This command will:

1. Parse the template file and check it is consistent
2. Create a working directory to put temporary files (automatically deleted after)
3. Create an output directory to store the results in, by default called `dpd_explore/sample_ID` in the same directory.
   If it already exists, it is left along.
4. Copy the template into the output directory, or if it already exists check that the template there is the same as the template
   specified for this exploration.
4. For the given number of repeats (in this case 4):
    a. Generate a 64 bit integer SEED and use that to generate random parameters
    b. Create a sub working directory called `sample_SEED` and write a dmpci file into that directory called `dmpci.SEED`.
    c. Run osprey on the seed
    d. Parse the output of dmpcas into an sqlite database
    f. Create a zip file in the output file called `sample_SEED.zip` and add the main osprey outputs and sqlite database to it.
    e. (Optionally) render any povray files into images and add them to the zip file.
    g. (Optionally) compress and add specific outputs (povray, rst, dat)
    h. Write the zip file, and then copy it into the output directory.

Possible output from the above command is:
```
dbt1c21@davids-MacBook-Pro dpd-exploration % ./run_exploration.py examples/dmpci.water.template --repeats=4
Working dir = /var/folders/1v/l8ng86996qd34ydq4ggglz040000gp/T/tmphp2pgxal
Output dir = dpd_explore/water
DMPCIParameter(name='CON_STRENGTH', type='REAL', minval=25.0, maxval=75.0)
DMPCIParameter(name='POLY_LENGTH', type='INTEGER', minval=1.0, maxval=10.0)
Starting sample_0b8087a78e93cf2b
Finished sample_0b8087a78e93cf2b
Starting sample_2f8bd3832f8b3488
Finished sample_2f8bd3832f8b3488
Starting sample_51830a1e5187e70e
Finished sample_51830a1e5187e70e
Starting sample_75d6571f1e1ec74a
Finished sample_75d6571f1e1ec74a
dbt1c21@davids-MacBook-Pro dpd-exploration %
```

If we look in `dpd_explore/water` we'll see the output zip files:
```
dbt1c21@davids-MacBook-Pro dpd-exploration % ls  dpd_explore/water 
dmpci.water.template  sample_0b8087a78e93cf2b.zip  sample_2f8bd3832f8b3488.zip  sample_51830a1e5187e70e.zip  sample_75d6571f1e1ec74a.zip
```
If we look at what's inside one of the zip files we can see the results of one simulation:
```
dbt1c21@davids-MacBook-Pro dpd-exploration % zipinfo dpd_explore/water/sample_0b8087a78e93cf2b.zip
Archive:  dpd_explore/water/sample_0b8087a78e93cf2b.zip
Zip file size: 6224 bytes, number of entries: 7
drwxrwxrwx  2.0 unx        0 b- stor 80-Jan-01 00:00 sample_0b8087a78e93cf2b/
-rw-r--r--  2.0 unx      685 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/dmpci.sample_0b8087a78e93cf2b
-rw-r--r--  2.0 unx    12191 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/dmpcas.sample_0b8087a78e93cf2b
-rw-r--r--  2.0 unx     1200 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/dmpchs.sample_0b8087a78e93cf2b
-rw-r--r--  2.0 unx      480 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/dmpcis.sample_0b8087a78e93cf2b
-rw-r--r--  2.0 unx      788 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/dmpcls.sample_0b8087a78e93cf2b
-rw-r--r--  2.0 unx    36864 b- defN 23-Jun-05 21:00 sample_0b8087a78e93cf2b/sample_0b8087a78e93cf2b.hdf5
7 files, 52208 bytes uncompressed, 5054 bytes compressed:  90.3%
dbt1c21@davids-MacBook-Pro dpd-exploration % 
```

The script has a number of parameters, documented via `--help`. Current options are:
TODO

Exploration outputs
--------------------

The expectation is that we'll want to run a lot of samples, potentially up to 10,000
or more. Clearly we can't store huge amounts of data, so we'd only like to keep
1MB or less for each simulation. This only suggests 10GB, which is not too bad, but
in many HPC systems the bottleneck is the number of files - for example Iridis
at Southampton allows 1500GB of space in /scratch, but only 500K files. Each dpd
simulation produces at least 5 output files, and state snapshots increase that
further.

### Samples

To limit both space and files, each sample's input and output is packed into zip file, so that
there is only one file per sample. These files can then be coallesced into
chunkier zip files for archive or analysis. Walking a zip file is easy in most
languages, so it doesn't provide too much of an impediment for analysis.

Each sample has an id `sample_{SEED}`, where SEED is a 64-bit number (I'm assuming
we never do close to 2^32 simulations, so collisions are not considered).

The output of a sample is a file `sample_{SEED}.zip`, which contains
simulation outputs in a subdirectory called `sample_{SEED}` (see earlier example
of zip listing). Anything with prefix `sample_` should only contain one
sample for that seed.

The paramers and observable outputs are stored in a hdf5 file in the zip called
`sample_{SEED}.hdf5`. Internally this contains:
- `experiments` : a 1d string vector of all the experiment names
- `tags` : a 1d vector of tag sets. Each tag set is a semi-colon separated set of tags. 
- `parameters` : a 1d string vector of all the parameters names
- `observables` : a 1d string vector of all the observable names
- `times` : a 1d int64 vector of all the observation times
- `configurations` : a 2d float64 matrix of nExperiments x nParameters
- `data` : a 3d float64 matrix of nExperiments x nTimes x nObservables


### Datasets

A dataset `{DATASET_ID}` is a directory `{DIR}` that contains the following:
- "{DIR}/dataset_id.txt" : Text file containing the text `{DATASET_ID}`.
- "{DIR}/dmpci.{DATASET_ID}.template" : The DMPCI template used to created the dataset.
- "{DIR}/{DATASET_ID}.hdf5" : The results matrix for all samples in the dataset.
- "{DIR}/samples/sample_{SAMPLE_ID}.zip" : One zip file for each sample in the data-set.
