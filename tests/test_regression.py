#!/usr/bin/env python

# Copyright (c) 2004 Damien Miller <djm@mindrot.org>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

# $Id$

import sys
import radix
import unittest
import socket
import struct
import pickle
if sys.version_info[0] >= 3:
    # for Py3K
    t14_packed_addr = struct.pack('4B', 0xe0, 0x14, 0x0b, 0x40)
    t15_packed_addr = struct.pack(
        '16B',
        0xde, 0xad, 0xbe, 0xef, 0x12, 0x34, 0x56, 0x78,
        0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x00, 0x00, 0x00)
else:
    # for 2.x
    import cPickle
    t14_packed_addr = '\xe0\x14\x0b@'
    t15_packed_addr = ('\xde\xad\xbe\xef\x124Vx'
                       '\x9a\xbc\xde\xf0\x00\x00\x00\x00')


class TestRadix(unittest.TestCase):
    def test_00__create_destroy(self):
        tree = radix.Radix()
        self.assertTrue('radix.Radix' in str(type(tree)))
        del tree

    def test_01__create_node(self):
        tree = radix.Radix()
        node = tree.add("10.0.0.0/8")
        self.assertTrue('radix.RadixNode' in str(type(node)))
        self.assertEqual(node.prefix, "10.0.0.0/8")
        self.assertEqual(node.network, "10.0.0.0")
        self.assertEqual(node.prefixlen, 8)
        self.assertEqual(node.family, socket.AF_INET)
        node = tree.add("10.0.0.0", 16)
        self.assertEqual(node.network, "10.0.0.0")
        self.assertEqual(node.prefixlen, 16)
        node = tree.add(network="10.0.0.0", masklen=24)
        self.assertEqual(node.network, "10.0.0.0")
        self.assertEqual(node.prefixlen, 24)
        node2 = tree.add(network="ff00::", masklen=24)
        self.assertEqual(node2.network, "ff00::")
        self.assertEqual(node2.prefixlen, 24)
        self.assertTrue(node is not node2)

    def test_02__node_userdata(self):
        tree = radix.Radix()
        node = tree.add(network="10.0.0.0", masklen=28)
        node.data["blah"] = "abc123"
        node.data["foo"] = 12345
        self.assertEqual(node.data["blah"], "abc123")
        self.assertEqual(node.data["foo"], 12345)
        self.assertRaises(AttributeError, lambda x: x.nonexist, node)
        del node.data["blah"]
        self.assertRaises(KeyError, lambda x: x.data["blah"], node)

    def test_03__search_exact(self):
        tree = radix.Radix()
        node1 = tree.add("10.0.0.0/8")
        node2 = tree.add("10.0.0.0/16")
        node3 = tree.add("10.0.0.0/24")
        node2.data["foo"] = 12345
        node = tree.search_exact("127.0.0.1")
        self.assertEqual(node, None)
        node = tree.search_exact("10.0.0.0")
        self.assertEqual(node, None)
        node = tree.search_exact("10.0.0.0/24")
        self.assertEqual(node, node3)
        node = tree.search_exact("10.0.0.0/8")
        self.assertEqual(node, node1)
        node = tree.search_exact("10.0.0.0/16")
        self.assertEqual(node.data["foo"], 12345)

    def test_04__search_best(self):
        tree = radix.Radix()
        node2 = tree.add("10.0.0.0/16")
        node3 = tree.add("10.0.0.0/24")
        node = tree.search_best("127.0.0.1")
        self.assertEqual(node, None)
        node = tree.search_best("10.0.0.0")
        self.assertEqual(node, node3)
        node = tree.search_best("10.0.0.0/24")
        self.assertEqual(node, node3)
        node = tree.search_best("10.0.1.0/24")
        self.assertEqual(node, node2)

    def test_05__concurrent_trees(self):
        tree1 = radix.Radix()
        node1_2 = tree1.add("10.0.0.0/16")
        node1_3 = tree1.add("10.0.0.0/24")
        node1_3.data["blah"] = 12345
        tree2 = radix.Radix()
        node2_2 = tree2.add("10.0.0.0/16")
        node2_3 = tree2.add("10.0.0.0/24")
        node2_3.data["blah"] = 45678
        self.assertNotEqual(tree1, tree2)
        self.assertNotEqual(node1_2, node2_2)
        node = tree1.search_best("10.0.1.0/24")
        self.assertEqual(node, node1_2)
        self.assertNotEqual(node, node2_2)
        node = tree2.search_best("20.0.0.0/24")
        self.assertEqual(node, None)
        node = tree2.search_best("10.0.0.10")
        self.assertEqual(node.data["blah"], 45678)

    def test_06__deletes(self):
        tree = radix.Radix()
        node1 = tree.add("10.0.0.0/8")
        self.assertRaises(KeyError, tree.delete, "127.0.0.1")
        self.assertRaises(KeyError, tree.delete, "10.0.0.0/24")
        node = tree.search_best("10.0.0.10")
        self.assertEqual(node, node1)

    def test_07__nodes(self):
        tree = radix.Radix()
        prefixes = [
            "10.0.0.0/8", "127.0.0.1/32",
            "10.1.0.0/16", "10.100.100.100/32",
            "abcd:ef12::/32", "abcd:ef01:2345:6789::/64", "::1/128"
        ]
        prefixes.sort()
        for prefix in prefixes:
            tree.add(prefix)
        nodes = tree.nodes()
        addrs = list(map(lambda x: x.prefix, nodes))
        addrs.sort()
        self.assertEqual(addrs, prefixes)

    def test_08__nodes_empty_tree(self):
        tree = radix.Radix()
        nodes = tree.nodes()
        self.assertEqual(nodes, [])

    def test_09__prefixes(self):
        tree = radix.Radix()
        prefixes = [
            "10.0.0.0/8", "127.0.0.1/32",
            "10.1.0.0/16", "10.100.100.100/32",
            "abcd:ef12::/32", "abcd:ef01:2345:6789::/64", "::1/128"
        ]
        prefixes.sort()
        for prefix in prefixes:
            tree.add(prefix)
        addrs = tree.prefixes()
        addrs.sort()
        self.assertEqual(addrs, prefixes)

    def test_10__use_after_free(self):
        tree = radix.Radix()
        node1 = tree.add("10.0.0.0/8")
        del tree
        self.assertEquals(node1.prefix, "10.0.0.0/8")

    def test_11__unique_instance(self):
        tree = radix.Radix()
        node1 = tree.add("10.0.0.0/8")
        node2 = tree.add("10.0.0.0/8")
        self.assertTrue(node1 is node2)
        self.assertTrue(node1.prefix is node2.prefix)

    def test_12__inconsistent_masks4(self):
        tree = radix.Radix()
        node1 = tree.add("10.255.255.255", 28)
        node2 = tree.add(network="10.255.255.240/28")
        node3 = tree.add(network="10.255.255.252", masklen=28)
        self.assertTrue(node1 is node2)
        self.assertTrue(node1 is node3)
        self.assertEquals(node1.prefix, "10.255.255.240/28")

    def test_13__inconsistent_masks6(self):
        tree = radix.Radix()
        node1 = tree.add("dead:beef:1234:5678::", 32)
        node2 = tree.add(network="dead:beef:8888:9999::/32")
        node3 = tree.add(network="dead:beef::", masklen=32)
        self.assertTrue(node1 is node2)
        self.assertTrue(node1 is node3)
        self.assertEquals(node1.prefix, "dead:beef::/32")

    def test_14__packed_addresses4(self):
        tree = radix.Radix()
        p = struct.pack('4B', 0xe0, 0x14, 0x0b, 0x40)
        node = tree.add(packed=p, masklen=26)
        self.assertEquals(node.family, socket.AF_INET)
        self.assertEquals(node.prefix, "224.20.11.64/26")
        self.assertEquals(node.packed, p)

    def test_15__packed_addresses6(self):
        tree = radix.Radix()
        p = struct.pack(
            '16B',
            0xde, 0xad, 0xbe, 0xef, 0x12, 0x34, 0x56, 0x78,
            0x9a, 0xbc, 0xde, 0xf0, 0x00, 0x00, 0x00, 0x00)
        node = tree.add(packed=p, masklen=108)
        self.assertEquals(node.family, socket.AF_INET6)
        self.assertEquals(
            node.prefix,
            "dead:beef:1234:5678:9abc:def0::/108")
        self.assertEquals(node.packed, p)

    def test_16__bad_addresses(self):
        tree = radix.Radix()
        self.assertRaises(TypeError, tree.add)
        self.assertRaises(ValueError, tree.add, "blah/32")
        self.assertRaises(ValueError, tree.add, "blah", 32)
        self.assertRaises(ValueError, tree.add, "127.0.0.1", -2)
        self.assertRaises(ValueError, tree.add, "127.0.0.1", 64)
        self.assertRaises(ValueError, tree.add, "::", -2)
        self.assertRaises(ValueError, tree.add, "::", 256)
        self.assertEquals(len(tree.nodes()), 0)

    def test_17__mixed_address_family(self):
        tree = radix.Radix()
        node1 = tree.add("255.255.255.255", 32)
        node2 = tree.add("ffff::/32")
        node1_o = tree.search_best("255.255.255.255")
        node2_o = tree.search_best("ffff::")
        self.assertTrue(node1 is node1_o)
        self.assertTrue(node2 is node2_o)
        self.assertNotEquals(node1.prefix, node2.prefix)
        self.assertNotEquals(node1.network, node2.network)
        self.assertNotEquals(node1.family, node2.family)

    def test_18__iterator(self):
        tree = radix.Radix()
        prefixes = [
            "::1/128", "2000::/16", "2000::/8", "dead:beef::/64",
            "ffff::/16", "10.0.0.0/8", "a00::/8", "255.255.0.0/16",
            "::/0", "0.0.0.0/0"
        ]
        prefixes.sort()
        for prefix in prefixes:
            tree.add(prefix)
        iterprefixes = []
        for node in tree:
            iterprefixes.append(node.prefix)
        iterprefixes.sort()
        self.assertEqual(iterprefixes, prefixes)

    def test_19__iterate_on_empty(self):
        tree = radix.Radix()
        prefixes = []
        for node in tree:
            prefixes.append(node.prefix)
        self.assertEqual(prefixes, [])

    def test_20__iterate_and_modify_tree(self):
        tree = radix.Radix()
        prefixes = [
            "::1/128", "2000::/16", "2000::/8", "dead:beef::/64",
            "0.0.0.0/8", "127.0.0.1/32"
        ]
        prefixes.sort()
        for prefix in prefixes:
            tree.add(prefix)

        def iter_mod(t):
            [t.delete(x.prefix) for x in t]
        self.assertRaises(RuntimeWarning, iter_mod, tree)

    def test_21__lots_of_prefixes(self):
        tree = radix.Radix()
        num_nodes_in = 0
        for i in range(0, 128):
            for j in range(0, 128):
                k = ((i + j) % 8) + 24
                node = tree.add("1.%d.%d.0" % (i, j), k)
                node.data["i"] = i
                node.data["j"] = j
                num_nodes_in += 1

        num_nodes_del = 0
        for i in range(0, 128, 5):
            for j in range(0, 128, 3):
                k = ((i + j) % 8) + 24
                tree.delete("1.%d.%d.0" % (i, j), k)
                num_nodes_del += 1

        num_nodes_out = 0
        for node in tree:
            i = node.data["i"]
            j = node.data["j"]
            k = ((i + j) % 8) + 24
            prefix = "1.%d.%d.0/%d" % (i, j, k)
            self.assertEquals(node.prefix, prefix)
            num_nodes_out += 1

        self.assertEquals(num_nodes_in - num_nodes_del, num_nodes_out)
        self.assertEquals(
            num_nodes_in - num_nodes_del,
            len(tree.nodes()))

    def test_22__broken_sanitise(self):
        tree = radix.Radix()
        node = tree.add("255.255.255.255/15")
        self.assertEquals(node.prefix, "255.254.0.0/15")

    def test_21__pickle(self):
        tree = radix.Radix()
        num_nodes_in = 0
        for i in range(0, 128):
            for j in range(0, 128):
                k = ((i + j) % 8) + 24
                addr = "1.%d.%d.0" % (i, j)
                node = tree.add(addr, k)
                node.data["i"] = i
                node.data["j"] = j
                num_nodes_in += 1
        tree_pickled = pickle.dumps(tree)
        del tree
        tree2 = pickle.loads(tree_pickled)
        for i in range(0, 128):
            for j in range(0, 128):
                k = ((i + j) % 8) + 24
                addr = "1.%d.%d.0" % (i, j)
                node = tree2.search_exact(addr, k)
                self.assertNotEquals(node, None)
                self.assertEquals(node.data["i"], i)
                self.assertEquals(node.data["j"], j)
                node.data["j"] = j
        self.assertEquals(len(tree2.nodes()), num_nodes_in)

    def test_21__cpickle(self):
        if sys.version_info[0] >= 3:
            return
        tree = radix.Radix()
        num_nodes_in = 0
        for i in range(0, 128):
            for j in range(0, 128):
                k = ((i + j) % 8) + 24
                addr = "1.%d.%d.0" % (i, j)
                node = tree.add(addr, k)
                node.data["i"] = i
                node.data["j"] = j
                num_nodes_in += 1
        tree_pickled = cPickle.dumps(tree)
        del tree
        tree2 = cPickle.loads(tree_pickled)
        for i in range(0, 128):
            for j in range(0, 128):
                k = ((i + j) % 8) + 24
                addr = "1.%d.%d.0" % (i, j)
                node = tree2.search_exact(addr, k)
                self.assertNotEquals(node, None)
                self.assertEquals(node.data["i"], i)
                self.assertEquals(node.data["j"], j)
                node.data["j"] = j
        self.assertEquals(len(tree2.nodes()), num_nodes_in)

    def test_22_search_best(self):
        tree = radix.Radix()
        tree.add('10.0.0.0/8')
        tree.add('10.0.0.0/13')
        tree.add('10.0.0.0/16')
        self.assertEquals(
            tree.search_best('10.0.0.0/15').prefix,
            '10.0.0.0/13')

    def test_23_add_with_glue(self):
        # https://github.com/mjschultz/py-radix/issues/3
        tree = radix.Radix()
        tree.add('1.0.24.0/23')
        tree.add('1.0.26.0/23')
        tree.add('1.0.28.0/22')
        expected = ['1.0.24.0/23', '1.0.26.0/23', '1.0.28.0/22']
        self.assertEqual(expected, [n.prefix for n in tree])

    def test_24_search_worst(self):
        tree = radix.Radix()
        tree.add('10.0.0.0/8')
        tree.add('10.0.0.0/13')
        tree.add('10.0.0.0/16')
        self.assertEquals(
            tree.search_worst('10.0.0.0/15').prefix,
            '10.0.0.0/8')
        self.assertEquals(
            tree.search_worst('100.0.0.0/15'),
            None)

    def test_25_search_covered(self):
        tree = radix.Radix()
        tree.add('10.0.0.0/8')
        tree.add('10.0.0.0/13')
        tree.add('10.0.0.0/31')
        tree.add('11.0.0.0/16')
        self.assertEquals(
            [n.prefix for n in tree.search_covered('10.0.0.0/8')],
            ['10.0.0.0/8', '10.0.0.0/13', '10.0.0.0/31'])
        self.assertEquals(
            [n.prefix for n in tree.search_covered('11.0.0.0/8')],
            ['11.0.0.0/16'])
        self.assertEquals(
            [n.prefix for n in tree.search_covered('21.0.0.0/8')],
            [])
        self.assertEquals(
            [n.prefix for n in tree.search_covered('0.0.0.0/0')],
            ['10.0.0.0/8', '10.0.0.0/13', '10.0.0.0/31', '11.0.0.0/16'])

def main():
    unittest.main()

if __name__ == '__main__':
    main()
