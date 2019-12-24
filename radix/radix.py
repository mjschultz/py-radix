from socket import (getaddrinfo, gaierror,
                    inet_pton, inet_ntop, AF_INET, AF_INET6, SOCK_RAW,
                    AI_NUMERICHOST)

import pylru


class RadixPrefix(object):
    family = None
    bitlen = 0
    addr = None

    def __init__(self, network=None, masklen=None, packed=None):
        if network and packed:
            raise ValueError('Two address types specified. Please pick one.')
        if network is None and packed is None:
            self.addr = None
            self.bitlen = None

        if network:
            self._from_network(network, masklen)
        elif packed:
            self._from_packed(packed, masklen)

    def __str__(self):
        return '{0}/{1}'.format(self.network, self.bitlen)

    @property
    def packed(self):
        return bytes(self.addr)

    @property
    def network(self):
        if not self.addr:
            return None
        return inet_ntop(self.family, bytes(self.addr))

    def _inet_pton(self, family, sockaddr, masklen):
        addr = bytearray(inet_pton(family, sockaddr))
        if family == AF_INET:
            max_masklen = 32
        elif family == AF_INET6:
            max_masklen = 128
        quotient, remainder = divmod(masklen, 8)
        if remainder != 0:
            addr[quotient] = addr[quotient] & ((~0) << (8 - remainder))
            quotient += 1
        while quotient < max_masklen / 8:
            addr[quotient] = 0
            quotient += 1
        return addr

    def _from_network(self, network, masklen):
        split = network.split('/')
        if len(split) > 1:
            # network has prefix in it
            if masklen:
                raise ValueError('masklen specified twice')
            network = split[0]
            masklen = int(split[1])
        else:
            network = split[0]
        try:
            family, _, _, _, sockaddr = getaddrinfo(
                network, None, 0, SOCK_RAW, 6, AI_NUMERICHOST)[0]
        except gaierror as e:
            raise ValueError(e)
        if family == AF_INET:
            if masklen is None:
                masklen = 32
            if not (0 <= masklen <= 32):
                raise ValueError('invalid prefix length')
        elif family == AF_INET6:
            if masklen is None:
                masklen = 128
            if not (0 <= masklen <= 128):
                raise ValueError('invalid prefix length')
        else:
            return
        self.addr = self._inet_pton(family, sockaddr[0], masklen)
        self.bitlen = masklen
        self.family = family

    def _from_packed(self, packed, masklen):
        packed_len = len(packed)
        if packed_len == 4:
            family = AF_INET
            if masklen is None:
                masklen = 32
            if not (0 <= masklen <= 32):
                raise ValueError('invalid prefix length')
        elif packed_len == 16:
            family = AF_INET6
            if masklen is None:
                masklen = 128
            if not (0 <= masklen <= 128):
                raise ValueError('invalid prefix length')
        else:
            return
        self.addr = packed
        self.bitlen = masklen
        self.family = family


