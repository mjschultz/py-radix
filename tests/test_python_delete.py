import unittest

from radix.radix import Radix


class TestPythonDeletion(unittest.TestCase):
    def test_deleted_branch_preserves_children(self):
        cases = [
            ('10.0.0.0/8', '10.0.0.0/9', '10.128.0.0/9', '10.0.0.1', '10.128.0.1', '0.0.0.0/0'),
            ('1.2.2.0/23', '1.2.2.0/24', '1.2.3.0/24', '1.2.2.1', '1.2.3.1', '0.0.0.0/0'),
            ('2001:db8::/32', '2001:db8::/33', '2001:db8:8000::/33', '2001:db8::1', '2001:db8:8000::1', '::/0'),
        ]
        for parent, left, right, left_host, right_host, ancestor in cases:
            for internal in (False, True):
                with self.subTest(parent=parent, internal=internal):
                    tree = Radix()
                    if internal:
                        tree.add(ancestor)
                    tree.add(parent).data['deleted'] = True
                    left_node = tree.add(left)
                    right_node = tree.add(right)
                    left_node.data['side'] = 'left'
                    right_node.data['side'] = 'right'
                    tree.delete(parent)
                    self.assertIsNone(tree.search_exact(parent))
                    for prefix, host, node, side in [(left, left_host, left_node, 'left'),
                                                     (right, right_host, right_node, 'right')]:
                        self.assertIs(tree.search_exact(prefix), node)
                        self.assertIs(tree.search_best(host), node)
                        self.assertEqual(node.data['side'], side)
                    self.assertEqual({node.prefix for node in tree.search_covered(parent)}, {left, right})
                    self.assertEqual(set(tree.prefixes()), {left, right} | ({ancestor} if internal else set()))

                    # Restore the deleted branch, then remove it and each child.
                    restored = tree.add(parent)
                    self.assertEqual(restored.data, {})
                    self.assertIs(tree.search_exact(parent), restored)
                    self.assertIs(tree.search_worst(right_host), tree.search_exact(ancestor) if internal else restored)
                    self.assertIn(restored, tree.search_covering(right))
                    tree.delete(parent)
                    tree.delete(right)
                    self.assertIs(tree.search_exact(left), left_node)
                    self.assertIsNone(tree.search_exact(right))
                    tree.delete(left)
                    self.assertEqual(set(tree.prefixes()), {ancestor} if internal else set())
                    self.assertRaises(KeyError, tree.delete, right)
