from socket import getaddrinfo, inet_pton, inet_ntop, AF_INET, AF_INET6


class RadixPrefix(object):
    family = None
    bitlen = 0
    addr = None

    def __init__(self, network=None, masklen=None, packed=None):
        if network and packed:
            raise Exception('Two address types specified. Please pick one.')
        if network is None and packed is None:
            raise Exception('No address specified (use `address` or `packed`)')

        if network:
            self._from_network(network, masklen)
        elif packed:
            self._from_blob(packed, masklen)

    def __str__(self):
        return '{}/{}'.format(inet_ntop(self.family, self.addr), self.bitlen)

    def _from_network(self, network, masklen):
        split = network.split('/')
        if len(split) > 1:
            # network has prefix in it
            if masklen:
                raise Exception('masklen specified twice')
            network = split[0]
            masklen = int(split[1])
        else:
            network = split[0]
        family, _, _, _, sockaddr = getaddrinfo(network, None)[0]
        if family == AF_INET:
            if masklen is None:
                masklen = 32
            if not (0 <= masklen <= 32):
                raise Exception('invalid prefix length')
        elif family == AF_INET6:
            if masklen is None:
                masklen = 128
            if not (0 <= masklen <= 128):
                raise Exception('invalid prefix length')
        else:
            return
        self.bitlen = masklen
        self.addr = inet_pton(family, sockaddr[0])
        self.family = family

    def _from_blob(self, packed, masklen):
        packed_len = len(packed)
        if packed_len == 4:
            self.family = AF_INET
            if masklen is None:
                masklen = 32
            if not (0 <= masklen <= 32):
                raise Exception('invalid prefix length')
        elif packed_len == 16:
            self.family = AF_INET6
            if masklen is None:
                masklen = 128
            if not (0 <= masklen <= 128):
                raise Exception('invalid prefix length')
        else:
            return
        self.addr = packed
        self.bitlen = masklen


class RadixTree(object):
    def __init__(self):
        self.maxbits = 128
        self.head = None
        self.active_nodes = 0

    def _addr_test(self, addr, bitlen):
        left = ord(addr[bitlen >> 3])
        right = 0x80 >> (bitlen & 0x07)
        return left & right

    def lookup(self, prefix):
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
        while node.bitlen < bitlen or node.prefix is None:
            if node.bitlen < self.maxbits and self._addr_test(addr, node.bitlen):
                if node.right is None:
                    break
                node = node.right
            else:
                if node.left is None:
                    break
                node = node.left
        # find the first differing bit
        test_addr = node.prefix.addr
        check_bit = node.bitlen if node.bitlen < bitlen else bitlen
        differ_bit = 0
        for i in xrange(0, check_bit / 8):
            r = ord(addr[i]) ^ ord(test_addr[i])
            if r == 0:
                differ_bit = (i + 1) * 8
                continue
            # bitwise check
            for j in xrange(8):
                if r & (0x80 >> j):
                    break
            differ_bit = i * 8 + j
        if differ_bit > check_bit:
            differ_bit = check_bit
        # now figure where to insert
        parent = node.parent
        while parent and parent.bitlen >= differ_bit:
            node, parent = parent, node.parent
        # found a match
        if differ_bit == bitlen and node.bitlen == bitlen:
            if node.prefix is None:
                node.prefix = prefix
            return node
        # no match, new node
        new_node = RadixNode(prefix)
        self.active_nodes += 1
        # fix it up
        if node.bitlen == differ_bit:
            new_node.parent = node
            if node.bitlen < self.maxbits and self._addr_test(addr, node.bitlen):
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

    def search_best(self, prefix):
        if self.head is None:
            return None
        node = self.head
        addr = node.prefix.addr
        bitlen = node.bitlen

        stack = []
        while node.bitlen < bitlen:
            if node.prefix:
                stack.append(node)
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                break
        if node and node.prefix:
            stack.append(node)
        if len(stack) <= 0:
            return None
        for node in stack[::-1]:
            if (self._prefix_match(node.prefix, prefix, bitlen) and
                    node.prefix.bitlen <= bitlen):
                return node
        return None

    def search_exact(self, prefix):
        if self.head is None:
            return None
        node = self.head
        addr = node.prefix.addr
        bitlen = node.bitlen

        while node.bitlen < bitlen:
            if self._addr_test(addr, node.bitlen):
                node = node.right
            else:
                node = node.left
            if node is None:
                return None

        if node.bitlen > bitlen or node.prefix is None:
            return None

        if self._prefix_match(node.prefix, prefix, bitlen):
            return node
        return None

    def _prefix_match(self, left, right, bitlen):
        l = left.addr
        r = right.addr
        quotient, remainder = divmod(bitlen, 8)
        if l[:quotient] != r[:quotient]:
            return False
        lp = ord(l[quotient+1])
        rp = ord(r[quotient+1])
        for i in xrange(remainder):
            mask = 1 << (8 - i)
            if lp & mask != rp & mask:
                return False
        return True


class RadixNode(object):
    def __init__(self, prefix=None, prefix_size=None, data=None,
                 parent=None, left=None, right=None):
        self.prefix = prefix
        if prefix:
            self.bitlen = prefix.bitlen
        else:
            self.bitlen = prefix_size
        self.parent = parent
        self.left = left
        self.right = right
        self.data = data


class Radix(object):
    def __init__(self):
        self._tree = RadixTree()
        self._type = None
        self.gen_id = 0            # detection of modifiction during iteration

    def add(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        node = self._tree.lookup(prefix)
        node.data = {}
        self.gen_id += 1
        return node

    def delete(self):
        pass

    def search_exact(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        node = self._tree.search_exact(prefix)
        if node and node.data is not None:
            return node
        else:
            return None

    def search_best(self, network=None, masklen=None, packed=None):
        prefix = RadixPrefix(network, masklen, packed)
        node = self._tree.search_best(prefix)
        if node and node.data is not None:
            return node
        else:
            return None

    def _iter(self, attr=None):
        node = self._tree.head
        stack = []
        while True:
            print node.prefix
            if node.prefix and node.data is not None:
                if attr:
                    yield getattr(node, attr)
                else:
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

    def nodes(self):
        ret = []
        for elt in self._iter():
            ret.append(elt)
        return ret

    def prefixes(self):
        ret = []
        for elt in self._iter('prefix'):
            ret.append(str(elt))
        return ret

    def __getstate__(self):
        pass

    def __setstate__(self):
        pass

    def __reduce__(self):
        pass


class RadixIter(object):
    pass
