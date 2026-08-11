"""Core utilities for sampling image brightness and generating kymographs."""

import numpy as np

from .io_utils import read_image_any


def load_centerline_data(filepath):
    return np.loadtxt(filepath)


def equally_space_points(data):
    x = data[:, 0]
    y = data[:, 1]
    distances = np.sqrt(np.diff(x)**2 + np.diff(y)**2)
    cumulative_distances = np.insert(np.cumsum(distances), 0, 0)
    total_length = cumulative_distances[-1]
    num_points = len(x)
    new_distances = np.linspace(0, total_length, num_points)
    new_x = np.interp(new_distances, cumulative_distances, x)
    new_y = np.interp(new_distances, cumulative_distances, y)
    new_points = np.column_stack((new_x, new_y))
    return new_points


def calculate_normals(points):
    vectors = np.diff(points, axis=0)
    normals = np.empty_like(vectors)
    normals[:, 0] = -vectors[:, 1]
    normals[:, 1] = vectors[:, 0]
    norm = np.linalg.norm(normals, axis=1, keepdims=True)
    normalized_normals = normals / norm
    return normalized_normals


def sample_brightness_along_normals(image, mask, points, normals, length=100):
    mean_brightness = []
    for point, normal in zip(points, normals):
        samples = []
        for t in np.linspace(-length, length, num=2*length+1):
            sample_point = point + t * normal
            x, y = np.round(sample_point).astype(int)
            if 0 <= x < image.shape[1] and 0 <= y < image.shape[0]:
                if mask[y, x] == 255:
                    samples.append(image[y, x])
        if samples:
            mean_brightness.append(np.mean(samples))
        else:
            mean_brightness.append(0)
    return mean_brightness


def process_images(image_base_path, mask_base_path, centerline_base_path, brightness_base_path, num_images, sample_length=100, mask_path_fn=None, image_ext="png"):
    import cv2

    for i in range(num_images):
        image_path = f"{image_base_path}" + "_" + "%03d" % (i) + f".{image_ext}"
        mask_path = mask_path_fn(i) if mask_path_fn is not None else f"{mask_base_path}" + "_" + "%03d" % (i) + ".png"
        coordinates_path = f"{centerline_base_path}" + "_" + "%03d" % (i) + ".txt"

        # 元画像はTIFF等でも16bitの画素値をそのまま保持するためPIL経由で読む
        # (マスクはSAM2出力の2値PNG固定なのでcv2のままでよい)。
        image = read_image_any(image_path)
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        centerline_data = load_centerline_data(coordinates_path)
        spaced_centerline = equally_space_points(centerline_data)

        normals = calculate_normals(spaced_centerline)
        mean_brightness = sample_brightness_along_normals(image, mask, spaced_centerline, normals, length=sample_length)

        combined_data = np.column_stack((spaced_centerline[:len(mean_brightness)], mean_brightness))

        output_path = f"{brightness_base_path}" + "_" + "%03d" % (i) + ".txt"
        np.savetxt(output_path, combined_data, fmt="%.6f")


def _xaxis_label_and_ticks(num_images, time_interval_sec=None, axis_unit="min"):
    """x軸のラベルと目盛(位置・表示値)を返す。

    始点・終点の2目盛だけでなく、matplotlibのMaxNLocatorでキリのよい間隔の
    中間目盛も補完する。time_interval_sec(1フレームあたりの秒数)が指定された
    場合は、axis_unit("sec"または"min")に換算した値を目盛に使う。
    """
    from matplotlib.ticker import MaxNLocator

    if time_interval_sec:
        per_frame_value = time_interval_sec / (1.0 if axis_unit == "sec" else 60.0)
        label = "Time (sec)" if axis_unit == "sec" else "Time (min)"
    else:
        per_frame_value = 1.0
        label = "t (frame)"

    last_frame = max(num_images - 1, 0)
    max_value = last_frame * per_frame_value

    if last_frame <= 0:
        return label, ([0], [0])

    locator = MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10], integer=(per_frame_value == 1.0))
    tick_values = [v for v in locator.tick_values(0, max_value) if 0 <= v <= max_value]
    if not tick_values or tick_values[0] > 0:
        tick_values = [0.0] + tick_values

    # データ終端(max_value)は、キリのよい目盛と表示値が重複したり位置が
    # 近すぎてラベルが重なったりしない場合のみ追加する。近すぎる場合は
    # 末尾だけ間隔が空く不自然な見た目になるため、キリのよい目盛の方を残す。
    min_gap = max_value * 0.06
    if tick_values[-1] < max_value:
        if (max_value - tick_values[-1]) >= min_gap and round(tick_values[-1]) != round(max_value):
            tick_values.append(max_value)

    tick_pos = [v / per_frame_value for v in tick_values]
    tick_labels = [round(v) for v in tick_values]
    return label, (tick_pos, tick_labels)


