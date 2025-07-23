import os
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from skimage import measure
from cellpose import models, denoise
from cellpose.io import imread, imsave
import torch


def collect_images(input_root: Path, identifier: str = None):
    """
    Recursively collect TIFF images. If `identifier` is given, only keep files
    whose name contains that substring (case-insensitive).
    """
    exts = (".tif", ".tiff")
    files = []
    for p in input_root.rglob("*"):
        if p.suffix.lower() in exts:
            if identifier:
                if identifier.lower() in p.name.lower():
                    files.append(p)
            else:
                files.append(p)
    return files


def process_image(tif_path: Path,
                  input_root: Path,
                  output_root: Path,
                  denoise_model,
                  seg_model,
                  diameter: float,
                  flow_threshold: float,
                  cellprob_threshold: float):
    """Denoise, segment, save outputs, compute simple metrics, return dict."""
    rel = tif_path.relative_to(input_root)
    out_subdir   = output_root / rel.parent
    denoised_dir = out_subdir / "denoised"
    masks_dir    = out_subdir / "masks"
    denoised_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing: {rel}")

    # 1) Read
    img = imread(str(tif_path)).astype(np.float32)

    # 2) Denoise (denoise_cyto3)
    # channels=[0,0] -> single-channel image
    _, _, _, imgs_dn = denoise_model.eval([img], channels=[0, 0], diameter=diameter)
    img_dn = imgs_dn[0]
    dn_path = denoised_dir / f"{tif_path.stem}_denoised.tif"
    imsave(str(dn_path), img_dn)

    # 3) Segment with cyto2
    masks, flows, styles, diams = seg_model.eval(
        [img_dn],
        diameter=diameter,
        flow_threshold=flow_threshold,
        cellprob_threshold=cellprob_threshold,
        channels=[[0, 0]]
    )

    if masks is None or len(masks) == 0:
        return {"file": str(rel), "n_objects": 0}

    mask = masks[0].astype(np.uint16)
    mask_path = masks_dir / f"{tif_path.stem}_mask.tif"
    imsave(str(mask_path), mask)

    # 4) Quantify
    lbl = measure.label(mask > 0)
    props = measure.regionprops(lbl)
    n_objects = len(props)
    if n_objects == 0:
        return {"file": str(rel), "n_objects": 0}

    # Use largest object by area (like organoid script)
    p = max(props, key=lambda r: r.area)
    area = p.area
    perimeter = p.perimeter
    circularity = 4 * np.pi * area / (perimeter ** 2) if perimeter else 0
    y0, x0 = p.centroid

    return {
        "file": str(rel),
        "n_objects": int(n_objects),
        "area": float(area),
        "perimeter": float(perimeter),
        "circularity": float(circularity),
        "centroid_x": float(x0),
        "centroid_y": float(y0),
    }


def main():
    # Load config
    with open("config.yml", "r") as f:
        cfg = yaml.safe_load(f)

    input_root  = Path(cfg["input_root"])
    output_root = Path(cfg["output_root"])
    threads     = os.cpu_count() if cfg.get("threads", "auto") == "auto" else int(cfg["threads"])
    diameter    = float(cfg["diameter"])
    flow_thr    = float(cfg["flow_threshold"])
    cellprob_thr= float(cfg.get("cellprob_threshold", 0.0))
    identifier  = cfg.get("file_identifier", None)

    # Models
    use_gpu = torch.cuda.is_available()
    print(f"Using device: {'GPU' if use_gpu else 'CPU'}")

    denoise_model = denoise.CellposeDenoiseModel(
        gpu=use_gpu,
        model_type="cyto3",
        restore_type="upsample_cyto3"
    )
    seg_model = models.Cellpose(
        gpu=use_gpu,
        model_type="cyto2"
    )

    # Collect files
    all_imgs = collect_images(input_root, identifier=identifier)
    print(f"Found {len(all_imgs)} images to process.")

    results = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(
                process_image,
                tif,
                input_root,
                output_root,
                denoise_model,
                seg_model,
                diameter,
                flow_thr,
                cellprob_thr
            )
            for tif in all_imgs
        ]
        for fut in tqdm(futures, desc="Cellpose batch"):
            res = fut.result()
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    csv_path = output_root / "cellpose_single_channel_metrics.csv"
    df.to_csv(csv_path, index=False)
    print(f"[DONE] Metrics written to {csv_path}")


if __name__ == "__main__":
    main()
