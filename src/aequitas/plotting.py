
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.cm as cm
import matplotlib.gridspec as gridspec
import re
import math
import squarify

def nearest_quartile(x):
    rounded = round(x*4)/4
    if rounded > x:
        return rounded
    else:
        return rounded + 1/4


def truncate_colormap(orig_cmap, min_value=0.0, max_value=1.0, num_colors=100):
    '''
    Use only part of a colormap.
    Attribution: Adapted from: https://stackoverflow.com/questions/
    18926031/how-to-extract-a-subset-of-a-colormap-as-a-new-colormap-in-matplotlib
    '''
    cmap = plt.get_cmap(orig_cmap)
    new_cmap = colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=min_value, b=max_value),
        cmap(np.linspace(min_value, max_value, num_colors)))
    return new_cmap


def check_brightness(rgb_tuple):
    '''
    Determine the brightness of background color.
    Adapted from https://trendct.org/2016/01/22/how-to-choose-a-label-color-to-contrast-with-background/
    '''
    r, g, b = rgb_tuple
    return (r * 299 + g * 587 + b * 114) / 1000


def brightness_threshold(rgb_tuple, min_brightness, light_color,
                         dark_color='black'):
    '''
    Determine ideal label color based on brightness of background color.
    Adapted from https://trendct.org/2016/01/22/how-to-choose-a-label-color-to-contrast-with-background/
    '''
    if check_brightness(rgb_tuple) > min_brightness:
        return dark_color

    return light_color


def assemble_ref_groups(df, ref_group_flag='_ref_group_value'):
    ref_groups = {}
    ref_group_cols = list(df.columns[df.columns.str.contains(ref_group_flag)])
    attributes = list(df.attribute_name.unique())
    for attribute in attributes:
        attr_table = df.loc[df['attribute_name'] == attribute]
        attr_refs = {}
        for col in ref_group_cols:
            metric_key = "".join(col.split(ref_group_flag))
            attr_refs[metric_key] = attr_table.loc[attr_table['attribute_name']==attribute, col].min()
        ref_groups[attribute] = attr_refs
    return ref_groups


def locate_ref_group_indices(df, attribute_name, group_metric, ref_group_flag='_ref_group_value', model_id=1):
    abs_metric = "".join(group_metric.split('_disparity'))
    all_ref_groups = assemble_ref_groups(df, ref_group_flag)
    ind = list(df[(df['attribute_name'] == attribute_name) &
                  (df['attribute_value'] == all_ref_groups[attribute_name][abs_metric]) &
                  (df['model_id'] == model_id)].index)
    idx = ind[0]
    relative_ind = df.index.get_loc(idx)
    return relative_ind


def squarify_plot_rects(rects, data_table, norm_x=100, norm_y=100, color=None,
                        label=None, value=None, ax=None, **kwargs):
    """
    Plotting with Matplotlib from predefined rectangles.
    Adapted from squarify source code.

    Parameters
    ----------
    rects: list-like of dictionaries indicating rectangle dimensions for plotting
    data-table: base data table
    norm_x, norm_y: overall figure dimensions for normalizing box sizes
    color: color string or list-like (see Matplotlib documentation for details)
    label: list-like used as label text
    value: list-like used as value text
    ax: Matplotlib Axes instance
    kwargs: dict, keyword arguments passed to matplotlib.Axes.bar
    Returns
    -------
    axes: Matplotlib Axes
    """
    x = [rect['x'] for rect in rects]
    y = [rect['y'] for rect in rects]
    dx = [rect['dx'] for rect in rects]
    dy = [rect['dy'] for rect in rects]

    ax.bar(x, dy, width=dx, bottom=y, color=color,
           label=label, align='edge', **kwargs)

    if value is not None:
        va = 'center' if label is None else 'top'
        for v, r in zip(value, rects):
            x, y, dx, dy = r['x'], r['y'], r['dx'], r['dy']
            ax.text(x + dx / 2, y + dy / 2, v, va=va, ha='center')

    if label is not None:
        va = 'center' if value is None else 'bottom'
        under_plot = []
        alphabet = list(map(chr, range(65, 91)))
        under_plot_num = 0

        for l, r in zip(label, rects):
            x, y, dx, dy = r['x'], r['y'], r['dx'], r['dy']
            length = dx

            indent_length = 4
            CHAR_PLACEHOLDER = 1.5

            # if box large enough, add labels and values
            if (dx >= (indent_length * 2) + CHAR_PLACEHOLDER * len(l)) & (dx > 10):
                ax.text(x + dx / 2, y + dy / 2, l, va=va, ha='center', fontsize=14, wrap=False)

            else:
                # add labels that don't fit in boxes undeneath plot
                ax.text(x + dx / 2, y + dy / 2, alphabet[under_plot_num], va=va, ha='center', fontsize=10, wrap=False)
                underplot_label = l.replace('\n', ', ')
                under_plot.append(f"{alphabet[under_plot_num]}: {underplot_label}")
                under_plot_num += 1

    if len(under_plot) > 0:
        unlabeled = ('\n').join(under_plot)
        ax.text(0.0, -0.05, f"Not labeled above:\n{unlabeled}",
                ha='left', va='top', transform=ax.transAxes, fontsize=14)

    ax.set_xlim(0, norm_x)
    ax.set_ylim(0, norm_y)
    return ax



