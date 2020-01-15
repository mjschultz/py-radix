import pylru
from radix import RadixNode, RadixPrefix, RadixTree

class AggradixNode(RadixNode):
    n_node = 0

    def __init__(self, node_id):
        super(AggradixNode, self).__init__()
        if node_id is None:
            self.node_id = AggradixNode.n_node
            AggradixNode.n_node += 1
        else:
            self.node_id = node_id

    def set(self, prefix):
        self.prefix = prefix
        self.bitlen = prefix.bitlen
        self.free = False

    def reset(self):
        self.prefix = None
        self.left = None
        self.right = None
        self.data = {}
        self.free = True

class AggradixTree(RadixTree):
    def __init__(self, aggradix="aggradix"):
        super(AggradixTree, self).__init__()

    def _common_prefix(self, node1, node2):
        '''
        Generate common prefix of node1 and node2.

        Args:
            node1 (RadixNode)
            node2 (RadixNode)

        Returns:
            RadixPrefix: common prefix of node1 and node2
        '''
        addr1 = node1.prefix.addr
        addr2 = node2.prefix.addr
        common_addr = bytearray(16)
        prefixmask = [0x00, 0x80, 0xc0, 0xe0, 0xf0, 0xf8, 0xfc, 0xfe]

        # differ_bit: addr1とaddr2の一致するビット長
        differ_bit = 0
        i = 0
        while i * 8 < 128:
            r = addr1[i] ^ addr2[i]
            if r == 0:
                differ_bit = (i + 1) * 8
                common_addr[i] = addr1[i]
                i += 1
                continue
            
            for j in range(8):
                if r & (0x80 >> j):
                    common_addr[i] = addr1[i] & prefixmask[j&7]
                    break
            differ_bit = i * 8 + j
            break

        return RadixPrefix(packed=common_addr, masklen=differ_bit)        

    def add(self, prefix):
        '''
        1. add without using RadixGlue
        2. do not append node under aggregated node
        '''
        pass

    def aggregate(self, n):

        pass

class Aggradix():
    def __init__(self, prefix, maxnode):
        self.tree = AggradixTree()
        self.maxnode = maxnode - 2
        self.free_nodes = self.maxnode
        self.packet_count = 0
        self.cache = pylru.lrucache(self.maxnode)
        self.last_leaf_cache = self.cache.head.prev
        self._init_lru()
        self._init_head(prefix)

    def _init_lru(self):
        for i in range(self.maxnode):
            self.cache[i] = RadixNode()

    def _init_head(self, prefix):
        '''
        Args:
            prefix (str): i.e. 2001:db8::/48
        '''
        node = RadixNode(node_id=-1)
        node.set(RadixPrefix(prefix))
        self.head = node

    def find_or_insert(self, address, prefixlen=128):
        target_prefix = RadixPrefix(address, prefixlen)

        if self.free_nodes <= 2:
            self.tree.aggregate(2)

if __name__ == "__main__":
    aggradix = AggradixTree()
