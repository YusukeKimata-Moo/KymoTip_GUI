# Object Detection (Gaussian fit)

Detects the position and width of a localized fluorescence signal along the
cell's centerline, by fitting a 1D Gaussian to an intensity profile sampled
across the cell. The detected "object" is not limited to any specific
structure -- it works for anything that produces a single intensity peak
along the cell's length (a nucleus, an MT band, an aggregate, etc.). Ported
from the analysis logic in
[`NucleusDetection.ipynb`](https://github.com/blues0910/KymoTip/blob/main/2.%20nucleus(MT%20band)_detection/NucleusDetection.ipynb),
adapted to run directly on KymoTip's own `03_contour` / `05_centerline`
pipeline outputs instead of the notebook's separate contour/centerline files.

## Inputs

- **Input directory**: registered image frames (`01_registration` output,
  `{image_fname}_NNN.<ext>`) for the channel to detect the object in. This
  can be a *different* channel from the one used for contour/centerline
  (e.g. contour/centerline computed on a cell-outline channel, object
  detected on a nucleus channel) -- see "File name prefix (contour/centerline
  channel)" vs. "Image file name prefix (detection channel)" below.
- **File name prefix (contour/centerline channel)**: the `fname` used by the
  Contour/Centerline stages (looks up `{contour_dir}/{fname}_NNN.txt` and
  `{centerline_dir}/{fname}_NNN.txt`).
- **Image file name prefix (detection channel)**: the `fname` of the channel
  to sample intensity from (looks up `{input_dir}/{image_fname}_NNN.<ext>`).
  Defaults to the same value as the contour/centerline prefix (single-channel
  case) but can be edited independently, matching the `_ch2`/`_ch3` per-
  channel file naming used by Registration/Kymograph. Use "Auto-detect image
  prefix/frames from input directory" to fill it in from the input
  directory's contents.
- **Contour directory**: `03_contour` output (`{fname}_NNN.txt`, columns
  `x y`).
- **Centerline directory**: `05_centerline` output (`{fname}_NNN.txt`,
  columns `x y`).

Run Contour Extraction (stage 3) and Centerline Extraction (stage 5) first
(on whichever channel you used for cell shape), and Registration (stage 1)
for whichever channel you want to detect the object in.

## How it works, per frame

1. For each centerline segment, find the pair of contour points on either
   side that are most perpendicular to it.
2. Sample the raw image intensity along the line between each such point
   pair (bilinear interpolation) and average it, giving an intensity
   profile along the cell's length.
3. Normalize the profile to its max, estimate the object's center as the
   mean position where normalized intensity exceeds the detection
   threshold, then fit `amp * exp(-(x-mu)^2 / (2*sigma^2)) + baseline`
   (with `mu` fixed to that estimate) via least squares.
4. Object width is reported as `2 * scc * |sigma|`.

## Output

`{output_dir}/{image_fname}_gaussian_fit.tsv` with one row per frame: `frame`,
`center_position`, `width`, `total_length`, `amplitude`, `sigma`,
`baseline` (position/length units follow the "Pixel size (px/um)" parameter:
leave it at `1.0` for pixel units, or set it to your px/um conversion factor).

If "Save preview images" is checked, a two-panel PNG (raw image with the
detected object segment overlaid on the centerline, plus the intensity
profile with the Gaussian fit) is saved per frame under
`{output_dir}/images/`.

## Notes

- Requires the cell's contour to be a closed loop and the centerline to
  reasonably bisect it (as produced by KymoTip's own Contour/Centerline
  stages); this mirrors the assumptions of the original notebook.
- Assumes a single intensity peak per frame. If the signal has multiple
  peaks (e.g. two objects), only one Gaussian is fit and the result may be
  unreliable -- this plugin does not do multi-peak detection.
- If detection looks off for a given cell, try adjusting the detection
  threshold (search window for the initial center estimate) or the number
  of samples per cross-section slice.