def plot_group_metric(group_table, group_metric, ax=None, ax_lim=None,
                      title=True, label_dict=None):
    '''
    Plot a single group metric's absolute metrics
    :param group_table: A group table
    :param group_metric: The metric to plot. Must be a column in the group_table
    :param ax: A matplotlib Axis. If not passed a new figure will be created.
    :param ax_lim: Maximum value on x-axis, used to match axes across subplots
        when plotting multiple metrics. Default is None.
    :param title: Whether a title should be added to the plot. Default is True.
    :param label_dict: Dictionary of replacement labels for data. Default is None.
    :return: matplotlib.Axis
    '''
    if any(group_table[group_metric].isnull()):
        raise IOError(f"Cannot plot {group_metric}, has NaN values.")

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5))

    height_of_bar = 1
    attribute_names = group_table.attribute_name.unique()
    tick_indices = []
    next_bar_height = 0
    label_position_values = list(group_table[group_metric].values)

    lighter_coppers = truncate_colormap('copper_r', min_value=0, max_value=0.65)

    norm = colors.Normalize(vmin=group_table[group_metric].min(),
                            vmax=group_table[group_metric].max())
    mapping = cm.ScalarMappable(norm=norm, cmap=lighter_coppers)

    # Lock absolute value metric plot x-axis to (0, 1)
    ax_lim = 1
    ax.set_xlim(0, ax_lim)

    for attribute_name in attribute_names:

        attribute_data = group_table.loc[
            group_table['attribute_name'] == attribute_name]
        values = attribute_data[group_metric].values

        attribute_indices = np.arange(next_bar_height,
                                      next_bar_height + attribute_data.shape[0],
                                      step=height_of_bar)
        attribute_tick_location = float((min(attribute_indices) +
                                         max(attribute_indices) + height_of_bar)) / 2

        h_attribute = ax.barh(attribute_indices,
                              width=values,
                              label=list(attribute_data['attribute_value'].values),
                              align='edge', edgecolor='grey')

        label_colors = []
        min_brightness = 0.55

        for (i, bar), val in zip(enumerate(h_attribute), values):
            my_col = mapping.to_rgba(val)
            bar.set_color(my_col)
            label_colors.append(brightness_threshold(my_col[:3], min_brightness,
                                                     light_color=(1, 1, 1, 1)))

        if label_dict:
            labels = [label if label not in label_dict.keys() else
                      label_dict[label] for label in
                        attribute_data['attribute_value'].values]
        else:
            labels = attribute_data['attribute_value'].values

        for y, label, value, text_color in zip(attribute_indices, labels,
                                               values, label_colors):
            next_position = label_position_values.pop(0)

            if ax_lim < 3:
                CHAR_PLACEHOLDER = 0.03
            else:
                CHAR_PLACEHOLDER = 0.25

            label_length = len(label) * CHAR_PLACEHOLDER
            max_val_length = 7 * CHAR_PLACEHOLDER
            indent_length = ax_lim * 0.025

            # bar long enough for label, enough space after bar for value
            if ((indent_length + label_length) < (next_position - indent_length)) & (
                    (next_position + indent_length + max_val_length) < (ax_lim - indent_length)):

                ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
                        f"{value:.2f}", fontsize=12, verticalalignment='top')
                ax.text(indent_length, y + float(height_of_bar) / 2,
                        label, fontsize=11, verticalalignment='top',
                        color=text_color)

            # case when bar too long for labels after bar, print all text in bar
            elif (next_position + indent_length + max_val_length) > (ax_lim - indent_length):

                ax.text(indent_length, y + float(height_of_bar) / 2,
                        f"{label}, {value:.2f}", fontsize=11,
                        verticalalignment='top', color=text_color)

            # case when bar too small for labels inside bar, print all text after bar
            else:
                ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
                        f"{label}, {value:.2f}", fontsize=12,
                        verticalalignment='top')

        tick_indices.append((attribute_name, attribute_tick_location))
        next_bar_height = max(attribute_indices) + 2 * height_of_bar

    ax.yaxis.set_ticks(list(map(lambda x: x[1], tick_indices)))
    ax.yaxis.set_ticklabels(list(map(lambda x: x[0], tick_indices)), fontsize=14)
    ax.set_xlabel("Absolute Metric Magnitude")

    if title:
        ax.set_title(f"{group_metric.upper()}", fontsize=20)

    return ax


