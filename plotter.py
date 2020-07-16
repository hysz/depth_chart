import matplotlib.pyplot as plt
import collections
import json
import sys
from functools import cmp_to_key

######### TYPES #########
Depth = collections.namedtuple("Depth", ['input', 'output', 'cum_output']) # input:uint, output:uint, cum_output:uint
Source = collections.namedtuple("Source", ['name', 'depths']) # depths:Depth[]


######### PLOTTING #########
def create_plot(name):
    fig, ax = plt.subplots()
    ax.set_title(name)
    return ax

def plot(ax, prices, cumulative_depths):
    handle = ax.fill_between(prices, 0, cumulative_depths)
    return handle

def show_plot():
    plt.ylabel('Depth')
    plt.xlabel('Price')
    plt.show()
    # Uncomment below to save chart
    #plt.savefig('unified.png', bbox_inches='tight')

def plot_and_show(name, prices, cumulative_depths):
    ax = create_plot(name)
    plot(ax, prices, cumulative_depths)
    show_plot()


######### PARSING 0x API (FAKE RESPONSE) #########
response_json = json.load(open('./raw'))
sources = []
for name,inouts in response_json['depth'].items():
    cum_output = 0.0
    depths = [Depth(0,0,0)]
    for inout in inouts:
        depths.append(Depth(float(inout["input"]), float(inout["output"]), float(inout["output"]) + cum_output))
        cum_output += float(inout["output"])
    sources.append(Source(name, depths))
  

######### ALGOS #########
# Convert an array of Depth[] to (prices[], cumulative_depths[])
# This output gets plotted, with prices on the x-axis and cumulative-depths on the y-axis.
def depths_to_xy(depths):
    prices = []
    cumulative_depths = []
    for depth in depths:
        prices.append(depth.input)
        cumulative_depths.append(depth.cum_output)
    return (prices, cumulative_depths)

# Compares two depths, used for sorting by price (low-to-high)
def compare_depths(d1, d2):
    if d1.input < d2.input:
        return -1
    elif d1.input > d2.input:
        return 1
    else:
        return 0

# Sorts input Depth[] and then merges instances that have the same cumulative output.
def merge_and_sort(depths):
    merged_depths = []
    for depth in sorted(depths,  key=cmp_to_key(compare_depths)):
        if merged_depths and merged_depths[-1].input == depth.input:
            # print("Merging input=%f, cumoutput=%f with output=%f"%(merged_depths[-1].input, merged_depths[-1].cum_output, depth.cum_output))
            merged_depths[-1] = Depth(merged_depths[-1].input, -1, merged_depths[-1].cum_output + depth.cum_output)
        else:
            merged_depths.append(depth)
    return merged_depths

# Returns unified depths across all sources.
# All depths at each price will be summed together.
def get_unified_depths(sources):
    cumulative_depths = [depth for source in sources for depth in source.depths]  
    return merge_and_sort(unified_depths)

# Returns an array of Depth[] where each cumulative output is offset from `unified_depths`.
# So, if unified_depths has an entry of 10 at price=1, then the offset_depth will
# add 10 to its value at price=1. This is how we create the rainbow effect.
def offset_from_unified(depths, unified_depths):
    offset_depths = []
    for depth in depths:
        relevant_unified_depths = [unified_depth for unified_depth in unified_depths if unified_depth.input == depth.input]
        if len(relevant_unified_depths) == 0:
            offset_depths.append(depth)
        elif len(relevant_unified_depths) == 1:
            print("FOUND: %f+%f = %f"%(depth.cum_output, relevant_unified_depths[0].cum_output,depth.cum_output + relevant_unified_depths[0].cum_output))
            offset_depths.append(Depth(depth.input, -1, depth.cum_output + relevant_unified_depths[0].cum_output))
        else:
            raise Exception("Unexpected; does not appear this unified depths list is merged & sorted")

    return offset_depths

# Prints an individual source
def print_individual(sources):
    for source in sources:
        if source.name == 'Balancer':
            (prices, cumulative_depths) = depths_to_xy(merge_and_sort(source.depths))
            plot_and_show(source.name, prices, cumulative_depths)

# Prints the cumulative chart
def print_cumulative(sources):
    (prices, cumulative_depths) = depths_to_xy(get_unified_depths(get_unified_depths))  
    plot_and_show("Cumulative", prices, cumulative_depths)

# Prints all sources unified into a single chart.
def print_unified(sources):
    # Unlike the cumulative printer, we build the cumulative depth as we go!
    unified_cumulative_depths = []
    ax = create_plot("Unified")

    plots = []
    for source in sources:
        print("Adding ", source.name)
        (prices, individual_cumulative_depths) = depths_to_xy(offset_from_unified(merge_and_sort(source.depths), unified_cumulative_depths))
        plots.append({"name": source.name, "prices": prices, "individual_cumulative_depths": individual_cumulative_depths})

        # Update unified cumulative depths
        unified_cumulative_depths += source.depths
        unified_cumulative_depths = merge_and_sort(unified_cumulative_depths)


    handles = []
    labels = []
    for single_plot in reversed(plots):
        handle = plot(ax, single_plot["prices"], single_plot["individual_cumulative_depths"])
        handles.append(handle)
        labels.append(single_plot["name"])

    ax.legend(handles, labels)
    show_plot()

#print_individual(sources)
print_unified(sources)
    
