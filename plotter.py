import matplotlib.pyplot as plt
import collections

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

# Fake response from 0x API
responseJson = {
    "Uniswap": [{"input": 123, "output": 234}],
    "Balancer": [{"input": 124, "output": 458}],
    "0x": [{"input": 123, "output": 456}, {"input": 124, "output": 10}, {"input": 125, "output": 4}]
}

# Parse out sources
sources = []
for name,inouts in responseJson.items():
    cum_output = 0
    depths = [Depth(0,0,0)]
    for inout in inouts:
        depths.append(Depth(inout["input"], inout["output"], inout["output"] + cum_output))
        cum_output += inout["output"]
    sources.append(Source(name, depths))
  
# print(sources)


for source in sources:
    prices = []
    cumulative_depths = []
    for depth in source.depths:
        prices.append(depth.input)
        cumulative_depths.append(depth.cum_output)
    plot(source.name, prices, cumulative_depths)
    

