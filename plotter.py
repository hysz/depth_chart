import matplotlib.pyplot as plt
import collections
import json
import sys
from functools import cmp_to_key
import argparse
import requests
from pprint import pprint
import statistics


######### TYPES #########
Depth = collections.namedtuple("Depth", ['bucket', 'value', 'price'])
Source = collections.namedtuple("Source", ['name', 'depths'])
BucketRange = collections.namedtuple("BucketRange", ['min', 'mid', 'max', 'raw'])

######### PARSE COMMAND LINE ARGS #########
parser = argparse.ArgumentParser()
parser.add_argument("--buy", help="buy token", type=str, required=True)
parser.add_argument("--sell", help="sell token", type=str, required=True)
parser.add_argument("--sell-amount", help="amount to sell", type=str, default='50000')
parser.add_argument("--samples", help="number of samples", type=str, default='5')
parser.add_argument("--distribution", help="sample distribution base", type=str, default='1')
parser.add_argument("--plot", help="what to plot [unified|individual|both]", type=str, default='unified')
parser.add_argument("--sources", help="source1,source2,source3,...", type=str, default="")
parser.add_argument("--file", help="file to read from, instead of hitting URL", type=str, default="")
parser.add_argument("--x-axis", help="bucket|price", type=str, default="price")
parser.add_argument("--side", help="buy|sell", type=str, default="buy")
args = parser.parse_args()
url = 'https://02b23f2b8271.ngrok.io/swap/v0/depth?buyToken=%s&sellToken=%s&sellAmount=%s&numSamples=%s&sampleDistributionBase=%s'%(args.buy, args.sell, int(args.sell_amount) * pow(10,18), args.samples, args.distribution)
print(url)

######### INIT #########
MIN_PRICE = sys.float_info.max
MAX_PRICE = 0
PRICE_STEP = 0

######### PLOTTING #########
def gen_name(name):
    return "%s-%s_%s (%de18, %s samples)"%(args.buy, args.sell, name, int(args.sell_amount), args.samples)

def create_plot(name):
    fig, ax = plt.subplots()
    ax.set_title(gen_name(name))
    return ax

def plot(ax, prices, cumulative_depths, color = None):
    handle = ax.fill_between(prices, 0, cumulative_depths, color=color)
    return handle

def show_plot(name):
    plt.ylabel('depth')
    plt.xlabel(args.x_axis)
    plt.savefig('%s.png'%(gen_name(name)), bbox_inches='tight')
    plt.show()  

def plot_and_show(name, prices, cumulative_depths):
    ax = create_plot(name)
    plot(ax, prices, cumulative_depths)
    show_plot(name)

######### PARSING 0x API RESPONSE #########
response_json = None
if not args.file:
    response = requests.get(url)
    response.raise_for_status()
    response_json = json.loads(response.content)
    json.dump(response_json, open('./latest.json', 'w'))
else:
    response_json = json.load(open(args.file))

######### GENERATE SOURCES #########
# returns sources[], bucket_prices
def gen_sources(side):
    sources = []
    bucket_prices = []

    depths_by_source_name = {}
    for bucket, data_by_bucket_price in enumerate(response_json[side]['dataByBucketPrice']):
        for source_name in data_by_bucket_price.keys():
            if args.sources != "" and not source_name.lower() in args.sources.lower():
                continue
            elif source_name == "cumulative" or source_name == "price" or source_name == "bucket":
                continue

            if not source_name in depths_by_source_name:
                depths_by_source_name[source_name] = []
            
            depths_by_source_name[source_name].append(Depth(float(bucket), float(data_by_bucket_price[source_name]), float(data_by_bucket_price["price"])))
        
        bucket_prices.append(float(data_by_bucket_price["price"]))

    sources = [Source(name, depths_by_source_name[name]) for name in depths_by_source_name.keys()]
    return (sources, bucket_prices)

######### ALGOS #########
# Convert an array of Depth[] to (prices[], cumulative_depths[])
# This output gets plotted, with prices on the x-axis and cumulative-depths on the y-axis.
def depths_to_xy(depths, bucket_prices):
    prices = []
    cumulative_depths = []
    for depth in depths:
        #if args.x_axis == "price":
        prices.append(bucket_prices[int(depth.bucket)])
        '''
        else:
            prices.append(depth.bucket)
        '''
        cumulative_depths.append(depth.value)
    return (prices, cumulative_depths)

# Compares two depths, used for sorting by price (low-to-high)
def compare_depths(d1, d2):
    if d1.bucket < d2.bucket:
        return -1
    elif d1.bucket > d2.bucket:
        return 1
    else:
        return 0

# Sorts input Depth[] and then merges instances that have the same cumulative depth.
def merge_and_sort(depths):
    return sorted(depths, key=cmp_to_key(compare_depths))

# Returns unified depths across all sources.
# All depths at each price will be summed together.
def get_unified_depths(sources):
    cumulative_depths = [depth for source in sources for depth in source.depths]  
    return get_interpolated(merge_and_sort(unified_depths))