# def plot_disparity(disparities_table, group_metric, ax=None, ax_lim=None,
#                    title=True, label_dict=None):
#     '''
#     Plot a single group metric's disparity
#     :param disparities_table: A disparity table
#     :param group_metric: The metric to plot. Must be a column in the
#         disparities_table
#     :param ax: A matplotlib Axis. If not passed a new figure will be created.
#     :param ax_lim: Maximum value on x-axis, used to match axes across subplots
#         when plotting multiple metrics. Default is None.
#     :param title: Whether a title should be added to the plot. Default is True.
#     :param label_dict: Dictionary of replacement labels for data. Default is None.
#     :return: matplotlib.Axis
#     '''
#     if any(disparities_table[group_metric].isnull()):
#         raise IOError(f"Cannot plot {group_metric}, has NaN values.")
#
#     if ax is None:
#         fig, ax = plt.subplots(figsize=(10, 5))
#
#     height_of_bar = 1
#     attribute_names = disparities_table.attribute_name.unique()
#     tick_indices = []
#     next_bar_height = 0
#     label_position_values = list(disparities_table[group_metric].values)
#
#     lighter_purples = truncate_colormap('PuBu', min_value=0, max_value=0.65)
#
#     norm = colors.Normalize(vmin=disparities_table[group_metric].min(),
#                             vmax=disparities_table[group_metric].max())
#     mapping = cm.ScalarMappable(norm=norm, cmap=lighter_purples)
#
#     if not ax_lim:
#         ax_lim = nearest_quartile(disparities_table[group_metric].max()) + 0.1
#
#     ax.set_xlim(0, min(10, ax_lim))
#
#     for attribute_name in attribute_names:
#
#         attribute_data = disparities_table.loc[
#             disparities_table['attribute_name'] == attribute_name]
#         values = attribute_data[group_metric].values
#
#         attribute_indices = np.arange(next_bar_height,
#                                       next_bar_height + attribute_data.shape[0],
#                                       step=height_of_bar)
#         attribute_tick_location = float(
#             (min(attribute_indices) + max(attribute_indices) + height_of_bar)) / 2
#
#         h_attribute = ax.barh(
#             attribute_indices, width=values,
#             label=list(attribute_data['attribute_value'].values),
#             align='edge', edgecolor='grey')
#
#         label_colors = []
#         min_brightness = 0.55
#
#         for (i, bar), val in zip(enumerate(h_attribute), values):
#             my_col = mapping.to_rgba(val)
#             bar.set_color(my_col)
#             label_colors.append(brightness_threshold(my_col[:3], min_brightness,
#                                                      light_color=(1, 1, 1, 1)))
#
#         if label_dict:
#             labels = [label if label not in label_dict.keys() else
#                       label_dict[label] for label in
#                       attribute_data['attribute_value'].values]
#         else:
#             labels = attribute_data['attribute_value'].values
#
#         for y, label, value, text_color in zip(attribute_indices, labels, values,
#                                                label_colors):
#             next_position = label_position_values.pop(0)
#
#             if ax_lim < 3:
#                 CHAR_PLACEHOLDER = 0.03
#             else:
#                 CHAR_PLACEHOLDER = 0.25
#
#             label_length = len(label) * CHAR_PLACEHOLDER
#             max_val_length = 7 * CHAR_PLACEHOLDER
#             indent_length = ax_lim * 0.025
#
#             # bar long enough for label, enough space after bar for value
#             if ((indent_length + label_length) < (next_position - indent_length)) & (
#                     (next_position + indent_length + max_val_length) < (ax_lim - indent_length)):
#
#                 ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
#                         f"{value:.2f}", fontsize=12, verticalalignment='top')
#                 ax.text(indent_length, y + float(height_of_bar) / 2,
#                         label, fontsize=11, verticalalignment='top',
#                         color=text_color)
#
#             # case when bar too long for labels after bar, print all text in bar
#             elif (next_position + indent_length + max_val_length) > (ax_lim - indent_length):
#
#                 ax.text(indent_length, y + float(height_of_bar) / 2,
#                         f"{label}, {value:.2f}", fontsize=11,
#                         verticalalignment='top', color=text_color)
#
#             # case when bar too small for labels inside bar, print all text after bar
#             else:
#                 ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
#                         f"{label}, {value:.2f}", fontsize=12,
#                         verticalalignment='top')
#
#         tick_indices.append((attribute_name, attribute_tick_location))
#         next_bar_height = max(attribute_indices) + 2 * height_of_bar
#
#     ax.yaxis.set_ticks(list(map(lambda x: x[1], tick_indices)))
#     ax.yaxis.set_ticklabels(list(map(lambda x: x[0], tick_indices)), fontsize=14)
#
#     ax.set_xlabel('Disparity Magnitude')
#
#     if title:
#         ax.set_title(f"{group_metric.upper()}", fontsize=20)
#
#     return ax


