import matplotlib.pyplot as plt
import collections

# Types
Depth = collections.namedtuple("Depth", ['input', 'output']) # input:uint, output:uint
Source = collections.namedtuple("Source", ['depths']) # depths:Depth[]

# Fake response from 0x API
responseJson = {
    "Uniswap": [{"input": 123, "output": 234}],
    "Balancer": [{"input": 124, "output": 458}],
    "0x": [{"input": 123, "output": 456}, {"input": 124, "output": 10}, {"input": 125, "output": 4}]
}




# Show chart
plt.plot([0, 123, 124, 125], [0, 234, 458, 4])
plt.ylabel('Depth')
plt.xlabel('Sources')
plt.show()

