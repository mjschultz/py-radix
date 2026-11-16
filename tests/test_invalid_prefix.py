"""Keep validation errors consistent between allocating and lookup callers."""

import socket

import pytest

import radix


METHODS = ('add', 'delete', 'search_exact', 'search_best', 'search_worst',
           'search_covered', 'search_covering')
INVALID_PREFIXES = (
    (('10.0.0.0/33',), {}),
    (('2001:db8::/129',), {}),
    (('10.0.0.0',), {'masklen': 33}),
    (('2001:db8::',), {'masklen': 129}),
    (('10.0.0.0',), {'masklen': -2}),
    (('2001:db8::',), {'masklen': -2}),
)


@pytest.mark.parametrize('method', METHODS)
@pytest.mark.parametrize('args,kwargs', INVALID_PREFIXES)
def test_invalid_prefix_does_not_modify_tree(method, args, kwargs):
    tree = radix.Radix()
    ipv4 = tree.add('10.0.0.0/8')
    ipv6 = tree.add('2001:db8::/32')
    ipv4.data['route'] = 'ipv4'
    ipv6.data['route'] = 'ipv6'
    iterator = iter(tree)
    first = next(iterator)

    with pytest.raises(ValueError, match='invalid prefix length'):
        getattr(tree, method)(*args, **kwargs)

    assert {node.prefix for node in [first] + list(iterator)} == {
        '10.0.0.0/8', '2001:db8::/32'}
    assert tree.search_best('10.1.2.3') is ipv4
    assert tree.search_best('2001:db8::1') is ipv6
    assert ipv4.data == {'route': 'ipv4'}
    assert ipv6.data == {'route': 'ipv6'}


@pytest.mark.parametrize('network,masklen,family', (
    ('10.0.0.1', 32, socket.AF_INET),
    ('2001:db8::1', 128, socket.AF_INET6),
    ('0.0.0.0', 0, socket.AF_INET),
    ('::', 0, socket.AF_INET6),
))
def test_valid_prefixes_remain_usable(network, masklen, family):
    tree = radix.Radix()
    node = tree.add(network, masklen)
    assert node.family == family
    assert tree.search_exact(network, masklen) is node
    assert tree.search_best(network) is node
    assert tree.search_worst(network) is node
    assert tree.search_covered(network, masklen) == [node]
    assert tree.search_covering(network, masklen) == [node]
    with pytest.raises(KeyError):
        tree.delete('192.0.2.0/24')
    assert tree.search_exact(network, masklen) is node
    tree.delete(network, masklen)
    assert tree.prefixes() == []
