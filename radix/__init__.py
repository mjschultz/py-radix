"""
Fast radix tree implementation for IPv4 and IPv6 network prefixes.

This is a Rust-based rewrite of the original py-radix library, providing
100% API compatibility with significant performance improvements.
"""

from ._radix_rs import RadixTree as _RadixTree, RadixNode as _RadixNode

__version__ = '0.10.0'
__all__ = ['Radix', 'RadixNode']


class Radix:
    """
    A radix tree for storing and retrieving IPv4 and IPv6 network prefixes.
    
    This is the main interface that provides the same API as the original
    py-radix library, but with improved performance through Rust implementation.
    """
    
    def __init__(self):
        self._tree = _RadixTree()
    
    def add(self, network=None, masklen=None, packed=None):
        """
        Add a network prefix to the radix tree.
        
        Args:
            network: Network address as string (e.g., "10.0.0.0" or "10.0.0.0/8")
            masklen: Optional mask length if not included in network
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            RadixNode: The node for this prefix
        """
        return self._tree.add(network=network, masklen=masklen, packed=packed)
    
    def delete(self, network=None, masklen=None, packed=None):
        """
        Delete a network prefix from the radix tree.
        
        Args:
            network: Network address as string (e.g., "10.0.0.0" or "10.0.0.0/8")
            masklen: Optional mask length if not included in network
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
        """
        return self._tree.delete(network=network, masklen=masklen, packed=packed)
    
    def search_exact(self, network=None, masklen=None, packed=None):
        """
        Search for an exact match of the given prefix.
        
        Args:
            network: Network address as string (e.g., "10.0.0.0" or "10.0.0.0/8")
            masklen: Optional mask length if not included in network
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            RadixNode or None: The matching node if found
        """
        return self._tree.search_exact(network=network, masklen=masklen, packed=packed)
    
    def search_best(self, network=None, packed=None):
        """
        Search for the longest matching prefix that contains the given address.
        
        Args:
            network: Network address as string
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            RadixNode or None: The best matching node if found
        """
        return self._tree.search_best(network=network, packed=packed)
    
    def search_worst(self, network=None, packed=None):
        """
        Search for the shortest matching prefix that contains the given address.
        
        Args:
            network: Network address as string
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            RadixNode or None: The worst matching node if found
        """
        return self._tree.search_worst(network=network, packed=packed)
    
    def search_covered(self, network=None, masklen=None, packed=None):
        """
        Search for all prefixes covered by the given prefix.
        
        Args:
            network: Network address as string (e.g., "10.0.0.0" or "10.0.0.0/8")
            masklen: Optional mask length if not included in network
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            List[RadixNode]: List of covered nodes
        """
        return self._tree.search_covered(network=network, masklen=masklen, packed=packed)
    
    def search_covering(self, network=None, masklen=None, packed=None):
        """
        Search for all prefixes that cover the given prefix.
        
        Args:
            network: Network address as string (e.g., "10.0.0.0" or "10.0.0.0/8")
            masklen: Optional mask length if not included in network
            packed: Binary packed address (4 bytes for IPv4, 16 for IPv6)
            
        Returns:
            List[RadixNode]: List of covering nodes
        """
        return self._tree.search_covering(network=network, masklen=masklen, packed=packed)
    
    def nodes(self):
        """
        Return all RadixNode objects in the tree.
        
        Returns:
            List[RadixNode]: List of all nodes
        """
        return self._tree.nodes()
    
    def prefixes(self):
        """
        Return all prefixes in the tree as strings.
        
        Returns:
            List[str]: List of all prefixes
        """
        return self._tree.prefixes()
    
    def __iter__(self):
        """Iterate over all nodes in the tree."""
        return iter(self._tree)
    
    def __len__(self):
        """Return the number of nodes in the tree."""
        return len(self._tree)


# Re-export RadixNode from the Rust implementation
RadixNode = _RadixNode