def plot_disparity(data_table, group_metric, attribute_name,
                           color_mapping=None, model_id=1, ax=None, fig=None,
                           higlight_fairness=False):
    '''
    Create treemap from disparity or absolute metric values

    Adapted from https://plot.ly/python/treemaps/,
    https://gist.github.com/gVallverdu/0b446d0061a785c808dbe79262a37eea,
    and https://fcpython.com/visualisation/python-treemaps-squarify-matplotlib
    '''
    # Use matplotlib to truncate colormap, scale metric values
    # between the min and max, then assign colors to individual values
    attribute_table = data_table.loc[data_table['attribute_name'] == attribute_name]

    sorted_df = attribute_table.sort_values(group_metric, ascending=False)

    x = 0.
    y = 0.
    width = 100.
    height = 100.

    values = sorted_df.loc[:, group_metric]

    # labels for squares in tree map:
    # label should always be disparity value, disparities visualized should be
    # capped between 0.1x ref group and 10x ref group
    if group_metric + '_disparity' not in attribute_table.columns:
        related_disparity = group_metric

    else:
        related_disparity = group_metric + '_disparity'

    if higlight_fairness:
        metric_parity_mapping = {
            'ppr_disparity': 'Statistical Parity',
            'pprev_disparity': 'Impact Parity',
            'precision_disparity': 'Precision Parity',
            'fdr_disparity': 'FDR Parity',
            'for_disparity': 'FOR Parity',
            'fpr_disparity': 'FPR Parity',
            'fnr_disparity': 'FNR Parity',
            'tpr_disparity': 'TPR Parity',
            'tnr_disparity': 'TNR Parity',
            'npv_disparity': 'NPV Parity',
            'tpr': 'TPR Parity',
            'tnr': 'TNR Parity',
            'for': 'FOR Parity',
            'fdr': 'FDR Parity',
            'fpr': 'FPR Parity',
            'fnr': 'FNR Parity',
            'npv': 'NPV Parity',
            'precision': 'Precision Parity',
            'ppr': 'Statistical Parity',
            'pprev': 'Impact Parity'}

        # apply red for "False" fairness determinations and green for "True"
        # determinations
        cb_green = '#1b7837'
        cb_red = '#a50026'
        measure = metric_parity_mapping[group_metric]
        clrs = [cb_green if val == True else
                cb_red for val in attribute_table[measure]]
    else:
        darker_blues = truncate_colormap('Blues', min_value=0.3, max_value=1)

        if not color_mapping:
            norm = colors.Normalize(vmin=0, vmax=2)
            color_mapping = cm.ScalarMappable(norm=norm, cmap=darker_blues)

        clrs = [color_mapping.to_rgba(val) for val in sorted_df[related_disparity]]

    # color reference group grey
    ref_group_idx = locate_ref_group_indices(df=sorted_df,
                                             attribute_name=attribute_name,
                                             group_metric=group_metric)
    clrs[ref_group_idx] = '#D3D3D3'

    compare_value = values.iloc[ref_group_idx]

    scaled_values = [(0.1 * compare_value) if val < (0.1 * compare_value) else
                     (10 * compare_value) if val >= (10 * compare_value) else
                     val for val in values]


    labels = [f"{attr_val}\n{disp:.2f}" if disp != 1. else
              f"{attr_val}\n(Reference)" for attr_val, disp in
              zip(sorted_df['attribute_value'], sorted_df[related_disparity])]

    normed = squarify.normalize_sizes(scaled_values, width, height)

    #     rects = squarify.squarify(normed, x, y, width, height)
    padded_rects = squarify.padded_squarify(normed, x, y, width, height)

    # make plot
    if not ax or not fig:
        fig, ax = plt.subplots(figsize=(5, 4))

    ax = squarify_plot_rects(padded_rects, data_table=sorted_df, color=clrs,
                             label=labels, ax=ax, alpha=0.8)
    ax.set_title(f"{(' ').join(group_metric.split('_')).upper()} ({attribute_name.upper()})",
                 fontsize=23, fontweight="bold")

    if not higlight_fairness:
        # create dummy invisible image with a color map to leverage for color bar
        img = plt.imshow([[0, 2]], cmap=darker_blues, alpha=0.8)
        img.set_visible(False)
        fig.colorbar(img, orientation="vertical", shrink=.96, ax=ax)

    #     Remove axes and display the plot
    ax.axis('off')


def plot_fairness_group(fairness_table, group_metric, ax=None, ax_lim=None,
                        title=False, label_dict=None):
    '''
    This function plots absolute group metrics as indicated by the config file,
        colored based on calculated parity
    :param fairness_table: A fairness table
    :param group_metric: The fairness metric to plot. Must be a column in the
        fairness_table.
    :param ax: A matplotlib Axis. If not passed a new figure will be created.
    :param ax_lim: Maximum value on x-axis, used to match axes across subplots
        when plotting multiple metrics. Default is None.
    :param title: Whether a title should be added to the plot. Default is True.
    :param label_dict: (Optional) Dictionary of replacement values for data.
        Default is None.
    :return: matplotlib.Axis
    '''

    if any(fairness_table[group_metric].isnull()):
        raise IOError(f"Cannot plot {group_metric}, has NaN values.")

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5))

    height_of_bar = 1
    attributes = fairness_table.attribute_name.unique()
    tick_indices = []
    next_bar_height = 0
    label_position_values = list(fairness_table[group_metric].values)

    # Define mapping for condiitonal coloring based on fairness determinations
    metric_parity_mapping = {'tpr': 'TPR Parity',
                             'tnr': 'TNR Parity',
                             'for': 'FOR Parity',
                             'fdr': 'FDR Parity',
                             'fpr': 'FPR Parity',
                             'fnr': 'FNR Parity',
                             'npv': 'NPV Parity',
                             'precision': 'Precision Parity',
                             'ppr': 'Statistical Parity',
                             'pprev': 'Impact Parity'}

    # Lock absolute value metric plot x-axis to (0, 1)
    if not ax_lim:
        ax_lim = 1
    ax.set_xlim(0, ax_lim)

    for attribute in attributes:
        attribute_data = fairness_table.loc[
            fairness_table['attribute_name'] == attribute]
        values = attribute_data[group_metric].values
        label_values = attribute_data[group_metric + '_disparity']

        # apply red for "False" fairness determinations and green for "True"
        # determinations
        cb_green = '#1b7837'
        cb_red = '#a50026'
        measure = metric_parity_mapping[group_metric]
        measure_colors = [cb_green if val == True else
                          cb_red for val in attribute_data[measure]]

        # Set white text for red bars and black text for green bars
        label_colors = [(0, 0, 0, 1) if val == True else
                        (1, 1, 1, 1) for val in attribute_data[measure]]

        attribute_indices = np.arange(next_bar_height,
                                      next_bar_height + attribute_data.shape[0],
                                      step=height_of_bar)
        attribute_tick_location = float((min(attribute_indices) +
                                         max(attribute_indices) + height_of_bar)) / 2

        h_attribute = ax.barh(attribute_indices,
                              width=values,
                              color=measure_colors,
                              align='edge', edgecolor='grey', alpha=0.8)

        if label_dict:
            labels = [label if label not in label_dict.keys() else
                      label_dict[label] for label in
                      attribute_data['attribute_value'].values]
        else:
            labels = attribute_data['attribute_value'].values

        for y, label, value, text_color in zip(attribute_indices, labels,
                                               label_values, label_colors):

            next_position = label_position_values.pop(0)

            if ax_lim < 3:
                CHAR_PLACEHOLDER = 0.03
            else:
                CHAR_PLACEHOLDER = 0.25

            label_length = len(label) * CHAR_PLACEHOLDER
            max_val_length = 7 * CHAR_PLACEHOLDER
            indent_length = ax_lim * 0.025

            # bar long enough for label, enough space after bar for value
            if ((indent_length + label_length) < (next_position - indent_length)) & (
                    (next_position + indent_length + max_val_length) < (ax_lim - indent_length)):

                ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
                        f"{value:.2f}", fontsize=12, verticalalignment='top')
                ax.text(indent_length, y + float(height_of_bar) / 2,
                        label, fontsize=11, verticalalignment='top',
                        color=text_color)

            # case when bar too long for labels after bar, print all text in bar
            elif (next_position + indent_length + max_val_length) > (ax_lim - indent_length):

                ax.text(indent_length, y + float(height_of_bar) / 2,
                        f"{label}, {value:.2f}", fontsize=11,
                        verticalalignment='top', color=text_color)

            # case when bar too small for labels inside bar, print all text
            # after bar
            else:
                ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
                        f"{label}, {value:.2f}", fontsize=12,
                        verticalalignment='top')

        tick_indices.append((attribute, attribute_tick_location))
        next_bar_height = max(attribute_indices) + 2 * height_of_bar

    ax.yaxis.set_ticks(list(map(lambda x: x[1], tick_indices)))
    ax.yaxis.set_ticklabels(list(map(lambda x: x[0], tick_indices)), fontsize=14)

    ax.set_xlabel('Absolute Metric Magnitude')

    if title:
        ax.set_title(f"{group_metric.upper()}", fontsize=20)

    return ax


