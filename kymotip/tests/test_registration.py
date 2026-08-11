from pathlib import Path

import numpy as np

from kymotip.core.registration import ChannelSpec, run_registration

DATA_DIR = Path(__file__).parent / "data" / "registration_input"


def test_run_registration_single_channel(tmp_path):
    output_dir = tmp_path / "out"
    log_path = tmp_path / "registration_log.txt"
    channel = ChannelSpec(input_dir=DATA_DIR, output_dir=output_dir, fname="PM")

    run_registration(
        channels=[channel],
        angs=-2,
        ange=2,
        dtheta=2,
        start_t=0,
        num_t=4,
        d=10,
        n_fill=0,
        log_path=log_path,
    )

    written = sorted(output_dir.glob("PM_*.png"))
    assert [p.name for p in written] == [f"PM_{i:03d}.png" for i in range(4)]

    import cv2

    for p in written:
        img = cv2.imread(str(p), 0)
        assert img is not None
        assert img.shape == (300, 300)

    assert log_path.is_file()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2  # header + 1 run
    assert lines[0].split("\t")[0] == "fname"


def test_run_registration_two_channels(tmp_path):
    output_dir_a = tmp_path / "out_a"
    output_dir_b = tmp_path / "out_b"
    channels = [
        ChannelSpec(input_dir=DATA_DIR, output_dir=output_dir_a, fname="PM"),
        ChannelSpec(input_dir=DATA_DIR, output_dir=output_dir_b, fname="PM"),
    ]

    run_registration(
        channels=channels,
        angs=0,
        ange=0,
        dtheta=1,
        start_t=0,
        num_t=3,
        d=0,
        n_fill=0,
        log_path=None,
    )

    for output_dir in (output_dir_a, output_dir_b):
        written = sorted(output_dir.glob("PM_*.png"))
        assert len(written) == 3
