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
parser.add_argument("--sell-amount", help="amount to sell", type=str, default='50000000000000000000000')
parser.add_argument("--samples", help="number of samples", type=str, default='5')
parser.add_argument("--distribution", help="sample distribution base", type=str, default='1')
parser.add_argument("--plot", help="what to plot [unified|individual|both]", type=str, default='unified')
parser.add_argument("--sources", help="source1,source2,source3,...", type=str, default="")
parser.add_argument("--file", help="file to read from, instead of hitting URL", type=str, default="")
args = parser.parse_args()
url = 'https://02b23f2b8271.ngrok.io/swap/v0/depth?buyToken=%s&sellToken=%s&sellAmount=%s&numSamples=%s&sampleDistributionBase=%s'%(args.buy, args.sell, args.sell_amount, args.samples, args.distribution)
print(url)

######### INIT #########
BUCKET_RANGES = [BucketRange(0.0,0.0,0.0,[]) for i in range(0,int(args.samples) + 1)]
MIN_PRICE = sys.float_info.max
MAX_PRICE = 0
PRICE_STEP = 0

######### PLOTTING #########
def gen_name(name):
    return "%s-%s_%s (%de18, %s samples)"%(args.buy, args.sell, name, int(args.sell_amount) / pow(10,18), args.samples)

def create_plot(name):
    fig, ax = plt.subplots()
    ax.set_title(gen_name(name))
    return ax

def plot(ax, prices, cumulative_depths, color = None):
    handle = ax.fill_between(prices, 0, cumulative_depths)
    return handle

def show_plot(name):
    plt.ylabel('Value')
    plt.xlabel('Price')
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
sources = []
for name,inouts in response_json['depth'].items():
    if args.sources != "" and not name.lower() in args.sources.lower():
        continue
    pprint(inouts)
    depths = []
    for inout in inouts:
        depth = Depth(float(inout["bucket"]), float(inout["output"]), float(inout["price"]))
        depths.append(depth)

        BUCKET_RANGES[int(depth.bucket)] = BucketRange(0.0,0.0,0.0,BUCKET_RANGES[int(depth.bucket)].raw + [float(depth.price)])
    sources.append(Source(name, depths))
  
######### COMPUTE BUCKET RANGES #########
for i,raw_bucket_range in enumerate(BUCKET_RANGES):
    min = sys.float_info.max
    mid = 0.0
    max = 0.0

    for price in raw_bucket_range.raw:
        if price < min:
            min = price
        if price > max:
            max = price

    if raw_bucket_range.raw:
        mid = statistics.mean(raw_bucket_range.raw)
        if mid < MIN_PRICE:
            MIN_PRICE = mid
        if mid > MAX_PRICE:
            MAX_PRICE = mid

    BUCKET_RANGES[i] = BucketRange(min, mid, max, raw_bucket_range.raw)

######### INTERPOLATE BUCKET RANGES #########
bucket_price_step = 0
for i,bucket_range in enumerate(BUCKET_RANGES):
    print("%f"%(bucket_price_step))
    if i == 0:
        continue
    
    # Already have a range
    if bucket_range.raw:
        bucket_price_step = 0
        continue


    # Compute price step to next valid
    if bucket_price_step == 0:
        for j in range(i+1, len(BUCKET_RANGES)):
            if BUCKET_RANGES[j].raw:
                bucket_price_step = (BUCKET_RANGES[j].mid - BUCKET_RANGES[i-1].mid) / (j - i + 1)
                print("FOUND: %f"%(bucket_price_step))
                break

    # Could not find a future non-empty bucket
    if bucket_price_step == 0:
        bucket_price_step = (MAX_PRICE - MIN_PRICE) / float(args.samples)

    last_bucket_range = BUCKET_RANGES[i-1]
    BUCKET_RANGES[i] = BucketRange(
        last_bucket_range.min + bucket_price_step,
        last_bucket_range.mid + bucket_price_step,
        last_bucket_range.max + bucket_price_step,
        []
    )

#pprint(BUCKET_RANGES[3])
pprint(BUCKET_RANGES)
#sys.exit(0)

######### ALGOS #########
# Convert an array of Depth[] to (prices[], cumulative_depths[])
# This output gets plotted, with prices on the x-axis and cumulative-depths on the y-axis.
def depths_to_xy(depths):
    prices = []
    cumulative_depths = []
    for depth in depths:
        prices.append(BUCKET_RANGES[int(depth.bucket)].mid)
        #prices.append(depth.bucket)
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
    merged_depths = []
    for depth in sorted(depths,  key=cmp_to_key(compare_depths)):
        if merged_depths and merged_depths[-1].bucket == depth.bucket:
            print("Merging ", depth.bucket)
            merged_depths[-1] = Depth(merged_depths[-1].bucket, merged_depths[-1].value + depth.value, (merged_depths[-1].price + depth.price) / 2)
        else:
            merged_depths.append(depth)
    return merged_depths

# Returns unified depths across all sources.
# All depths at each price will be summed together.
def get_unified_depths(sources):
    cumulative_depths = [depth for source in sources for depth in source.depths]  
    return get_interpolated(merge_and_sort(unified_depths))

def get_interpolated(depths):
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

    # add remaining buckets from [last_bucket..<args.samples>]
    (next_bucket, value_of_next_bucket) = (int(interpolated_depths[-1].bucket) + 1, interpolated_depths[-1].value) if interpolated_depths else (0, 0)
    for bucket in range(next_bucket, int(args.samples) + 1):
        interpolated_depths.append(Depth(bucket, value_of_next_bucket, BUCKET_RANGES[bucket].max))

    # add buckets from [0..first_bucket]
    first_bucket = int(interpolated_depths[0].bucket)
    for bucket in reversed(range(0, first_bucket)):
        interpolated_depths.insert(0, Depth(bucket,0, BUCKET_RANGES[bucket].min))

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
def print_unified(sources):
    # Unlike the cumulative printer, we build the cumulative depth as we go!
    unified_cumulative_depths = []
    ax = create_plot("Unified")

    plots = []
    for source in sources:
        print("Adding ", source.name)
        sanitized_depths = offset_from_unified(get_interpolated(merge_and_sort(source.depths)), unified_cumulative_depths)
        (prices, individual_cumulative_depths) = depths_to_xy(sanitized_depths)
        plots.append({"name": source.name, "prices": prices, "individual_cumulative_depths": individual_cumulative_depths})

        # Update unified cumulative depths
        unified_cumulative_depths = sanitized_depths
 

    handles = []
    labels = []
    color_idx = 0
    #colors = ["#6262A6", "#181632", "#25CD2C", "#FB4C5A", "#5C51FE"]
    for single_plot in reversed(plots):
        handle = plot(ax, single_plot["prices"], single_plot["individual_cumulative_depths"])#, colors[color_idx])
        #color_idx = (color_idx + 1)%len(colors)
        handles.append(handle)
        labels.append(single_plot["name"])

    ax.legend(handles, labels)
    show_plot('unified')

if args.plot == 'individual':
    print_individual(sources)
elif args.plot == 'both':
    print_unified(sources)
    print_individual(sources)
else:
    print_unified(sources)
    