# def plot_fairness_disparity(fairness_table, group_metric, ax=None, ax_lim=None,
#                             title=False, label_dict=None):
#     '''
#     This function plots absolute group metrics as indicated by the config file, colored
#         based on calculated parity
#     :param fairness_table: A fairness table
#     :param group_metric: The fairness metric to plot. Must be a column in the
#         fairness_table.
#     :param ax: A matplotlib Axis. If not passed a new figure will be created.
#     :param ax_lim: Maximum value on x-axis, used to match axes across subplots
#         when plotting multiple metrics. Default is None.
#     :param title: Whether a title should be added to the plot. Default is True.
#     :param label_dict: (Optional) Dictionary of replacement values for data.
#         Default is None.
#     :return: matplotlib.Axis
#     '''
#
#     if any(fairness_table[group_metric].isnull()):
#         raise IOError(f"Cannot plot {group_metric}, has NaN values.")
#
#     if ax is None:
#         fig, ax = plt.subplots(figsize=(10, 5))
#
#     height_of_bar = 1
#     attributes = fairness_table.attribute_name.unique()
#     tick_indices = []
#     next_bar_height = 0
#     label_position_values = list(fairness_table[group_metric].values)
#
#     # Define mapping for condiitonal coloring based on fairness determinations
#     metric_parity_mapping = {'ppr_disparity': 'Statistical Parity',
#                              'pprev_disparity': 'Impact Parity',
#                              'precision_disparity': 'Precision Parity',
#                              'fdr_disparity': 'FDR Parity',
#                              'for_disparity': 'FOR Parity',
#                              'fpr_disparity': 'FPR Parity',
#                              'fnr_disparity': 'FNR Parity',
#                              'tpr_disparity': 'TPR Parity',
#                              'tnr_disparity': 'TNR Parity',
#                              'npv_disparity': 'NPV Parity'}
#
#     if not ax_lim:
#         ax_lim = nearest_quartile(fairness_table[group_metric].max()) + 0.1
#     ax.set_xlim(0, ax_lim)
#
#     for attribute in attributes:
#         attribute_data = fairness_table.loc[
#             fairness_table['attribute_name'] == attribute]
#         values = attribute_data[group_metric].values
#
#         # apply red for "False" fairness determinations and green for "True"
#         # determinations
#         cb_green = '#1b7837'
#         cb_red = '#a50026'
#         measure = metric_parity_mapping[group_metric]
#         measure_colors = [cb_green if val == True else
#                           cb_red for val in attribute_data[measure]]
#         # Set white text for red bars and black text for green bars
#         label_colors = [(0, 0, 0, 1) if val == True else
#                         (1, 1, 1, 1) for val in attribute_data[measure]]
#
#         attribute_indices = np.arange(next_bar_height,
#                                       next_bar_height + attribute_data.shape[0],
#                                       step=height_of_bar)
#         attribute_tick_location = float((min(attribute_indices) +
#                                          max(attribute_indices) + height_of_bar)) / 2
#
#         h_attribute = ax.barh(attribute_indices, width=values,
#                               color=measure_colors, align='edge',
#                               edgecolor='grey', alpha=0.8)
#
#         if label_dict:
#             labels = [label if label not in label_dict.keys() else
#                       label_dict[label] for label in
#                       attribute_data['attribute_value'].values]
#         else:
#             labels = attribute_data['attribute_value'].values
#
#         for y, label, value, text_color in zip(attribute_indices, labels,
#                                                values, label_colors):
#
#             next_position = label_position_values.pop(0)
#
#             if ax_lim < 3:
#                 CHAR_PLACEHOLDER = 0.03
#             else:
#                 CHAR_PLACEHOLDER = 0.25
#
#             label_length = len(label) * CHAR_PLACEHOLDER
#             max_val_length = 7 * CHAR_PLACEHOLDER
#             indent_length = ax_lim * 0.025
#
#             # bar long enough for label, enough space after bar for value
#             if ((indent_length + label_length) < (next_position - indent_length)) & (
#                     (next_position + indent_length + max_val_length) < (ax_lim - indent_length)):
#
#                 ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
#                         f"{value:.2f}", fontsize=12, verticalalignment='top')
#                 ax.text(indent_length, y + float(height_of_bar) / 2,
#                         label, fontsize=11, verticalalignment='top',
#                         color=text_color)
#
#             # case when bar too long for labels after bar, print all text in bar
#             elif (next_position + indent_length + max_val_length) > (ax_lim - indent_length):
#
#                 ax.text(indent_length, y + float(height_of_bar) / 2,
#                         f"{label}, {value:.2f}", fontsize=11,
#                         verticalalignment='top', color=text_color)
#
#             # case when bar too small for labels inside bar, print all text
#             # after bar
#             else:
#                 ax.text(next_position + indent_length, y + float(height_of_bar) / 2,
#                         f"{label}, {value:.2f}", fontsize=12,
#                         verticalalignment='top')
#
#         tick_indices.append((attribute, attribute_tick_location))
#         next_bar_height = max(attribute_indices) + 2 * height_of_bar
#
#     ax.yaxis.set_ticks(list(map(lambda x: x[1], tick_indices)))
#     ax.yaxis.set_ticklabels(list(map(lambda x: x[0], tick_indices)), fontsize=14)
#
#     ax.set_xlabel('Disparity Magnitude')
#
#     if title:
#         ax.set_title(f"{group_metric.upper()}", fontsize=20)
#
#     return ax