def _compute_edge_margin(fig, axs, line_width, data_extent, fallback=1.5):
    """0フレーム目・最終フレームの目盛をプロット領域の両端に置いたとき、
    線幅の半分がちょうど収まるだけのx軸余白(データ単位)を逆算する。

    余白を0にすると端の線がプロット領域からはみ出し、逆に余白を大きく
    取りすぎると目盛と端の間に不自然な隙間ができるため、実際にレンダリング
    してAxesのピクセル幅を測定し、線幅(pt)から必要最小限の余白を求める。
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    if data_extent <= 0:
        return fallback

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    bbox = axs.get_window_extent(renderer=canvas.get_renderer())
    width_pt = bbox.width * 72.0 / fig.dpi

    margin_px = line_width / 2
    if width_pt <= 2 * margin_px:
        return fallback
    return margin_px * data_extent / (width_pt - 2 * margin_px)


def estimate_optimal_line_width(fig_size, num_images, labsize=12, stp=1.0, time_interval_sec=None, axis_unit="min"):
    """指定した図サイズでフレーム間に隙間ができない線幅(pt)を実測ベースで見積もる。

    Figure全体の幅をそのまま使うと、カラーバーや軸ラベルの分だけ実際のプロット
    領域より過大評価してしまう(隣の列と重なる原因になった)ため、colorbar・
    ラベルを含めて実際にレンダリングし、Axesの実ピクセル幅を測定して逆算する。
    """
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    from matplotlib.figure import Figure

    if num_images < 1:
        return 0.1

    fig = Figure(figsize=fig_size)
    axs = fig.add_subplot(111)
    sm = ScalarMappable(cmap="gray", norm=Normalize(0, 1))
    ct = fig.colorbar(sm, ax=axs)
    ct.set_label("Intensity", fontsize=labsize)
    ct.ax.tick_params(labelsize=labsize)
    xlabel, (tick_pos, tick_labels) = _xaxis_label_and_ticks(num_images, time_interval_sec, axis_unit)
    if num_images > 1:
        axs.set_xticks(tick_pos, tick_labels)
    axs.set_xlim(-1.5, num_images * stp + 0.5)
    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Length (um)", fontsize=labsize)
    axs.tick_params(labelsize=labsize)
    fig.tight_layout()

    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    bbox = axs.get_window_extent(renderer=canvas.get_renderer())
    width_pt = bbox.width * 72.0 / fig.dpi

    data_range = num_images * stp + 2
    if data_range <= 0:
        return 0.1
    return max(0.1, (width_pt / data_range) * stp)


def generate_kymograph(fname, brightness_path, num_images, out_path, fig_size, line_width, labsize, pixel_per_micron, adjust_color_range=True, time_interval_sec=None, axis_unit="min"):
    # pyplotのグローバル状態・自動バックエンド選択に依存すると、GUIのバックグラウンド
    # スレッドから呼び出した際にQtバックエンドと衝突しうるため、Figureを直接操作する
    # (描画ロジック自体はpyplot版から変更していない)。
    from matplotlib.collections import LineCollection
    from matplotlib.colors import Normalize
    from matplotlib.figure import Figure

    brightness = []
    max_distance = 0
    for i in range(num_images):
        bi = f"{brightness_path}" + "_" + "%03d" % (i) + ".txt"
        frame_data = np.loadtxt(bi)
        brightness.append(frame_data)
        distances = np.sqrt(np.diff(frame_data[:, 0])**2 + np.diff(frame_data[:, 1])**2)
        total_distance = np.sum(distances)
        if total_distance > max_distance:
            max_distance = total_distance

    if adjust_color_range:
        all_brightness_values = np.concatenate([frame[:, 2] for frame in brightness])
        vmax = np.max(all_brightness_values)
        norm = Normalize(0, vmax)
    else:
        norm = Normalize(0, 256)

    stp = 1
    fig = Figure(figsize=fig_size)
    axs = fig.add_subplot(111)
    axs.set_facecolor("black")
    for i in range(len(brightness)):
        # centerlineに沿った累積弧長(実際の細胞長)をy座標として使う。
        # 1点目とのy座標差だけを使うと、centerlineが斜めのフレームで
        # 細胞の実長より短く見積もられるため。
        point_distances = np.sqrt(np.diff(brightness[i][:, 0])**2 + np.diff(brightness[i][:, 1])**2)
        y = np.insert(np.cumsum(point_distances), 0, 0) / pixel_per_micron
        x = np.zeros(len(y)) + i * stp
        z = brightness[i][:, 2]
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        lc = LineCollection(segments, cmap="gray", norm=norm)
        lc.set_array(z)
        lc.set_linewidth(line_width)
        line = axs.add_collection(lc)

    ct = fig.colorbar(line, ax=axs)
    ct.set_label("Intensity", fontsize=labsize)
    ct.ax.tick_params(labelsize=labsize)
    xlabel, (tick_pos, tick_labels) = _xaxis_label_and_ticks(len(brightness), time_interval_sec, axis_unit)
    axs.set_xticks(tick_pos, tick_labels)
    data_extent = max(len(brightness) - 1, 0)
    axs.set_xlim(-1.5, data_extent + 1.5)
    axs.set_ylim(0, (max_distance / pixel_per_micron) + 10)
    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Length (um)", fontsize=labsize)
    axs.tick_params(labelsize=labsize)
    fig.tight_layout()

    margin = _compute_edge_margin(fig, axs, line_width, data_extent)
    axs.set_xlim(-margin, data_extent + margin)

    kymo_path = out_path + "/" + fname + "_kymograph.png"
    fig.savefig(kymo_path, format="png")
    return kymo_path


def merge_kymograph(brightness_path_1, brightness_path_2, num_images, out_path, fig_size, line_width, labsize, pixel_per_micron, adjust_color_range=True, color1="magenta", color2="green", time_interval_sec=None, axis_unit="min"):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.cm import ScalarMappable
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
    from matplotlib.figure import Figure

    brightness_ch1 = []
    brightness_ch2 = []
    max_distance = 0
    for i in range(num_images):
        bi_ch1 = f"{brightness_path_1}" + "_" + "%03d" % (i) + ".txt"
        bi_ch2 = f"{brightness_path_2}" + "_" + "%03d" % (i) + ".txt"
        frame_data_ch1 = np.loadtxt(bi_ch1)
        frame_data_ch2 = np.loadtxt(bi_ch2)
        brightness_ch1.append(frame_data_ch1)
        brightness_ch2.append(frame_data_ch2)
        distances_ch1 = np.sqrt(np.diff(frame_data_ch1[:, 0])**2 + np.diff(frame_data_ch1[:, 1])**2)
        total_distance = np.sum(distances_ch1)
        if total_distance > max_distance:
            max_distance = total_distance

    cmap1 = LinearSegmentedColormap.from_list("black_to_ch1", [(0, 0, 0), to_rgb(color1)])
    cmap2 = LinearSegmentedColormap.from_list("black_to_ch2", [(0, 0, 0), to_rgb(color2)])

    if adjust_color_range:
        vmax1 = np.max(np.concatenate([frame[:, 2] for frame in brightness_ch1]))
        vmax2 = np.max(np.concatenate([frame[:, 2] for frame in brightness_ch2]))
        norm1 = Normalize(0, vmax1)
        norm2 = Normalize(0, vmax2)
    else:
        norm1 = Normalize(0, 256)
        norm2 = Normalize(0, 256)

    data_extent = max(num_images - 1, 0)
    xlabel, (tick_pos, tick_labels) = _xaxis_label_and_ticks(num_images, time_interval_sec, axis_unit)

    fig = Figure(figsize=fig_size)
    axs = fig.add_subplot(111)
    axs.set_xticks(tick_pos, tick_labels)
    axs.set_xlabel(xlabel, fontsize=labsize)
    axs.set_ylabel("Length (um)", fontsize=labsize)
    axs.tick_params(labelsize=labsize)
    axs.set_xlim(-1.5, data_extent + 1.5)
    axs.set_ylim(0, (max_distance / pixel_per_micron) + 10)

    # 個別チャンネルのキモグラフ(カラーバーあり)とプロットエリアの大きさ・
    # 左右余白を揃えるため、一時的にカラーバー分の余白をレイアウトさせて
    # から、同じロジックで余白(margin)を実測し、カラーバーだけ取り除く。
    colorbar = fig.colorbar(ScalarMappable(cmap=cmap1, norm=norm1), ax=axs)
    colorbar.set_label("Intensity", fontsize=labsize)
    colorbar.ax.tick_params(labelsize=labsize)
    fig.tight_layout()

    margin = _compute_edge_margin(fig, axs, line_width, data_extent)
    axs_width_pt = axs.get_window_extent(
        renderer=FigureCanvasAgg(fig).get_renderer()
    ).width * 72.0 / fig.dpi
    axs.set_xlim(-margin, data_extent + margin)
    colorbar.remove()

    # render_channelは軸をfigure全面([0,0,1,1])に配置するため、最終図の軸
    # (カラーバー分だけ幅が狭い)よりデータ1単位あたりのピクセル密度が高い。
    # 同じ線幅(pt)で描くと線の半幅がmarginまで届かず、最終画像に余分な
    # 余白が残るため、密度比に応じて描画時の線幅を拡大しておく
    # (拡大分はimshowで最終軸に縮小表示される際に相殺され、太さは変わらない)。
    render_line_width = line_width * (fig_size[0] * 72.0) / axs_width_pt if axs_width_pt > 0 else line_width

    def render_channel(brightness, cmap, norm):
        # 同一座標の2色を不透明描画で上書きしないよう、各チャネルを別々に描画する。
        # 余白があるとraster全体がextentに引き伸ばされる際にデータ部分が
        # 縮小・中央寄りにずれるため、軸をfigure全面に配置し余白をなくし、
        # 最終図と同じmarginをxlimに使ってピクセルとデータ範囲を一致させる。
        channel_fig = Figure(figsize=fig_size, facecolor="black")
        channel_axs = channel_fig.add_axes([0, 0, 1, 1])
        channel_axs.set_facecolor("black")
        for i in range(num_images):
            distances = np.sqrt(np.diff(brightness[i][:, 0])**2 + np.diff(brightness[i][:, 1])**2)
            y = np.insert(np.cumsum(distances), 0, 0) / pixel_per_micron
            x = np.zeros(len(y)) + i
            z = brightness[i][:, 2]
            points = np.array([x, y]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            line = LineCollection(segments, cmap=cmap, norm=norm)
            line.set_array(z)
            line.set_linewidth(render_line_width)
            channel_axs.add_collection(line)

        channel_axs.set_xlim(-margin, data_extent + margin)
        channel_axs.set_ylim(0, (max_distance / pixel_per_micron) + 10)
        canvas = FigureCanvasAgg(channel_fig)
        canvas.draw()
        return np.asarray(canvas.buffer_rgba(), dtype=np.uint8)

    rgba1 = render_channel(brightness_ch1, cmap1, norm1)
    rgba2 = render_channel(brightness_ch2, cmap2, norm2)
    merged_rgb = np.clip(
        rgba1[:, :, :3].astype(np.float32) + rgba2[:, :, :3].astype(np.float32),
        0,
        255,
    ).astype(np.uint8)

    axs.imshow(
        merged_rgb,
        origin="upper",
        extent=[-margin, data_extent + margin, 0, (max_distance / pixel_per_micron) + 10],
        aspect="auto",
    )
    kymo_path = out_path + "/merged_kymograph.png"
    fig.savefig(kymo_path, format="png")
    return kymo_path