class RadixTree(object):
    def __init__(self):
        self.maxbits = 128
        self.head = None
        self.active_nodes = 0

    def _addr_test(self, addr, bitlen):
        left = addr[bitlen >> 3]
        right = 0x80 >> (bitlen & 0x07)
        return left & right

    def add(self, prefix):
        if self.head is None:
            # easy case
            node = RadixNode(prefix)
            self.head = node
            self.active_nodes += 1
            return node
        addr = prefix.addr
        bitlen = prefix.bitlen
        node = self.head
        # find the best place for the node
        while node.bitlen < bitlen or node._prefix.addr is None:
            if (node.bitlen < self.maxbits and
                    self._addr_test(addr, node.bitlen)):
                if node.right is None:
                    break
                node = node.right
            else:
                if node.left is None:
                    break
                node = node.left
        # find the first differing bit
        test_addr = node._prefix.addr
        check_bit = node.bitlen if node.bitlen < bitlen else bitlen
        differ_bit = 0
        i = 0
        while i * 8 < check_bit:
            r = addr[i] ^ test_addr[i]
            if r == 0:
                differ_bit = (i + 1) * 8
                i += 1
                continue
            # bitwise check
            for j in range(8):
                if r & (0x80 >> j):
                    break
            differ_bit = i * 8 + j
            break
        if differ_bit > check_bit:
            differ_bit = check_bit
        # now figure where to insert
        parent = node.parent
        while parent and parent.bitlen >= differ_bit:
            node, parent = parent, node.parent
        # found a match
        if differ_bit == bitlen and node.bitlen == bitlen:
            if isinstance(node._prefix, RadixGlue):
                node._prefix = prefix
            return node
        # no match, new node
        new_node = RadixNode(prefix)
        self.active_nodes += 1
        # fix it up
        if node.bitlen == differ_bit:
            new_node.parent = node
            if (node.bitlen < self.maxbits and
                    self._addr_test(addr, node.bitlen)):
                node.right = new_node
            else:
                node.left = new_node
            return new_node
        if bitlen == differ_bit:
            if bitlen < self.maxbits and self._addr_test(test_addr, bitlen):
                new_node.right = node
            else:
                new_node.left = node
            new_node.parent = node.parent
            if node.parent is None:
                self.head = new_node
            elif node.parent.right == node:
                node.parent.right = new_node
            else:
                node.parent.left = new_node
            node.parent = new_node
        else:
            glue_node = RadixNode(prefix_size=differ_bit, parent=node.parent)
            self.active_nodes += 1
            if differ_bit < self.maxbits and self._addr_test(addr, differ_bit):
                glue_node.right = new_node
                glue_node.left = node
            else:
                glue_node.right = node
                glue_node.left = new_node
            new_node.parent = glue_node
            if node.parent is None:
                self.head = glue_node
            elif node.parent.right == node:
                node.parent.right = glue_node
            else:
                node.parent.left = glue_node
            node.parent = glue_node
        return new_node

    def remove(self, node):
        if node.right and node.left:
            node._prefix.addr = None
            node.data = None
            node.bitlen = 0
            return
        if node.right is None and node.left is None:
            parent = node.parent
            self.active_nodes -= 1
            if parent is None:
                self.head = None
                return
            if parent.right == node:
                parent.right = None
                child = parent.left
            else:
                parent.left = None
                child = parent.right
            if parent._prefix.addr:
                return
            # remove the parent too
            if parent.parent is None:
                self.head = child
            elif parent.parent.right == parent:
                parent.parent.right = child
            else:
                parent.parent.left = child
            child.parent = parent.parent
            self.active_nodes -= 1
            return
        if node.right:
            child = node.right
        else:
            child = node.left
        parent = node.parent
        child.parent = parent
        self.active_nodes -= 1

        if parent is None:
            self.head = child
            return
        if parent.right == node:
            parent.right = child
        else:
            parent.left = child
        return

    def search_best(self, prefix):
        if self.head is None:
            return None
        node = self.head
        addr = prefix.addr
        bitlen = prefix.bitlen

        stack = []
        while node.bitlen < bitlen:
            if node._prefix.addr:
                stack.append(node)
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break
        if node and node._prefix.addr:
            stack.append(node)
        if len(stack) <= 0:
            return None
        for node in stack[::-1]:
            if (self._prefix_match(node._prefix, prefix, node.bitlen) and
                    node.bitlen <= bitlen):
                return node
        return None

    def search_exact(self, prefix):
        if self.head is None:
            return None
        node = self.head
        addr = prefix.addr
        bitlen = prefix.bitlen

        while node.bitlen < bitlen:
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                return None

        if node.bitlen > bitlen or node._prefix.addr is None:
            return None

        if self._prefix_match(node._prefix, prefix, bitlen):
            return node
        return None

    def search_worst(self, prefix):
        if self.head is None:
            return None
        node = self.head
        addr = prefix.addr
        bitlen = prefix.bitlen

        stack = []
        while node.bitlen < bitlen:
            if node._prefix.addr:
                stack.append(node)
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break
        if node and node._prefix.addr:
            stack.append(node)
        if len(stack) <= 0:
            return None
        for node in stack:
            if self._prefix_match(node._prefix, prefix, node.bitlen):
                return node
        return None

    def search_covered(self, prefix):
        results = []
        if self.head is None:
            return results
        node = self.head
        addr = prefix.addr
        bitlen = prefix.bitlen

        while node.bitlen < bitlen:
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                return results

        stack = [node]
        while stack:
            node = stack.pop()
            if self._prefix_match(node._prefix, prefix, prefix.bitlen):
                results.append(node)
            if node.right:
                stack.append(node.right)
            if node.left:
                stack.append(node.left)

        return results

    def _prefix_match(self, left, right, bitlen):
        l = left.addr
        r = right.addr
        if l is None or r is None:
            return False
        quotient, remainder = divmod(bitlen, 8)
        if l[:quotient] != r[:quotient]:
            return False
        if remainder == 0:
            return True
        mask = (~0) << (8 - remainder)
        if (l[quotient] & mask) == (r[quotient] & mask):
            return True
        return False


