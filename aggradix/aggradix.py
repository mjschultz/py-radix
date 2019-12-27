import pylru
from .radix import RadixNode, RadixPrefix

class Aggradix(object):
    '''Radix Tree for IPv6 address with aggregation.

    Represents Radix Tree with LRU cache. It automatically aggregates itself.
    
    Attributes:
        max_nodes (int): maximum number of nodes in Radix Tree.
        free_nodes (int): number of nodes which is not in tree.
        maxbits (int): maximum length of bits of IPv6 address (fixed).
        packet_count (int): number of packets input.
        cache (pyrlu): LRU cache used when aggregation.
        last_leaf_cache (RadixNode): pointer to the last leaf cache in LRU cache.
        head (RadixNode): pointer to head node.
    '''
    def __init__(self, root="::", bitlen=0, max_nodes=16):
        self.max_nodes = max_nodes - 2
        self.free_nodes = self.max_nodes
        self.maxbits = 128
        self.packet_count = 0
        self.cache = pylru.lrucache(self.max_nodes)
        self.last_leaf_cache = self.cache.head.prev
        self._init_lru()
        self._init_head(root, bitlen)

    def _init_lru(self):
        '''Initialize LRU cache with ${max_nodes} of empty RadixNode.'''
        for i in range(self.max_nodes):
            self.cache[i] = RadixNode()

    def _init_head(self, address, prefixlen):
        '''
        Initalize head node with specific address space.
        ex) head node -> 2001:db8::/48

        Args:
            address (str): IPv6 network address.
            prefixlen (int): IPv6 network prefix length. 
        '''
        node = RadixNode(node_id=-1)
        node.set(RadixPrefix(address, prefixlen))
        self.head = node

    def add_count(self, src_addr, dst_addr):
        '''
        Search for ${dst_addr}/128.
        If failed, insert a node whose label is ${dst_addr}/128.
        Finally, add count of its hash table.

        Args:
            src_addr (str | bytearray): source IPv6 address.
            dst_addr (str | bytearray): destination IPv6 address.

        Returns:
            RadixNode: found or inserted node.
        '''
        node = self.find_or_insert(dst_addr)

        if src_addr in node.data:
            node.data[src_addr] += 1
        else:
            node.data[src_addr] = 1
        self.packet_count += 1

        return node

    def find_or_insert(self, address, prefixlen=128):
        '''
        Search for ${address}/${masklen}.
        If failed, insert a node whose label is ${dst_addr}/${masklen}.
        When LRU cache is full, aggregate the tree.

        Args:
            address (str | bytearray): IPv6 address to search.
            masklen (int): IPv6 prefix size.
        
        Returns:
            RadixNode: found or inserted node whose label is ${address}/${masklen}.

        '''
        target_prefix = RadixPrefix(address, prefixlen)

        # When LRU cahce is full, reclaim nodes to make space for new nodes.
        if self.free_nodes <= 2:
            self.reclaim_node(2)

        addr = target_prefix.addr
        node = self.head

        while True:
            # When ${prefix} is not contained in ${node}'s prefix.
            if not (self.prefix_cmp(node.prefix, target_prefix)):
                return self.leaf_alloc(node, target_prefix)

            # When search succeeded.
            ## If ${prefix} is contained in ${node}'s prefix AND prefix sizes are the same,
            ## ${node} is the target.
            elif (node.prefix.bitlen == target_prefix.bitlen):
                return node

            # When we cannot traverse tree more.
            elif (node.right is None):
                return self.leaf_alloc(node, target_prefix)

            # When we can traverse tree more.
            if (node.bitlen < self.maxbits and self.addr_test(addr, node.bitlen)):
                node = node.right
            else:
                node = node.left

    def search_best(self, address, prefixlen, head=None):
        '''
        Search Tree and returns best-match node.

        Args:
            address (str | bytearray): IPv6 network address to search.
            prefixlen (int): IPv6 network prefix to search.
            head (RadixNode): If given, search starts from the node.
        
        Returns:
            RadixNode | None: found node.
        '''
        prefix = RadixPrefix(address, prefixlen)

        if self.head is None:
            return None

        if head is None:
            node = self.head
        
        addr = prefix.addr
        bitlen = prefix.bitlen
        stack = []
        while node.bitlen < bitlen:
            stack.append(node)
            if self.addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break
        
        if node is not None:
            stack.append(node)
        
        if len(stack) <= 0:
            return None

        for node in stack[::-1]:
            if (self.prefix_match(node.prefix, prefix, node.bitlen) and node.bitlen <= bitlen):
               return node
        return None

    def search_worst(self, address, prefixlen):
        '''
        Search Tree and return worst-match node.

        Args:
            address (str | bytearray): IPv6 network address to search.
            prefixlen (int): IPv6 network prefix to search.
        
        Returns:
            RadixNode | None: found node.
        '''
        prefix = RadixPrefix(address, prefixlen)
        if self.head is None:
            return None
        node = self.head
        addr = prefix.addr
        bitlen = prefix.bitlen

        stack = []
        while node.bitlen < bitlen:
            stack.append(node)
            if self.addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break

        if node is not None:
            stack.append(node)

        if len(stack) <= 0:
            return None

        for node in stack:
            # print(node)
            if self.prefix_match(node.prefix, prefix, node.bitlen):
                return node
        return None
    
    def search_covered_top(self, address, prefixlen, node=None):
        '''
        Search Tree 
        It returns the node which is contained in given prefix AND has shortest prefix.
        If exact-match, it returns the node.

        ex) When tree is like follows,

                           o <-2001:db8::/64
                          / \
                ::/101-> o   o <- 2001:db8:0:0:8000::/127
                        / \
             ::/128 -> o   o <- ::600:1/128

            # Search for 2001:db8::/96,
            - when best-match -> 2001:db8::/64
            + when covered -> 2001:db8::/101

            Nodes contained in ::/96 are [::/101, ::/128, ::600:1/128].
            And ::/101 has shortest prefix in these nodes.

        Args:
            address (str | bytearray): IPv6 network address to search.
            prefixlen (int): IPv6 network prefix to search.
            node (RadixNode): If given, search starts from the node.
        
        Returns:
            RadixNode | None: found node.
        '''
        prefix = RadixPrefix(address, prefixlen)
        
        if self.head is None:
            return None
        
        if node is None:
            node = self.head
        
        addr = prefix.addr
        bitlen = prefix.bitlen

        stack = []
        while node.bitlen < bitlen:
            stack.append(node)
            if self.addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break

        if node is not None:
            stack.append(node)

        if len(stack) <= 0:
            return None

        for node in stack[::-1]:
            if self.prefix_match(node.prefix, prefix, node.bitlen):
               return node
        return None

    def search_exact(self, address, prefixlen, head=None):
        '''
        Search tree with exact-match.

        Args:
            address (str | bytearray): IPv6 network address to search.
            prefixlen (int): IPv6 network prefix to search.
            head (RadixNode): If given, search starts from the node.

        Returns:
            RadixNode | None: found node or None.
        '''
        target_prefix = RadixPrefix(address, prefixlen)
        
        if self.head is None:
            return None

        if head is None:
            node = self.head

        target_addr = target_prefix.addr # (bytearray)
        target_prefixlen = target_prefix.bitlen # (int)

        while node.bitlen < target_prefixlen:
            # right or left or finish
            if self.addr_test(target_addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                return None

        if node.bitlen > target_prefixlen:
            return None

        if self.prefix_match(node.prefix, target_prefix, target_prefixlen):
            return node

        return None

    def weighted_count(self, src_address, dst_address, masklen):
        '''
        dst_address/masklenに含まれるノードのうち，dst_address/128を含む枝の
        src_addressのカウント合計を求める
        ノードのプレフィクス長によって重み付けする
        '''
        prefix = RadixPrefix(dst_address, 128)
        addr = prefix.addr

        head = self.search_covered_top(dst_address, masklen)
        
        count = 0
        node = head
        while node is not None:
            if src_address in node.data.keys():
                # ノードのプレフィクス長によってカウント値を調整する場合
                count += node.data[src_address] * (1/2) ** (128 - node.bitlen)

            if self.addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
        return count

    def traverse_postorder(self, node=None):
        if node == None:
            return
        print(node.prefix)
        self.traverse_postorder(node.left)
        self.traverse_postorder(node.right)
    
    def subtree_sum(self, node=None, count=0):
        if node == None:
            return 0

        left_count = self.subtree_sum(node.left, count)
        right_count = self.subtree_sum(node.right, count)
        return count + sum(node.data.values()) + left_count + right_count

    def addr_test(self, addr, bitlen):
        '''
        [input]
        addr <bytesarray>: 挿入したいプレフィクスのネットワークアドレス
        bitlen <int>: 対象ノードのビット長
        
        [output]
        <int>: 0 ならば左，それ以外は右
        '''
        left = addr[bitlen >> 3]
        right = 0x80 >> (bitlen & 0x07)
        return left & right

    def common_prefix(self, node1, node2):
        '''
        [input]
        node1<RadixNode>
        node2<RadixNode>

        [output]
        common_prefix<RadixPrefix>

        [description]
        node1とnode2が共通にもつ最も小さいプレフィクスを生成する
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

    def differing_bit(self, addr1, addr2, check_bit=128):
        '''
        [input]
        addr1<bytearray>
        addr2<bytearray>
        check_bit<int>: 何ビット目まで見るか

        [output]
        differ_bit<int>: 一致するビット数またはcheck_bit

        [description]
        [0:check_bit]番目のaddr1とaddr2のビット列で，何ビットまで等しいかを求める
        '''
        differ_bit = 0
        i = 0
        while i * 8 < check_bit:
            r = addr1[i] ^ addr2[i]
            if r == 0:
                differ_bit = (i + 1) * 8
                i += 1
                continue
            for j in range(8):
                if r & (0x80 >> j):
                    break
            differ_bit = i * 8 + j
            break

        # differ_bit > check_bitだった場合はcheck_bitを返す
        return check_bit if differ_bit > check_bit else differ_bit

    def prefix_cmp(self, node_prefix, insert_prefix):
        '''
        [input]
        node_prefix<RadixPrefix>: 探索中の対象ノードのプレフィクス
        insert_prefix<RadixPrefix>: 挿入したいアドレスのプレフィクス

        [output]
        True | False <Bool>

        [description]
        node_prefixのプレフィクス長までのビット列の値が全て同じかどうか
        '''
        node_addr = node_prefix.addr
        insert_addr = insert_prefix.addr
        differ_bit = self.differing_bit(node_addr, insert_addr, check_bit=node_prefix.bitlen)

        # ノードのプレフィクス長までnode_addrとinsert_addrのビットの値が全て同じ場合
        ## insert_addrはnode_prefixに含まれる
        return differ_bit == node_prefix.bitlen

    def prefix_match(self, prefix1, prefix2, bitlen):
        '''
        [input]
        prefix1 <RadixPrefix>
        prefix2 <RadixPrefix>
        bitlen <int>

        [output]
        match <Bool>

        [description]
        prefix1とprefix2のaddressがbitlenの長さまで同一かどうか
        '''
        addr1 = prefix1.addr
        addr2 = prefix2.addr
        if addr1 is None or addr2 is None:
            return False
        quotient, remainder = divmod(bitlen, 8)
        if addr1[:quotient] != addr2[:quotient]:
            return False
        if remainder == 0:
            return True
        mask = (~0) << (8 - remainder)
        if (addr1[quotient] & mask) == (addr2[quotient] & mask):
            return True
        return False 

    def bit_test(self, node, bitnum):
        '''
        [input]
        node<RadixNode>
        bitlen<int>:

        [output]
        0 | 1 <int>

        [description]
        node.addrのbitnum番目が0か1かを返す
        '''
        bitpos = [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]
        offset = (bitnum-1)//8
        return node.prefix.addr[offset] & bitpos[(bitnum-1)&7]

    def bit_set(self, node, bitnum):
        '''
        [input]
        node<RadixNode>
        bitnum<int>

        [description]
        node.addrのbitnum番目のビットを1にする
        '''
        bitpos = [0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01]
        offset = (bitnum-1)//8
        node.prefix.addr[offset] |= bitpos[(bitnum-1) & 7]

    def lru_get_free(self):
        '''
        キャッシュの中からフリーなノードを取り出す
        '''
        entry = self.cache.head.prev
        while entry is not None:
            if entry.empty or not entry.value.free:
                entry = entry.prev
                continue

            return entry.value
    def lru_get_active(self):
        '''
        最も使われていないアクティブなleafノードを取り出す
        '''
        entry = self.last_leaf_cache
        while entry != self.last_leaf_cache.next:
            # freeノードならば次へ
            if entry.empty or entry.value.free or entry.value.right is not None:
                entry = entry.prev
                continue

            self.last_leaf_cache = entry.prev
            if entry.value is None:
                print(f'strange: {entry.value}, {entry.prev.value}')
            return entry.value

    def lru_move_tail(self, node):
        '''
        nodeをlruの一番うしろに持ってくる
        '''
        ## LRU cacheから対象ノードを探索する
        self.cache[node.node_id] = node
        entry = self.cache.head

        ## つなぎ替える
        self.cache.head = entry.next
        if self.cache.head.prev.value.node_id != node.node_id:
            print("not")

    def leaf_alloc(self, node, prefix):
        '''
        leafを2つ作る．
        '''
        leaf = self.lru_get_free()
        leaf.set(prefix)
        self.cache[leaf.node_id] = leaf
        branch = self.lru_get_free()
        branch.set(self.common_prefix(node, leaf))
        self.cache[branch.node_id] = branch
        self.free_nodes -= 2

        # 共通プレフィクス長がnodeのプレフィクス長と等しい場合
        if (branch.prefix.bitlen == node.prefix.bitlen):
            node.left = branch
            node.right = leaf

            branch.bitlen = 128
            branch.parent = node
            leaf.parent = node
        
        # 共通プレフィクスがnodeのプレフィクスよりも深い
        elif (branch.prefix.bitlen > node.prefix.bitlen):
            self.bit_set(branch, node.prefix.bitlen+1)
            node.left = leaf
            node.right = branch

            branch.bitlen = 128
            branch.parent = node
            leaf.parent = node

        # 共通プレフィクスがnodeのプレフィクスよりも浅い
        ## node.bitlen==128である場合など, branchの下にnodeとleafを配置
        else:
            if (node.parent.left == node):
                node.parent.left = branch
            else:
                node.parent.right = branch

            branch.parent = node.parent

            if self.bit_test(leaf, branch.bitlen+1):
                branch.left = node
                branch.right = leaf
            else:
                branch.left = leaf
                branch.right = node
            node.parent = branch
            leaf.parent = branch

        return leaf

    def leaf_free(self, leaf):
        '''
        leafとその親(branch point)を親ノードにマージ
        '''
        branch_point = leaf.parent
        parent = branch_point.parent

        data = parent.data
        for k, v in leaf.data.items():
            if k in data.keys():
                data[k] += v
            else:
                data[k] = v

        for k, v in branch_point.data.items():
            if k in data.keys():
                data[k] += v
            else:
                data[k] = v

        if branch_point.left == leaf:
            node = branch_point.right
        else:
            node = branch_point.left
        
        if parent.left == branch_point:
            parent.left = node
        else:
            parent.right = node

        node.parent = parent
        
        leaf.reset()
        self.lru_move_tail(leaf)
        branch_point.reset()
        self.lru_move_tail(branch_point)
        self.free_nodes += 2

    def subtree_merge(self, node, depth=0):
        if node is None:
            return {}

        data = node.data

        data_left = self.subtree_merge(node.left, depth+1)
        for k, v in data_left.items():
            if k in data.keys():
                data[k] += v
            else:
                data[k] = v

        data_right = self.subtree_merge(node.right, depth+1)
        for k, v in data_right.items():
            if k in data.keys():
                data[k] += v
            else:
                data[k] = v

        if depth > 0:
            if node.parent.left == node:
                node.parent.left = None
            else:
                node.parent.right = None
            self.free_nodes += 1

            node.reset()
            self.lru_move_tail(node)
        
        # 最初のコールだけ
        elif (depth == 0):
            node.data = data
            # print(f'here {node}: {data}')

        return data

    def reclaim_node(self, n):
        '''
        freenodeをn個減らす
        しきい値はprobeの合計数とする
        '''

        # 対象となるノードを探索する
        loopcount = 0
        while self.free_nodes < n:
            # とても簡単な集約閾値を設定する
            ## 合計パケット数と10の大きい方
            thr = self.packet_count * 0.3 if self.packet_count > 10 else 10

            leaf = self.lru_get_active()
            if leaf is None:
                print(f'strange: {leaf.node_id}')
                # pprint(self.cache)

            # leafのパケットの合計値が閾値より大きい場合は除外
            if sum(leaf.data.values()) > thr and loopcount < 10:
                self.cache[leaf.node_id] = leaf
                loopcount += 1
                continue

            parent = leaf.parent
            if parent.left == leaf:
                sibling = parent.right
            else:
                sibling = parent.left

            sibling_count = self.subtree_sum(sibling)
            parent_count = sum(parent.data.values())

            need_sibling = sibling_count > thr
            need_parent = (parent == self.head) or (parent_count > thr)

            if need_parent and need_sibling:
                self.cache[leaf.node_id] = leaf
                loopcount += 1
                continue
            
            elif need_sibling:
                self.leaf_free(leaf)
            else:
                self.subtree_merge(leaf.parent)
