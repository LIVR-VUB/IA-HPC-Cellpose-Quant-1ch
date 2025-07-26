![Under Development](https://img.shields.io/badge/Status-under_development-orange)

![May Contain Bugs](https://img.shields.io/badge/Warning-may%20contain%20bugs-red)


# Cellpose Single-Channel Pipeline (Upsample➜ Segment ➜ Quantify)

This project provides a **one-command workflow** to:

1. **Upsample** single‑channel TIFF images with `upsample_cyto3`
2. **Segment** them with the `cyto2` Cellpose model
3. **Quantify** basic object metrics (area, perimeter, circularity, centroid, count)
4. **Save** denoised images, masks, and a CSV summary

Everything runs inside a **Singularity/Apptainer container**, so students only need to:

* Edit a small YAML config fileBelow is a ready‑to‑drop **`README.md`** for your repo.

* Run one Singularity command

* No coding required.

## Pipeline Overview
![Pipeline overview](https://github.com/LIVR-VUB/IA-Cellpose-Quant-1ch/blob/main/misc/ChatGPT%20Image%20Jul%2023%2C%202025%2C%2011_37_03%20PM.png)


## Contents

* [Folder Structure](#folder-structure)
* [Quick Start (Most People)](#quick-start-most-people)
* [Config File (`config.yml`)](#config-file-configyml)
* [One-Liner Run Command](#one-liner-run-command)
* [Building the Container (if needed)](#building-the-container-if-needed)
* [Script Arguments & CLI Overrides](#script-arguments--cli-overrides)
* [Outputs](#outputs)
* [Typical SLURM Example](#typical-slurm-example)
* [Troubleshooting](#troubleshooting)
* [FAQ](#faq)


## Folder Structure

A minimal setup on the HPC (or your local machine) should look like:

```
project/
├─ cellpose_auto_single.py      # main pipeline script (already in container)
├─ cellpose.def         # definition file (for building container)
├─ cellpose.sif                 # built container (optional to store here)
├─ config.yml                   # YOU edit this
├─ images/                      # raw .tif/.tiff files
└─ output/                      # will be created/populated by the pipeline
```

> You only need to **edit `config.yml`** and put your images in `images/`.
> The `output/` folder will be created automatically.

---

## Quick Start (Most People)

1. **Clone or download** this repo:

   ```bash
   git clone https://github.com/LIVR-VUB/IA-Cellpose-Quant-1ch.git
   cd IA-Cellpose-Quant-1ch
   ```

2. **Make sure you have the container** (built or downloaded) — `cellpose.sif`.

3. **Edit `config.yml`:**

   ```yaml
   input_root:  /work/images     # inside-container path
   output_root: /work/output     # inside-container path
   threads: auto
   diameter: 30
   flow_threshold: 0.4
   cellprob_threshold: 0.0
   file_identifier: d3.TIF       # substring to filter files (optional)
   restore_type: upsample_cyto3  # or denoise_cyto3 (if supported in your Cellpose)
   ```

4. **Run the pipeline:**

   ```bash
   singularity run --nv -B /path/on/hpc/project:/work /path/to/cellpose.sif /work/config.yml
   ```

5. **Check outputs in** `/path/on/hpc/project/output/`:

   * `cellpose_single_channel_metrics.csv`
   * mirrored subfolders containing `denoised/` and `masks/` images

---

## Config File (`config.yml`)

| Key                  | What it does                                           | Example          |
| -------------------- | ------------------------------------------------------ | ---------------- |
| `input_root`         | Path to your raw images **inside the container**       | `/work/images`   |
| `output_root`        | Where results go **inside the container**              | `/work/output`   |
| `threads`            | `auto` or an integer (CPU threads for parallelism)     | `auto`           |
| `diameter`           | Approx. object size in pixels (Cellpose param)         | `30`             |
| `flow_threshold`     | Cellpose flow cutoff (tune if over/under-segmentation) | `0.4`            |
| `cellprob_threshold` | Cell probability cutoff (tune for detection)           | `0.0`            |
| `file_identifier`    | Substring to filter files (case-insensitive)           | `d3.TIF`         |
| `restore_type`       | Denoise model type (e.g. `upsample_cyto3`)             | `upsample_cyto3` |

> Paths in the YAML are **inside** the container. We bind `/path/on/hpc/project` to `/work`, so use `/work/...` in the config.

---

## One-Liner Run Command

```bash
singularity run --nv -B /path/on/hpc/project:/work /path/to/cellpose.sif /work/config.yml
```

* `--nv` exposes the GPU (remove if CPU only)
* `-B /path/on/hpc/project:/work` binds your project folder to `/work` inside the container
* Final argument `/work/config.yml` is the path to your config **inside the container**

**If you omit the config path**, the container will use the baked-in default (`/opt/cellpose/config.yml`). Make sure that one points to valid paths, or override options via CLI flags (see below).

---

## Building the Container (if needed)

If your HPC won’t let you build, do this on a machine with Singularity/Apptainer and root:

```bash
singularity build cellpose.sif cellpose.def
# or apptainer build cellpose.sif Singularity.cellpose
```

Upload `cellpose.sif` to the HPC.

---

## Script Arguments & CLI Overrides

The script reads `--config` but also lets you override specific keys on the command line.

Examples:

```bash
# Use default config.yml inside container
singularity run --nv -B /proj:/work cellpose.sif

# Override just the diameter and flow_threshold
singularity run --nv -B /proj:/work cellpose.sif \
  --diameter 40 --flow_threshold 0.25
```

Available overrides:

```
--input_root
--output_root
--threads
--diameter
--flow_threshold
--cellprob_threshold
--file_identifier
--restore_type
```

---

## Outputs

* **CSV**: `cellpose_single_channel_metrics.csv` with one row per image:

  * `file`, `n_objects`, `area`, `perimeter`, `circularity`, `centroid_x`, `centroid_y`
* **Images**:

  * `denoised/<original_name>_denoised.tif`
  * `masks/<original_name>_mask.tif`
* All saved in a mirrored folder structure under `output_root`.

---

## Typical SLURM Example

```bash
#!/bin/bash
#SBATCH -J cellpose
#SBATCH -p gpu
#SBATCH --gres=gpu:1
#SBATCH -c 8
#SBATCH -t 02:00:00
#SBATCH -o cellpose.out
#SBATCH -e cellpose.err

module load apptainer   # or singularity
# Paths on HPC
PROJ=/path/on/hpc/project
SIF=/path/on/hpc/project/cellpose.sif

apptainer run --nv -B $PROJ:/work $SIF /work/config.yml
```

Submit with `sbatch run_cellpose.sh`.

---

## Troubleshooting

* **`ModuleNotFoundError: yaml`**
  You’re not inside the container / wrong env. Always run via Singularity.

* **No images found**
  Check `input_root` path and `file_identifier` substring.

* **No masks / 0 objects**
  Adjust `diameter`, `flow_threshold`, `cellprob_threshold`. Try increasing or decreasing.

* **CUDA OOM**
  Reduce batch size (we currently do 1 per eval), free GPU memory, or run on CPU (remove `--nv`).

* **Permission errors writing output**
  Ensure the bound folder is writable (`chmod -R u+w output`).

---

## FAQ

**Q: Can I run this on my laptop without Singularity?**
A: Yes. Create a conda env, install the listed packages, run `python cellpose_auto_single.py --config config.yml`.

**Q: What if I want per-object stats, not just the biggest object?**
A: Modify `process_image` to loop over `props` and append rows. Happy to help extend it.

**Q: Can I skip denoising?**
A: Set `restore_type` to something neutral or bypass the denoise step with a flag (requires code tweak).

**Q: My files don’t end in `.tif/.tiff`**
A: Add more extensions in `collect_images`.

**Q: How to create the cellpose quantification environment**
A: You can create conda env by the following commands
   *Step 1:* Create the conda virtual env
   ```python
   conda create --name cellpose python=3.10
   ```
   *Step 2:* Install `cellpose-3`:
   ```python
   pip install cellpose==3.1.1.2
   ```
   *Step 3:* Install other dependencies:
   ```python
   conda install -c conda-forge pyyaml
   conda install -c conda-forge pandas scikit-image tqdm
   ```
And you have successfully installed dependencies!!!!
   

---

### Enjoy & Good luck!

If something breaks, open an issue or ping your supervisor.

---