def get_interpolated(depths, bucket_prices):
    interpolated_depths = []
    for i,depth in enumerate(depths):
        if i == 0:
            continue
        
        if depths[i].bucket == depths[i-1].bucket + 1:
            interpolated_depths.append(depth)
            continue

        # interpolate
        step = (depths[i].value - depths[i-1].value) / (depths[i].bucket - depths[i-1].bucket)
        cur_depth = float(depths[i-1].value + step)
        price_step = (depths[i].price - depths[i-1].price) / (depths[i].bucket - depths[i-1].bucket)
        cur_price = float(depths[i-1].price + price_step)
        for bucket in range(int(depths[i-1].bucket) + 1, int(depths[i].bucket)):
            interpolated_depths.append(Depth(bucket, cur_depth, cur_price))
            cur_depth += step
            cur_price += price_step
        interpolated_depths.append(depth)

    # add remaining buckets from [last_bucket..<MAX_BUCKET>]
    (next_bucket, value_of_next_bucket) = (int(interpolated_depths[-1].bucket) + 1, interpolated_depths[-1].value) if interpolated_depths else (0, 0)
    for bucket in range(next_bucket, len(bucket_prices)):
        interpolated_depths.append(Depth(bucket, value_of_next_bucket, bucket_prices[bucket]))

    # add buckets from [0..first_bucket]
    first_bucket = int(interpolated_depths[0].bucket)
    for bucket in reversed(range(0, first_bucket)):
        interpolated_depths.insert(0, Depth(bucket,0, bucket_prices[bucket]))

    return interpolated_depths

def is_reverse_sorted(depths):
    for i,depth in enumerate(depths):
        if i > 0:
            if depth.bucket > depths[i-1].bucket:
                print(depth.bucket, ' > ', depths[i-1].bucket)
                return False

    return True

# Returns an array of Depth[] where each cumulative depth is offset from `unified_depths`.
# So, if unified_depths has an entry of 10 at price=1, then the offset_depth will
# add 10 to its value at price=1. This is how we create the rainbow effect.
def offset_from_unified(depths, unified_depths):
    offset_depths = []
    for depth in depths:
        relevant_unified_depths = [unified_depth for unified_depth in reversed(unified_depths) if unified_depth.bucket <= depth.bucket]

        if not is_reverse_sorted(relevant_unified_depths):
            raise Exception("Not reverse sorted")
        #print([bucket for depth.bucket in relevant_unified_depths])
        if len(relevant_unified_depths) == 0:
            # Find 
            offset_depths.append(depth)
        else:
            offset_depths.append(Depth(depth.bucket, depth.value + relevant_unified_depths[0].value, depth.price))

    return offset_depths

# Prints an individual source
def print_individual(sources):
    for source in sources:
        #sanitized_depths = get_interpolated(merge_and_sort(source.depths))
        sanitized_depths = get_interpolated(merge_and_sort(source.depths))
        (prices, cumulative_depths) = depths_to_xy(sanitized_depths)
        plot_and_show(source.name, prices, cumulative_depths)

# Prints the cumulative chart
def print_cumulative(sources):
    (prices, cumulative_depths) = depths_to_xy(get_unified_depths(get_unified_depths))  
    plot_and_show("Cumulative", prices, cumulative_depths)

# Prints all sources unified into a single chart.
def print_unified(ax, sources, bucket_prices):
    # Unlike the cumulative printer, we build the cumulative depth as we go!
    unified_cumulative_depths = []

    plots = []
    for source in sources:
        print("Adding ", source.name)
        sanitized_depths = offset_from_unified(get_interpolated(merge_and_sort(source.depths), bucket_prices), unified_cumulative_depths)
        (prices, individual_cumulative_depths) = depths_to_xy(sanitized_depths, bucket_prices)
        plots.append({"name": source.name, "prices": prices, "individual_cumulative_depths": individual_cumulative_depths})

        # Update unified cumulative depths
        unified_cumulative_depths = sanitized_depths

    handles = []
    labels = []
    color_idx = 0
    #colors = ["#6262A6", "#181632", "#25CD2C", "#FB4C5A", "#5C51FE"]
    colors = ["#C2FAFF", "#8ADEFF", "#55B0FE", "#3F91FF", "#286FFF", "#144AEB", "#0026BB"]
    for single_plot in reversed(plots):
        handle = plot(ax, single_plot["prices"], single_plot["individual_cumulative_depths"], colors[color_idx])
        color_idx = (color_idx + 1)%len(colors)
        handles.append(handle)
        labels.append(single_plot["name"])

    ax.legend(handles, labels)
    

if args.plot == 'individual':
    print_individual(sources)
elif args.plot == 'both':
    print_unified(sources)
    print_individual(sources)
else:
    ax = create_plot("Unified")
    buy_sources,buy_bucket_prices = gen_sources("buy")
    print_unified(ax, buy_sources, buy_bucket_prices)
    sell_sources,sell_bucket_prices = gen_sources("sell")
    print_unified(ax, sell_sources, sell_bucket_prices)
    show_plot('unified')
    
