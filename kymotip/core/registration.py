"""Image-registration primitives and batch processing for KymoTip."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.interpolate import RectBivariateSpline
from scipy.signal import fftconvolve

from .io_utils import append_log, ensure_dir, frame_path, read_image_any, write_image_any


@dataclass
class ChannelSpec:
    input_dir: str | Path
    output_dir: str | Path
    fname: str
    ext: str = "png"


def translation(img, rx, ry, n, p):
    d = img.shape
    nimg = np.copy(img)
    if len(d) == 2:
        nimg = np.roll(nimg, rx, axis=0)
        nimg = np.roll(nimg, ry, axis=1)
        if p == 1:
            nimg = imgmosic(nimg, rx, ry, n)
    elif len(d) == 3:
        for i in range(d[-1]):
            nimg[:, :, i] = np.roll(nimg[:, :, i], rx, axis=0)
            nimg[:, :, i] = np.roll(nimg[:, :, i], ry, axis=1)
            if p == 1:
                nimg[:, :, i] = imgmosic(nimg[:, :, i], rx, ry, n)
    return nimg


def imgmosic(img, rx, ry, n2):
    n, m = img.shape
    if rx < 0:
        if n2 == 0:
            img[n + rx : n, :] = img[n + rx : n, :] * 0
        else:
            img[n + rx : n, :] = img[n + rx : n, :] * 0 + np.random.randint(
                n2, size=(-rx, m)
            )
    elif rx > 0:
        if n2 == 0:
            img[0:rx, :] = img[0:rx, :] * 0
        else:
            img[0:rx, :] = img[0:rx, :] * 0 + np.random.randint(
                n2, size=(rx, m)
            )

    if ry < 0:
        if n2 == 0:
            img[:, m + ry : m] = img[:, m + ry : m] * 0
        else:
            img[:, m + ry : m] = img[:, m + ry : m] * 0 + np.random.randint(
                n2, size=(n, -ry)
            )
    elif ry > 0:
        if n2 == 0:
            img[:, 0:ry] = img[:, 0:ry] * 0
        else:
            img[:, 0:ry] = img[:, 0:ry] * 0 + np.random.randint(
                n2, size=(n, ry)
            )
    return img


def normxcorr2(template, image, mode="full"):
    if np.ndim(template) > np.ndim(image) or len(
        [
            i
            for i in range(np.ndim(template))
            if template.shape[i] > image.shape[i]
        ]
    ) > 0:
        print("normxcorr2: TEMPLATE larger than IMG. Arguments may be swapped.")

    template = template - np.mean(template)
    image = image - np.mean(image)

    a1 = np.ones(template.shape)
    ar = np.flipud(np.fliplr(template))
    out = fftconvolve(image, ar.conj(), mode=mode)

    image = fftconvolve(np.square(image), a1, mode=mode) - np.square(
        fftconvolve(image, a1, mode=mode)
    ) / np.prod(template.shape)
    image[image < 0] = 0

    template = np.sum(np.square(template))
    with np.errstate(divide="ignore", invalid="ignore"):
        out = out / np.sqrt(image * template)
    out[np.where(np.logical_not(np.isfinite(out)))] = 0
    return out


def maximum(a):
    ind = np.unravel_index(np.argmax(a, axis=None), a.shape)
    return [ind[0] + 1, ind[1] + 1, a[ind[0], ind[1]]]


def rotate(img, theta, n):
    row, column = img.shape
    y = np.linspace(0, row - 1, row)
    x = np.linspace(0, column - 1, column)
    yc = np.median(y)
    xc = np.median(x)
    y = y - yc
    x = x - xc

    f = RectBivariateSpline(y, x, img, kx=3, ky=3, s=0)

    xx, yy = np.meshgrid(x, y)
    matrix = np.array(
        [
            [math.cos(theta), -math.sin(theta)],
            [math.sin(theta), math.cos(theta)],
        ],
        dtype=float,
    )
    xxnew = matrix[0, 0] * xx + matrix[0, 1] * yy
    yynew = matrix[1, 0] * xx + matrix[1, 1] * yy

    xlim = column - xc - 1
    ylim = row - yc - 1
    inside = (np.abs(xxnew) <= xlim) & (np.abs(yynew) <= ylim)

    if n == 0:
        imgnew = np.zeros((row, column), dtype=float)
    else:
        imgnew = np.random.randint(n, size=(row, column)).astype(float)

    vals = f.ev(yynew[inside], xxnew[inside])
    imgnew[inside] = vals
    return imgnew


def extension(img, n):
    nr, nc = img.shape
    pad_width = abs(nr - nc) // 2
    if nr > nc:
        padding = ((0, 0), (pad_width, pad_width))
    elif nr < nc:
        padding = ((pad_width, pad_width), (0, 0))
    else:
        return img
    padded_img = np.pad(img, padding, mode="constant", constant_values=0)
    if n != 0 and pad_width > 0:
        if nr > nc:
            padded_img[:, :pad_width] = np.random.randint(
                n, size=(nr, pad_width)
            )
            padded_img[:, -pad_width:] = np.random.randint(
                n, size=(nr, pad_width)
            )
        else:
            padded_img[:pad_width, :] = np.random.randint(
                n, size=(pad_width, nc)
            )
            padded_img[-pad_width:, :] = np.random.randint(
                n, size=(pad_width, nc)
            )
    return padded_img


def contraction(img1, img2):
    nr1, nc1 = img1.shape
    nr2, nc2 = img2.shape
    if nr1 > nc1:
        tmp = (nr1 - nc1) // 2
        img = img2[:, tmp : nc2 - tmp]
    elif nr1 < nc1:
        tmp = (nc1 - nr1) // 2
        img = img2[tmp : nr2 - tmp, :]
    else:
        img = img2
    return img


def _read_image(path: Path) -> np.ndarray:
    return read_image_any(path)


def _write_image(path: Path, image: np.ndarray, dtype: np.dtype) -> None:
    max_val = np.iinfo(dtype).max
    array = np.clip(np.rint(image), 0, max_val).astype(dtype)
    write_image_any(path, array)


def _rotation_angles(angs: float, ange: float, dtheta: float) -> np.ndarray:
    if dtheta <= 0:
        raise ValueError("dtheta must be greater than zero")
    if ange < angs:
        raise ValueError("ange must be greater than or equal to angs")
    degrees = np.arange(angs, ange + dtheta / 2.0, dtheta)
    return degrees / 180 * math.pi


def run_registration(
    channels: list[ChannelSpec],
    angs: float,
    ange: float,
    dtheta: float,
    start_t: int,
    num_t: int,
    d: int = 10,
    n_fill: int = 0,
    log_path: str | Path | None = None,
) -> None:
    if not 1 <= len(channels) <= 3:
        raise ValueError("channels must contain between one and three ChannelSpec items")
    if n_fill < 0:
        raise ValueError("n_fill must be nonnegative")

    theta = _rotation_angles(angs, ange, dtheta)
    for channel in channels:
        ensure_dir(channel.output_dir)

    reference_images = [
        _read_image(frame_path(channel.input_dir, channel.fname, 0, channel.ext))
        for channel in channels
    ]
    dtypes = [image.dtype for image in reference_images]
    for channel, image, dtype in zip(channels, reference_images, dtypes):
        _write_image(frame_path(channel.output_dir, channel.fname, 0, channel.ext), image, dtype)

    for frame in range(max(start_t, 1), num_t):
        moving_images = [
            _read_image(frame_path(channel.input_dir, channel.fname, frame, channel.ext))
            for channel in channels
        ]
        extended_reference = extension(reference_images[0], n_fill)
        extended_moving = [extension(image, n_fill) for image in moving_images]

        best_score = -np.inf
        registered_images = None
        for angle in theta:
            rotated_images = [rotate(image, angle, n_fill) for image in extended_moving]
            peak = maximum(normxcorr2(extended_reference, rotated_images[0], mode="full"))
            if peak[2] > best_score:
                best_score = peak[2]
                shift_y = extended_reference.shape[0] - peak[0]
                shift_x = extended_reference.shape[1] - peak[1]
                registered_images = [
                    translation(
                        contraction(original, rotated),
                        shift_y,
                        shift_x,
                        n_fill,
                        1,
                    )
                    for original, rotated in zip(moving_images, rotated_images)
                ]

        if registered_images is None:
            raise RuntimeError("rotation angle search produced no candidates")

        output_paths = [
            frame_path(channel.output_dir, channel.fname, frame, channel.ext)
            for channel in channels
        ]
        for output_path, image, dtype in zip(output_paths, registered_images, dtypes):
            _write_image(output_path, image, dtype)

        if d > 0 and frame % d == 0:
            reference_images = [_read_image(path) for path in output_paths]

    if log_path is not None:
        columns = [
            "fname",
            "n_channels",
            "angs",
            "ange",
            "dtheta",
            "start_t",
            "num_t",
            "d",
            "timestamp",
        ]
        append_log(
            log_path,
            columns,
            {
                "fname": channels[0].fname,
                "n_channels": len(channels),
                "angs": angs,
                "ange": ange,
                "dtheta": dtheta,
                "start_t": start_t,
                "num_t": num_t,
                "d": d,
            },
        )
