"""Voronoi skeleton-based centerline extraction utilities."""

import itertools

import networkx as nx
import numpy as np
import scipy.spatial


def load_contour_data(file_path):
    return np.loadtxt(file_path)


def extract_voronoi_skeleton(points):
    import matplotlib.path as mplPath

    vor = scipy.spatial.Voronoi(points)
    ph = mplPath.Path(points)
    contains = ph.contains_points(vor.vertices)
    vor.verticesInside = set(np.where(contains == True)[0].tolist())
    vor.validRidges = list(filter(lambda r: r[0] in vor.verticesInside and r[1] in vor.verticesInside,
                                  vor.ridge_vertices))
    return vor


def extract_centerline(vor):
    g = nx.Graph()
    for r in vor.verticesInside:
        g.add_node(r)
    for r in vor.validRidges:
        dist = np.linalg.norm(vor.vertices[r[0]] - vor.vertices[r[1]])
        g.add_edge(r[0], r[1], weight=dist)
    endpoints = [r for r in vor.verticesInside if len(list(g.neighbors(r))) == 1]
    longest_path = []
    longest_length = 0
    for x in itertools.combinations(endpoints, 2):
        path_length = nx.shortest_path_length(g, source=x[0], target=x[1], weight='weight')
        if path_length > longest_length:
            longest_length = path_length
            longest_path = nx.shortest_path(g, source=x[0], target=x[1], weight='weight')
    return longest_path


def adjust_centerline_path(vertices, path):
    if vertices[path[0]][1] - vertices[path[-1]][1] < 0:
        path.reverse()
    return path


def calculate_average_distance(points):
    distances = [np.linalg.norm(points[i] - points[i-1]) for i in range(1, len(points))]
    return np.mean(distances)


def interpolate_points(start_point, end_point, num_points):
    vector = end_point - start_point
    return [start_point + vector * (i / (num_points + 1)) for i in range(1, num_points + 1)]


def moving_avg(x, n):
    cumsum = np.cumsum(np.insert(x, 0, 0))
    return (cumsum[n:] - cumsum[:-n]) / float(n)


def smooth_centerline(vertices, path, m1, m2, mm):
    subpath = vertices[path[m1:len(path)-m2+1]]
    x_smooth = moving_avg(subpath[:, 0], mm)
    y_smooth = moving_avg(subpath[:, 1], mm)
    return np.column_stack((x_smooth, y_smooth))


def extend_centerline(yx, smooth_centerline, o, return_l1_l2=False):
    v1 = np.zeros((1, 2))
    v2 = np.zeros((1, 2))
    for i in range(o):
        v1 -= (smooth_centerline[i + 1] - smooth_centerline[i]) / np.linalg.norm(smooth_centerline[i + 1] - smooth_centerline[i]) / o
        v2 += (smooth_centerline[-1 - i] - smooth_centerline[-2 - i]) / np.linalg.norm(smooth_centerline[-1 - i] - smooth_centerline[-2 - i]) / o
    l1 = [np.dot(v1, (point - smooth_centerline[0]) / np.linalg.norm(point - smooth_centerline[0]))[0] for point in yx]
    l2 = [np.dot(v2, (point - smooth_centerline[-1]) / np.linalg.norm(point - smooth_centerline[-1]))[0] for point in yx]
    extended_start = yx[np.argmax(l1)]
    extended_end = yx[np.argmax(l2)]
    extended_centerline = np.vstack([extended_start, smooth_centerline, extended_end])
    if return_l1_l2:
        return extended_centerline, l1, l2
    else:
        return extended_centerline


def interpolate_and_construct_complete_centerline(centerline, average_distance):
    extension_distance_start = np.linalg.norm(centerline[1] - centerline[0])
    extension_distance_end = np.linalg.norm(centerline[-1] - centerline[-2])
    num_interpolation_points_start = int(extension_distance_start / average_distance) - 1
    num_interpolation_points_end = int(extension_distance_end / average_distance) - 1
    interpolated_points_before = np.array(interpolate_points(centerline[0], centerline[1], num_interpolation_points_start))
    interpolated_points_after = np.array(interpolate_points(centerline[-2], centerline[-1], num_interpolation_points_end))
    start_point = centerline[:1, :]
    end_point = centerline[-1:, :]
    mid_points = centerline[1:-1, :]
    complete_centerline = np.vstack([start_point, interpolated_points_before, mid_points, interpolated_points_after, end_point])
    return complete_centerline


def save_centerline_data(centerline, path):
    np.savetxt(path, centerline, fmt='%f')


def compute_centerline(contour_yx, o=10, m1=10, m2=10, mm=65):
    """Compute centerline (shape (M,2)) from a contour point sequence (yx, shape (N,2)).

    Mirrors the notebook driver cell order: extract_voronoi_skeleton -> extract_centerline ->
    adjust_centerline_path -> smooth_centerline -> extend_centerline -> calculate_average_distance ->
    interpolate_and_construct_complete_centerline.
    Defaults o=10, m1=10, m2=10, mm=65 come from the notebook's documented default parameter values
    (not the o=20/m1=40/m2=40/t=66 values that were overridden for one specific dataset in the notebook run).
    """
    vor = extract_voronoi_skeleton(contour_yx)
    path = extract_centerline(vor)
    path = adjust_centerline_path(vor.vertices, path)
    smoothed = smooth_centerline(vor.vertices, path, m1, m2, mm)
    centerline = extend_centerline(contour_yx, smoothed, o)
    average_distance = calculate_average_distance(centerline)
    return interpolate_and_construct_complete_centerline(centerline, average_distance)