def plot_fairness_disparity(data_table, group_metric, attribute_name,
                            model_id=1, ax=None, fig=None):
    return plot_disparity(data_table=data_table,
                                  group_metric=group_metric,
                                  attribute_name=attribute_name,
                                  color_mapping=None, model_id=model_id,
                                  ax=ax, fig=fig, higlight_fairness=True)


def plot_multiple(data_table, plot_fcn, metrics=None, fillzeros=True, title=True,
                  ncols=3, label_dict=None, show_figure=True):
    """
    This function plots disparities as indicated by the config file, colored
        based on calculated parity
    :param data_table: Output of group.get_crosstabs, bias.get_disparity, or
        fairness.get_fairness functions
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot the following absolute metrics (or
        related disparity measures):
            - Predicted Prevalence (pprev),
            - Predicted Positive Rate (ppr),
            - False Discovery Rate (fdr),
            - False Omission Rate (for),
            - False Positve Rate (fpr),
            - False Negative Rate (fnr)

    :param fillzeros: Should null values be filled with zeros. Default is True.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.

    :return: Returns a figure
    """
    if fillzeros:
        data_table = data_table.fillna(0)

    if plot_fcn in [plot_fairness_group, plot_group_metric]:
        if not metrics:
            primary_abs_metrics = ['pprev', 'ppr', 'fdr', 'for', 'fpr', 'fnr']
            metrics = [met for met in primary_abs_metrics if met in data_table.columns]

        #         metrics = list(set(self.input_group_metrics) & set(data_table.columns))
        elif metrics == 'all':
            abs_metrics = ['pprev', 'ppr', 'fdr', 'for', 'fpr', 'fnr',
                           'tpr', 'tnr', 'npv', 'precision']
            metrics = [met for met in abs_metrics if met in data_table.columns]

        ax_lim = 1

    # elif plot_fcn in [plot_fairness_disparity, plot_disparity]:
    else:
        if not metrics:
            primary_disparities = ['pprev_disparity', 'ppr_disparity', 'fdr_disparity',
                                  'for_disparity', 'fpr_disparity', 'fnr_disparity']
            metrics = [disp for disp in primary_disparities if disp in data_table.columns]
        elif metrics == 'all':
            metrics = list(data_table.columns[data_table.columns.str.contains('_disparity')])

        ax_lim = min(10, nearest_quartile(max(data_table[metrics].max())) + 0.1)

    num_metrics = len(metrics)
    rows = math.ceil(num_metrics / ncols)
    if ncols == 1 or (num_metrics % ncols == 0):
        axes_to_remove = 0
    else:
        axes_to_remove = ncols - (num_metrics % ncols)

    assert (
                0 < rows <= num_metrics), \
        "Plot must have at least one row. Please update number of columns " \
        "('ncols') or list of metrics to be plotted ('metrics')."
    assert (
                0 < ncols <= num_metrics), \
        "Plot must have at least one column, and no more columns than metrics. " \
        "Please update number of columns ('ncols') or list of metrics to be " \
        "plotted ('metrics')."

    total_plot_width = 25

    fig, axs = plt.subplots(nrows=rows, ncols=ncols,
                            figsize=(total_plot_width, 6 * rows), sharey=True,
                            gridspec_kw={'wspace': 0.075, 'hspace': 0.25})

    # set a different metric to be plotted in each subplot
    ax_col = 0
    ax_row = 0

    for group_metric in metrics:
        if (ax_col >= ncols) & ((ax_col + 1) % ncols) == 1:
            ax_row += 1
            ax_col = 0

        if rows == 1:
            current_subplot = axs[ax_col]

        elif ncols == 1:
            current_subplot = axs[ax_row]
            ax_row += 1
        else:
            current_subplot = axs[ax_row, ax_col]
        plot_fcn(data_table, group_metric=group_metric, ax=current_subplot,
                 ax_lim=ax_lim, title=title, label_dict=label_dict)
        ax_col += 1

    # disable axes not being used
    if axes_to_remove > 0:
        for i in np.arange(axes_to_remove):
            axs[-1, -(i + 1)].axis('off')

    if show_figure:
        plt.show()
    return fig


