use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use std::collections::HashMap;
use std::net::IpAddr;
use std::str::FromStr;

use crate::prefix::Prefix;
use crate::node::RadixNode;

#[pyclass]
pub struct RadixTree {
    nodes: HashMap<String, RadixNode>,
}

#[pymethods]
impl RadixTree {
    #[new]
    fn new() -> Self {
        RadixTree {
            nodes: HashMap::new(),
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn add(
        &mut self,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<RadixNode> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                // CIDR format like "10.0.0.0/8"
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Separate network and masklen
                Prefix::from_network_masklen(&net, mask)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Packed address format
                Prefix::from_packed(&packed_addr, mask)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        if let Some(existing_node) = self.nodes.get(&key) {
            Ok(existing_node.clone_for_return())
        } else {
            let node = RadixNode::new_with_prefix(normalized_prefix);
            let return_node = node.clone_for_return();
            self.nodes.insert(key, node);
            Ok(return_node)
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn delete(
        &mut self,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<()> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                Prefix::from_network_masklen(&net, mask)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                Prefix::from_packed(&packed_addr, mask)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        if self.nodes.remove(&key).is_some() {
            Ok(())
        } else {
            Err(PyValueError::new_err("Node not found"))
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_exact(
        &self,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<RadixNode>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                Prefix::from_network_masklen(&net, mask)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                Prefix::from_packed(&packed_addr, mask)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        Ok(self.nodes.get(&key).map(|node| node.clone_for_return()))
    }
    
    #[pyo3(signature = (network = None, packed = None))]
    fn search_best(
        &self,
        network: Option<String>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<RadixNode>> {
        let addr = match (network, packed) {
            (Some(net), None) => {
                IpAddr::from_str(&net)
                    .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?
            }
            (None, Some(packed_addr)) => {
                match packed_addr.len() {
                    4 => {
                        let bytes: [u8; 4] = packed_addr.try_into()
                            .map_err(|_| PyValueError::new_err("Invalid IPv4 packed address"))?;
                        IpAddr::V4(std::net::Ipv4Addr::from(bytes))
                    }
                    16 => {
                        let bytes: [u8; 16] = packed_addr.try_into()
                            .map_err(|_| PyValueError::new_err("Invalid IPv6 packed address"))?;
                        IpAddr::V6(std::net::Ipv6Addr::from(bytes))
                    }
                    _ => return Err(PyValueError::new_err("Packed address must be 4 or 16 bytes")),
                }
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network or packed address"
                ));
            }
        };
        
        let mut best_match: Option<&RadixNode> = None;
        let mut best_len = 0;
        
        for node in self.nodes.values() {
            if node.prefix.contains(&addr) && node.prefix.prefix_len >= best_len {
                best_match = Some(node);
                best_len = node.prefix.prefix_len;
            }
        }
        
        Ok(best_match.map(|node| node.clone_for_return()))
    }
    
    #[pyo3(signature = (network = None, packed = None))]
    fn search_worst(
        &self,
        network: Option<String>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<RadixNode>> {
        let addr = match (network, packed) {
            (Some(net), None) => {
                IpAddr::from_str(&net)
                    .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?
            }
            (None, Some(packed_addr)) => {
                match packed_addr.len() {
                    4 => {
                        let bytes: [u8; 4] = packed_addr.try_into()
                            .map_err(|_| PyValueError::new_err("Invalid IPv4 packed address"))?;
                        IpAddr::V4(std::net::Ipv4Addr::from(bytes))
                    }
                    16 => {
                        let bytes: [u8; 16] = packed_addr.try_into()
                            .map_err(|_| PyValueError::new_err("Invalid IPv6 packed address"))?;
                        IpAddr::V6(std::net::Ipv6Addr::from(bytes))
                    }
                    _ => return Err(PyValueError::new_err("Packed address must be 4 or 16 bytes")),
                }
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network or packed address"
                ));
            }
        };
        
        let mut worst_match: Option<&RadixNode> = None;
        let mut worst_len = 255;
        
        for node in self.nodes.values() {
            if node.prefix.contains(&addr) && node.prefix.prefix_len <= worst_len {
                worst_match = Some(node);
                worst_len = node.prefix.prefix_len;
            }
        }
        
        Ok(worst_match.map(|node| node.clone_for_return()))
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_covered(
        &self,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<RadixNode>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                Prefix::from_network_masklen(&net, mask)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                Prefix::from_packed(&packed_addr, mask)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let mut covered = Vec::new();
        
        for node in self.nodes.values() {
            if prefix.contains_prefix(&node.prefix) {
                covered.push(node.clone_for_return());
            }
        }
        
        // Sort by prefix length (longest first)
        covered.sort_by(|a, b| b.prefix.prefix_len.cmp(&a.prefix.prefix_len));
        
        Ok(covered)
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_covering(
        &self,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<RadixNode>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                Prefix::from_network_masklen(&net, mask)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                Prefix::from_packed(&packed_addr, mask)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let mut covering = Vec::new();
        
        for node in self.nodes.values() {
            if node.prefix.contains_prefix(&prefix) {
                covering.push(node.clone_for_return());
            }
        }
        
        // Sort by prefix length (shortest first)
        covering.sort_by(|a, b| a.prefix.prefix_len.cmp(&b.prefix.prefix_len));
        
        Ok(covering)
    }
    
    fn nodes(&self) -> Vec<RadixNode> {
        self.nodes.values().map(|node| node.clone_for_return()).collect()
    }
    
    fn prefixes(&self) -> Vec<String> {
        self.nodes.keys().cloned().collect()
    }
    
    fn __iter__(slf: PyRef<Self>) -> PyResult<RadixIterator> {
        let nodes: Vec<RadixNode> = slf.nodes.values().map(|node| node.clone_for_return()).collect();
        Ok(RadixIterator { nodes, index: 0 })
    }
    
    fn __len__(&self) -> usize {
        self.nodes.len()
    }
}

#[pyclass]
pub struct RadixIterator {
    nodes: Vec<RadixNode>,
    index: usize,
}

#[pymethods]
impl RadixIterator {
    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }
    
    fn __next__(mut slf: PyRefMut<Self>) -> Option<RadixNode> {
        if slf.index < slf.nodes.len() {
            let node = slf.nodes[slf.index].clone_for_return();
            slf.index += 1;
            Some(node)
        } else {
            None
        }
    }
}