class RadixGlue(RadixPrefix):
    def __init__(self, bitlen=None):
        self.bitlen = bitlen


class RadixNode(object):
    count = 0

    def __init__(self, prefix=None, prefix_size=None, data={},
                 parent=None, left=None, right=None, node_id=None):
        if prefix:
            self.prefix = prefix
        else:
            self.prefix = RadixPrefix()
        self.parent = parent
        self.bitlen = self.prefix.bitlen
        self.left = left
        self.right = right
        self.data = data
        self.cache = {}

        self.free = True

        if node_id is None:
            self.node_id = RadixNode.count
            RadixNode.count += 1
        else:
            self.node_id = node_id


    def __str__(self):
        return self.prefix

    def __repr__(self):
        return '<{0}>'.format(self.prefix)

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

    @property
    def network(self):
        return self.prefix.network

    @property
    def prefixlen(self):
        return self.bitlen

    @property
    def family(self):
        return self.prefix.family

    @property
    def packed(self):
        return self.prefix.packed

    def __set_parent(self, parent):
        self.parent = parent

    def __get_parent(self):
        return self.parent

    # parent = property(__get_parent, __set_parent, None, "parent of node")


class Radix(object):
    def __init__(self):
        self.tree4 = RadixTree()
        self.tree6 = RadixTree()
        self.gen_id = 0            # detection of modifiction during iteration

    def add(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        if prefix.family == AF_INET:
            node = self.tree4.add(prefix)
        else:
            node = self.tree6.add(prefix)
        if node.data is None:
            node.data = {}
        self.gen_id += 1
        return node

    def delete(self, network=None, masklen=None, packed=None):
        node = self.search_exact(network, masklen, packed)
        if not node:
            raise KeyError('match not found')
        if node.family == AF_INET:
            self.tree4.remove(node)
        else:
            self.tree6.remove(node)
        self.gen_id += 1

    def search_exact(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        if prefix.family == AF_INET:
            node = self.tree4.search_exact(prefix)
        else:
            node = self.tree6.search_exact(prefix)
        if node and node.data is not None:
            return node
        else:
            return None

    def search_best(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        if prefix.family == AF_INET:
            node = self.tree4.search_best(prefix)
        else:
            node = self.tree6.search_best(prefix)
        if node and node.data is not None:
            return node
        else:
            return None

    def search_worst(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        if prefix.family == AF_INET:
            node = self.tree4.search_worst(prefix)
        else:
            node = self.tree6.search_worst(prefix)
        if node and node.data is not None:
            return node
        else:
            return None

    def search_covered(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        if prefix.family == AF_INET:
            return self.tree4.search_covered(prefix)
        else:
            return self.tree6.search_covered(prefix)

    def search_covering(self, network=None, masklen=None, packed=None):
        node = self.search_best(network=network, masklen=masklen,
                                packed=packed)
        stack = []
        while node is not None:
            if node._prefix.addr and node.data is not None:
                stack.append(node)
            node = node.parent
        return stack

    def _iter(self, node):
        stack = []
        while node is not None:
            if node._prefix.addr and node.data is not None:
                yield node
            if node.left:
                if node.right:
                    # we'll come back to it
                    stack.append(node.right)
                node = node.left
            elif node.right:
                node = node.right
            elif len(stack) != 0:
                node = stack.pop()
            else:
                break
        return

    def nodes(self):
        return [elt for elt in self]

    def prefixes(self):
        return [str(elt._prefix) for elt in self]

    def __iter__(self):
        init_id = self.gen_id
        for elt in self._iter(self.tree4.head):
            if init_id != self.gen_id:
                raise RuntimeWarning('detected modification during iteration')
            yield elt
        for elt in self._iter(self.tree6.head):
            if init_id != self.gen_id:
                raise RuntimeWarning('detected modification during iteration')
            yield elt


class AggregateRadix(object):
    '''
    PatriciaTree全体を表す．IPv6のみを格納する
    '''
    def __init__(self, root="::", bitlen=0, max_nodes=16):
        self.max_nodes = max_nodes - 2
        self.free_nodes = self.max_nodes
        self.maxbits = 128
        self.cache = pylru.lrucache(self.max_nodes)
        self.last_leaf_cache = self.cache.head.prev
        self.packet_count = 0
        self._init_lru()
        self._init_head(root, bitlen)

    def _init_lru(self):
        for i in range(self.max_nodes):
            self.cache[i] = RadixNode()

    def _init_head(self, root, bitlen):
        node = RadixNode(node_id=-1)
        node.set(RadixPrefix(root, bitlen))
        self.head = node

    def add_count(self, src_addr, dst_addr):
        '''
        src_addr <String> | <bytearray>
        dst_addr <String> | <bytearray>
        '''
        node = self.find(dst_addr, 128)
        if src_addr in node.data:
            node.data[src_addr] += 1
        else:
            node.data[src_addr] = 1
        self.packet_count += 1

        return node

    def find(self, address, masklen):
        # import pdb; pdb.set_trace()
        '''
        [input]
        address <String> | <bytearray>
        masklen <int>
        
        [output]
        node <PatriciaNode>

        [description]
        木を集約・探索・挿入する
        '''
        prefix = RadixPrefix(address, masklen)

        # reclaim node
        # print(f'free: {self.free_nodes}')

        if self.free_nodes <= 2:
            # print([x for x in self.cache.items()])
            self.reclaim_node(2)
            # print(f'reclaimed: {self.free_nodes}')

        addr = prefix.addr
        node = self.head

        while True:
            # nodeのプレフィクス内に挿入したいプレフィクスが含まれない場合
            if not (self.prefix_cmp(node.prefix, prefix)):
                return self.leaf_alloc(node, prefix)

            # 探索が成功した場合
            ## node.prefix内にprefixが含まれかつ，プレフィクス長が同じならnodeが検索対象のノードである
            elif (node.prefix.bitlen == prefix.bitlen):
                return node

            # これ以上探索できない場合
            elif (node.right is None):
                return self.leaf_alloc(node, prefix)

            # まだ探索できる場合
            if (node.bitlen < self.maxbits and self.addr_test(addr, node.bitlen)):
                node = node.right
            else:
                node = node.left

    def search_best(self, address, masklen):
        prefix = RadixPrefix(address, masklen)
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

        for node in stack[::-1]:
            if (self.prefix_match(node.prefix, prefix, node.bitlen) and node.bitlen <= bitlen):
               return node
        return None

    def search_worst(self, address, masklen):
        prefix = RadixPrefix(address, masklen)
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
    
    def search_covered(self, address, masklen):
        '''
        [input]:
        address <string> | <bytearray>
        masklen <int>

        [output]
        node <PatriciaNode>

        [description]
        与えられたプレフィクスに含まれるノードのうち，最もビット長の大きいノードを返す．
        exactに同じノードがあればそれを返す．
        '''
        prefix = RadixPrefix(address, masklen)
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

        for node in stack[::-1]:
            if self.prefix_match(node.prefix, prefix, node.bitlen):
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

        head = self.search_covered(dst_address, masklen)
        
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
        # import pdb; pdb.set_trace()
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
        node1<PatriciaNode>
        node2<PatriciaNode>

        [output]
        common_prefix<PatriciaPrefix>

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
        node_prefix<PatriciaPrefix>: 探索中の対象ノードのプレフィクス
        insert_prefix<PatriciaPrefx>: 挿入したいアドレスのプレフィクス

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
        prefix1 <PatriciaPrefix>
        prefix2 <PatriciaPrefix>
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
        node<PatriciaNode>
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
        node<PatriciaNode>
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
        # loop = 0
        while entry != self.last_leaf_cache.next:
            # freeノードならば次へ
            if entry.empty or entry.value.free or entry.value.right is not None:
                entry = entry.prev
                # loop += 1
                continue

            # print(loop)
            self.last_leaf_cache = entry.prev
            if entry.value is None:
                print(f'strange: {entry.value}, {entry.prev.value}')
            return entry.value

    def lru_move_tail(self, node):
        '''
        nodeをlruの一番うしろに持ってくる
        '''
        # print([(x,y) for x, y in self.cache.items()][:10])
        # print(node.node_id)
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