def plot_multiple_treemaps(data_table, plot_fcn, attributes=None, metrics=None,
                           fillzeros=True, title=True, label_dict=None,
                           higlight_fairness=False, show_figure=True):
    """
    This function plots disparities as indicated by the config file, colored
        based on calculated parity
    :param data_table: Output of group.get_crosstabs, bias.get_disparity, or fairness.get_fairness functions
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot: Predicted Prevalence (pprev), Predicted Positive Rate (ppr),
        False Discovery Rate (fdr), False Omission Rate (for), False Positve Rate (fpr),
        False Negative Rate (fnr), (or related disparity measures).
    :param fillzeros: Should null values be filled with zeros. Default is True.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.

    :return: Returns a figure
    """
    if fillzeros:
        data_table = data_table.fillna(0)

    assert not all(v is None for v in
                   [attributes, metrics]), "One of the following parameters must be specified: 'attribute', 'metrics'"

    if attributes:
        if not metrics:
            primary_abs_metrics = ['pprev', 'ppr', 'fdr', 'for', 'fpr', 'fnr']
            metrics = [abs_m for abs_m in primary_abs_metrics if abs_m in data_table.columns]

        #         metrics = list(set(self.input_group_metrics) & set(data_table.columns))
        elif metrics == 'all':
            abs_metrics = ['tpr', 'tnr', 'for', 'fdr', 'fpr', 'fnr',
                           'npv', 'precision', 'ppr', 'pprev']
            metrics = [abs_m for abs_m in abs_metrics if abs_m in data_table.columns]

        viz_title = f"Disparity Metrics by {(', ').join(list(map(lambda x:x.upper(), attributes)))}"

    elif not attributes:
        attributes = list(data_table.attribute_name.unique())
        if metrics == 'all':
            abs_metrics = ['tpr', 'tnr', 'for', 'fdr', 'fpr', 'fnr',
                           'npv', 'precision', 'ppr', 'pprev']
            metrics = [abs_m for abs_m in abs_metrics if abs_m in data_table.columns]
        viz_title = f"{(', ').join(map(lambda x:x.upper(), metrics))} Across Attributes"

    ncols = 3
    num_metrics = len(attributes) * len(metrics)
    rows = math.ceil(num_metrics / ncols)
    if ncols == 1 or (num_metrics % ncols == 0):
        axes_to_remove = 0
    else:
        axes_to_remove = ncols - (num_metrics % ncols)

    assert (
            0 < rows <= num_metrics), \
        "Plot must have at least one row. Please update number of columns " \
        "('ncols') or list of metrics to be plotted ('metrics')."
    assert (
            0 < ncols <= num_metrics), \
        "Plot must have at least one column, and no more columns than metrics. " \
        "Please update number of columns ('ncols') or list of metrics to be " \
        "plotted ('metrics')."

    total_plot_width = 25

    fig, axs = plt.subplots(nrows=rows, ncols=ncols,
                            figsize=(total_plot_width, 8 * rows),
                            gridspec_kw={'wspace': 0.025, 'hspace': 0.5},
                            subplot_kw={'aspect': 'equal'})

    if higlight_fairness:
        mapping = None
    else:
        darker_blues = truncate_colormap('Blues', min_value=0.25, max_value=1)
        norm = colors.Normalize(vmin=0, vmax=2)
        mapping = cm.ScalarMappable(norm=norm, cmap=darker_blues)

    # set a different metric to be plotted in each subplot
    ax_col = 0
    ax_row = 0

    #     if attributes:
    for group_metric in metrics:
        for attr in attributes:
            if (ax_col >= ncols) & ((ax_col + 1) % ncols) == 1:
                ax_row += 1
                ax_col = 0

            if rows == 1:
                current_subplot = axs[ax_col]

            elif ncols == 1:
                current_subplot = axs[ax_row]
                ax_row += 1
            else:
                current_subplot = axs[ax_row, ax_col]

            plot_fcn(data_table, group_metric=group_metric,
                     attribute_name=attr, color_mapping=mapping,
                     ax=current_subplot, fig=fig,
                     higlight_fairness=higlight_fairness)

            ax_col += 1

    # disable axes not being used
    if axes_to_remove > 0:
        for i in np.arange(axes_to_remove):
            axs[-1, -(i + 1)].axis('off')

    plt.suptitle(f"{viz_title}", fontsize=25, fontweight="bold")

    # fig.tight_layout()

    if rows > 2:
        fig.subplots_adjust(top=0.95)
    else:
        fig.subplots_adjust(top=0.90)

    if show_figure:
        plt.show()
    return fig


def plot_group_metric_all(data_table, metrics=None, fillzeros=True,
                          ncols=3, title=True, label_dict=None,
                          show_figure=True):
    '''
    Plot multiple metrics at once from a fairness object table.
    :param data_table:  Output of group.get_crosstabs function.
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot:
            - Predicted Prevalence (pprev),
            - Predicted Positive Rate (ppr),
            - False Discovery Rate (fdr),
            - False Omission Rate (for),
            - False Positve Rate (fpr),
            - False Negative Rate (fnr)
    :param fillzeros: Whether null values be filled with zeros. Default is True.
    :param ncols: Number of subplots per row in figure. Default is 3.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :return:
    '''
    return plot_multiple(data_table, plot_fcn=plot_group_metric,
                         metrics=metrics,
                         fillzeros=fillzeros, title=title, ncols=ncols,
                         label_dict=label_dict, show_figure=show_figure)


