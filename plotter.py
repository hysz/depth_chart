import matplotlib.pyplot as plt
import collections
import json
import sys
from functools import cmp_to_key

# Types
Depth = collections.namedtuple("Depth", ['input', 'output', 'cum_output']) # input:uint, output:uint, cum_output:uint
Source = collections.namedtuple("Source", ['name', 'depths']) # depths:Depth[]

def plot(name, prices, cumulative_depths):
    fig, ax = plt.subplots()
    ax.set_title(name)
    ax.fill_between(prices, 0, cumulative_depths)
    plt.ylabel('Depth')
    plt.xlabel('Price')
    plt.show()
    #plt.savefig('%s.png'%(name), bbox_inches='tight')

# Fake response from 0x API
'''
response_json = {
    "Uniswap": [{"input": 123, "output": 234}],
    "Balancer": [{"input": 124, "output": 458}],
    "0x": [{"input": 123, "output": 456}, {"input": 124, "output": 10}, {"input": 125, "output": 4}]
}
'''


raw_json = json.load(open('./raw'))

response_json = {}
for quote_list in raw_json['dexQuotes']:
    for quote in quote_list:
        if not quote["source"] in response_json:
            response_json[quote["source"]] = []
        response_json[quote["source"]].append({"input": float(quote["input"]), "output": float(quote["output"])})





# Parse out sources
sources = []
for name,inouts in response_json.items():
    cum_output = 0
    depths = [Depth(0,0,0)]
    for inout in inouts:
        depths.append(Depth(inout["input"], inout["output"], inout["output"] + cum_output))
        cum_output += inout["output"]
    sources.append(Source(name, depths))
  
# print(sources)

def depths_to_xy(depths):
    prices = []
    cumulative_depths = []
    for depth in depths:
        prices.append(depth.input)
        cumulative_depths.append(depth.cum_output)
    return (prices, cumulative_depths)

def print_individual(sources):
    for source in sources:
        (prices, cumulative_depths) = depths_to_xy(source.depths)
        plot(source.name, prices, cumulative_depths)

def compare_depths(d1, d2):
    if d1.input < d2.input:
        return -1
    elif d1.input > d2.input:
        return 1
    else:
        return 0

def merge_and_sort(depths):
    merged_depths = []
    for depth in sorted(depths,  key=cmp_to_key(compare_depths)):
        if merged_depths and merged_depths[-1].input == depth.input:
            print(merged_depths)
            merged_depths[-1] = Depth(merged_depths[-1].input, -1, merged_depths[-1].cum_output + depth.cum_output)
        else:
            merged_depths.append(depth)

    return merged_depths


def print_unified(sources):
    cumulative_depths = [depth for source in sources for depth in source.depths]  
    (prices, cumulative_depths) = depths_to_xy(merge_and_sort(cumulative_depths))  
    plot("Cumulative", prices, cumulative_depths)

print_unified(sources)
    
