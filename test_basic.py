#!/usr/bin/env python3
"""
Basic tests for the new Rust-based radix implementation.
"""

import radix


def test_basic_operations():
    """Test basic add, search, and delete operations."""
    tree = radix.Radix()
    
    # Test adding nodes
    node1 = tree.add("10.0.0.0/8")
    assert node1.prefix == "10.0.0.0/8"
    assert node1.network == "10.0.0.0"
    assert node1.prefixlen == 8
    assert node1.family == 2  # AF_INET
    
    node2 = tree.add("10.0.0.0", 16)
    assert node2.prefix == "10.0.0.0/16"
    
    # Test exact search
    found = tree.search_exact("10.0.0.0/8")
    assert found is not None
    assert found.prefix == "10.0.0.0/8"
    
    # Test best match search
    best = tree.search_best("10.0.0.1")
    assert best is not None
    assert best.prefix == "10.0.0.0/16"  # Most specific match
    
    # Test worst match search
    worst = tree.search_worst("10.0.0.1")
    assert worst is not None
    assert worst.prefix == "10.0.0.0/8"  # Least specific match
    
    print("✓ Basic operations test passed")


def test_ipv6():
    """Test IPv6 functionality."""
    tree = radix.Radix()
    
    # Add IPv6 prefix
    node = tree.add("2001:db8::/32")
    assert node.prefix == "2001:db8::/32"
    assert node.family == 10  # AF_INET6
    
    # Search for IPv6 address
    found = tree.search_best("2001:db8::1")
    assert found is not None
    assert found.prefix == "2001:db8::/32"
    
    print("✓ IPv6 test passed")


def test_data_storage():
    """Test that we can store arbitrary data in nodes."""
    tree = radix.Radix()
    
    node = tree.add("192.168.1.0/24")
    
    # Test that we can access the data dict
    data = node.data
    assert isinstance(data, dict)
    
    print("✓ Data storage test passed")


def test_iteration():
    """Test iteration over tree nodes."""
    tree = radix.Radix()
    
    tree.add("10.0.0.0/8")
    tree.add("192.168.1.0/24")
    tree.add("2001:db8::/32")
    
    # Test nodes() method
    nodes = tree.nodes()
    assert len(nodes) == 3
    
    # Test prefixes() method
    prefixes = tree.prefixes()
    assert len(prefixes) == 3
    assert "10.0.0.0/8" in prefixes
    assert "192.168.1.0/24" in prefixes
    assert "2001:db8::/32" in prefixes
    
    # Test iteration
    count = 0
    for node in tree:
        count += 1
        assert hasattr(node, 'prefix')
    assert count == 3
    
    # Test len()
    assert len(tree) == 3
    
    print("✓ Iteration test passed")


def test_covered_search():
    """Test search for covered prefixes."""
    tree = radix.Radix()
    
    tree.add("10.0.0.0/8")
    tree.add("10.0.0.0/16")
    tree.add("10.0.0.0/24")
    tree.add("10.1.0.0/24")
    tree.add("192.168.1.0/24")
    
    # Search for prefixes covered by 10.0.0.0/8
    covered = tree.search_covered("10.0.0.0/8")
    covered_prefixes = [node.prefix for node in covered]
    
    assert "10.0.0.0/8" in covered_prefixes
    assert "10.0.0.0/16" in covered_prefixes
    assert "10.0.0.0/24" in covered_prefixes
    assert "10.1.0.0/24" in covered_prefixes
    assert "192.168.1.0/24" not in covered_prefixes
    
    print("✓ Covered search test passed")


def test_covering_search():
    """Test search for covering prefixes."""
    tree = radix.Radix()
    
    tree.add("10.0.0.0/8")
    tree.add("10.0.0.0/16")
    tree.add("10.0.0.0/24")
    tree.add("192.168.1.0/24")
    
    # Search for prefixes covering 10.0.0.0/24
    covering = tree.search_covering("10.0.0.0/24")
    covering_prefixes = [node.prefix for node in covering]
    
    assert "10.0.0.0/8" in covering_prefixes
    assert "10.0.0.0/16" in covering_prefixes
    assert "10.0.0.0/24" in covering_prefixes
    assert "192.168.1.0/24" not in covering_prefixes
    
    print("✓ Covering search test passed")


if __name__ == "__main__":
    test_basic_operations()
    test_ipv6()
    test_data_storage()
    test_iteration()
    test_covered_search()
    test_covering_search()
    print("\n🎉 All tests passed!")