# def plot_disparity_all(data_table, metrics=None, fillzeros=True,
#                        ncols=3, title=True, label_dict=None, show_figure=True):
#     '''
#     Plot multiple metrics at once from a fairness object table.
#     :param data_table:  Output of group.get_crosstabs, bias.get_disparity, or
#         fairness.get_fairness functions.
#     :param metrics: which metric(s) to plot, or 'all.'
#         If this value is null, will plot:
#             - Predicted Prevalence Disparity (pprev_disparity),
#             - Predicted Positive Rate Disparity (ppr_disparity),
#             - False Discovery Rate Disparity (fdr_disparity),
#             - False Omission Rate Disparity (for_disparity),
#             - False Positve Rate Disparity (fpr_disparity),
#             - False Negative Rate Disparity (fnr_disparity)
#     :param fillzeros: Should null values be filled with zeros. Default is True.
#     :param ncols: Number of subplots per row in figure. Default is 3.
#     :param title: Whether to display a title on each plot. Default is True.
#     :param label_dict: Dictionary of label replacements. Default is None.
#     :param show_figure: Whether to show figure (plt.show()). Default is True.
#     :return:
#     '''
#     return plot_multiple(data_table, plot_fcn=plot_disparity,
#                          metrics=metrics,
#                          fillzeros=fillzeros, title=title, ncols=ncols,
#                          label_dict=label_dict, show_figure=show_figure)


def plot_disparity_all(data_table, attributes=None, metrics=None,
                                fillzeros=True, ncols=3, title=True,
                                label_dict=None, show_figure=True):
    '''
    Plot multiple metrics at once from a fairness object table.
    :param data_table:  Output of group.get_crosstabs, bias.get_disparity, or
        fairness.get_fairness functions.
    :param attributes: which attribute(s) to plot metrics for.
        If this value is null, will plot metrics against all attributes.
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot:
            - Predicted Prevalence Disparity (pprev_disparity),
            - Predicted Positive Rate Disparity (ppr_disparity),
            - False Discovery Rate Disparity (fdr_disparity),
            - False Omission Rate Disparity (for_disparity),
            - False Positve Rate Disparity (fpr_disparity),
            - False Negative Rate Disparity (fnr_disparity)
    :param fillzeros: Should null values be filled with zeros. Default is True.
    :param ncols: Number of subplots per row in figure. Default is 3.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :return:
    '''
    return plot_multiple_treemaps(data_table, plot_fcn=plot_disparity,
                                  attributes=attributes, metrics=metrics,
                                  fillzeros=fillzeros, title=title,
                                  label_dict=label_dict, higlight_fairness=False,
                                  show_figure=show_figure)

def plot_fairness_group_all(data_table, metrics=None, fillzeros=True,
                            ncols=3, title=True, label_dict=None,
                            show_figure=True):
    '''
    Plot multiple metrics at once from a fairness object table.
    :param data_table:  Output of group.get_crosstabs, bias.get_disparity, or
        fairness.get_fairness functions.
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot:
            - Predicted Prevalence (pprev),
            - Predicted Positive Rate (ppr),
            - False Discovery Rate (fdr),
            - False Omission Rate (for),
            - False Positve Rate (fpr),
            - False Negative Rate (fnr)
    :param fillzeros: Should null values be filled with zeros. Default is True.
    :param ncols: Number of subplots per row in figure. Default is 3.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :return:
    '''
    return plot_multiple(data_table, plot_fcn=plot_fairness_group,
                         metrics=metrics,
                         fillzeros=fillzeros, title=title, ncols=ncols,
                         label_dict=label_dict, show_figure=show_figure)


def plot_fairness_disparity_all(data_table, attributes=None, metrics=None,
                                fillzeros=True, ncols=3, title=True,
                                label_dict=None, show_figure=True):
    '''
    Plot multiple metrics at once from a fairness object table.
    :param data_table:  Output of group.get_crosstabs, bias.get_disparity, or
        fairness.get_fairness functions.
    :param attributes: which attribute(s) to plot metrics for.
        If this value is null, will plot metrics against all attributes.
    :param metrics: which metric(s) to plot, or 'all.'
        If this value is null, will plot:
            - Predicted Prevalence Disparity (pprev_disparity),
            - Predicted Positive Rate Disparity (ppr_disparity),
            - False Discovery Rate Disparity (fdr_disparity),
            - False Omission Rate Disparity (for_disparity),
            - False Positve Rate Disparity (fpr_disparity),
            - False Negative Rate Disparity (fnr_disparity)
    :param fillzeros: Should null values be filled with zeros. Default is True.
    :param ncols: Number of subplots per row in figure. Default is 3.
    :param title: Whether to display a title on each plot. Default is True.
    :param label_dict: Dictionary of label replacements. Default is None.
    :param show_figure: Whether to show figure (plt.show()). Default is True.
    :return:
    '''
    return plot_multiple_treemaps(data_table, plot_fcn=plot_disparity,
                                  attributes=attributes, metrics=metrics,
                                  fillzeros=fillzeros, title=title,
                                  label_dict=label_dict, higlight_fairness=True,
                                  show_figure=show_figure)

