import matplotlib.pyplot as plt
import collections
import json
import sys
from functools import cmp_to_key
import argparse
import requests


######### TYPES #########
Depth = collections.namedtuple("Depth", ['input', 'output']) # input:uint, output:uint
Source = collections.namedtuple("Source", ['name', 'depths']) # depths:Depth[]

######### PARSE COMMAND LINE ARGS #########
parser = argparse.ArgumentParser()
parser.add_argument("--buy", help="buy token", type=str, required=True)
parser.add_argument("--sell", help="sell token", type=str, required=True)
parser.add_argument("--sell-amount", help="amount to sell", type=str, default='50000000000000000000000')
parser.add_argument("--samples", help="number of samples", type=str, default='5')
args = parser.parse_args()
url = 'https://02b23f2b8271.ngrok.io/swap/v0/depth?buyToken=%s&sellToken=%s&sellAmount=%s&numSamples=%s'%(args.buy, args.sell, args.sell_amount, args.samples)

######### PLOTTING #########
def gen_name(name):
    return "%s-%s_%s (%de18, %s samples)"%(args.buy, args.sell, name, int(args.sell_amount) / pow(10,18), args.samples)

def create_plot(name):
    fig, ax = plt.subplots()
    ax.set_title(gen_name(name))
    return ax

def plot(ax, prices, cumulative_depths):
    handle = ax.fill_between(prices, 0, cumulative_depths)
    return handle

def show_plot(name):
    plt.ylabel('Output')
    plt.xlabel('Input')
    plt.savefig('%s.png'%(gen_name(name)), bbox_inches='tight')
    plt.show()  

def plot_and_show(name, prices, cumulative_depths):
    ax = create_plot(name)
    plot(ax, prices, cumulative_depths)
    show_plot(name)

######### PARSING 0x API (FAKE RESPONSE) #########
response = requests.get(url)
response.raise_for_status()
response_json = json.loads(response.content)
sources = []
for name,inouts in response_json['depth'].items():
    depths = [Depth(0,0)]
    for inout in inouts:
        depths.append(Depth(float(inout["input"]), float(inout["output"])))
    sources.append(Source(name, depths))
  

######### ALGOS #########
# Convert an array of Depth[] to (prices[], cumulative_depths[])
# This output gets plotted, with prices on the x-axis and cumulative-depths on the y-axis.
def depths_to_xy(depths):
    prices = []
    cumulative_depths = []
    for depth in depths:
        prices.append(depth.input)
        cumulative_depths.append(depth.output)
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
            merged_depths[-1] = Depth(merged_depths[-1].input, merged_depths[-1].output + depth.output)
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
            offset_depths.append(Depth(depth.input, depth.output + relevant_unified_depths[0].output))
        else:
            raise Exception("Unexpected; does not appear this unified depths list is merged & sorted")

    return offset_depths

# Prints an individual source
def print_individual(sources):
    for source in sources:
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
    show_plot('unified')

#print_individual(sources)
print_unified(sources)
    
