use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyKeyError, PyTypeError};
use std::collections::HashMap;
use std::net::IpAddr;
use std::str::FromStr;

use crate::prefix::Prefix;
use crate::node::RadixNode;

enum SearchTarget {
    Address(IpAddr),
    Prefix(Prefix),
}

#[pyclass]
pub struct RadixTree {
    py_nodes: HashMap<String, Py<RadixNode>>,
}

#[pymethods]
impl RadixTree {
    #[new]
    fn new() -> Self {
        RadixTree {
            py_nodes: HashMap::new(),
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn add(
        &mut self,
        py: Python,
        network: Option<String>,
        masklen: Option<i32>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<PyObject> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                // CIDR format like "10.0.0.0/8"
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Separate network and masklen - validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_network_masklen(&net, mask as u8)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Packed address format - validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_packed(&packed_addr, mask as u8)?
            }
            _ => {
                return Err(PyTypeError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        if let Some(existing_py_node) = self.py_nodes.get(&key) {
            Ok(existing_py_node.clone_ref(py).into())
        } else {
            let node = RadixNode::new_with_prefix(py, normalized_prefix);
            let py_node = Py::new(py, node)?;
            
            // Store the Python object
            self.py_nodes.insert(key, py_node.clone_ref(py));
            
            Ok(py_node.into())
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn delete(
        &mut self,
        network: Option<String>,
        masklen: Option<i32>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<()> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_network_masklen(&net, mask as u8)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_packed(&packed_addr, mask as u8)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        if self.py_nodes.remove(&key).is_some() {
            Ok(())
        } else {
            Err(PyKeyError::new_err("match not found"))
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_exact(
        &self,
        py: Python,
        network: Option<String>,
        masklen: Option<i32>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<PyObject>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_network_masklen(&net, mask as u8)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_packed(&packed_addr, mask as u8)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let normalized_prefix = Prefix::new(prefix.network_addr(), prefix.prefix_len)?;
        let key = normalized_prefix.prefix();
        
        Ok(self.py_nodes.get(&key).map(|py_node| py_node.clone_ref(py).into()))
    }
    
    #[pyo3(signature = (network = None, packed = None))]
    fn search_best(
        &self,
        py: Python,
        network: Option<String>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<PyObject>> {
        let search_target = match (network, packed) {
            (Some(net), None) => {
                // Try to parse as CIDR first, then as IP address
                if net.contains('/') {
                    // For CIDR notation, we need to find prefixes that contain the entire range
                    let search_prefix = Prefix::from_str(&net)?;
                    SearchTarget::Prefix(search_prefix)
                } else {
                    // For IP address, find prefixes that contain this address
                    let addr = IpAddr::from_str(&net)
                        .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?;
                    SearchTarget::Address(addr)
                }
            }
            (None, Some(packed_addr)) => {
                let addr = match packed_addr.len() {
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
                };
                SearchTarget::Address(addr)
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network or packed address"
                ));
            }
        };
        
        let mut best_match: Option<&str> = None;
        let mut best_len = 0;
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            let matches = match &search_target {
                SearchTarget::Address(addr) => {
                    // For address search, find prefixes that contain this address
                    node_ref.prefix.contains(addr)
                }
                SearchTarget::Prefix(search_prefix) => {
                    // For prefix search, find prefixes that contain the entire search prefix
                    node_ref.prefix.contains_prefix(search_prefix)
                }
            };
            
            if matches && node_ref.prefix.prefix_len >= best_len {
                best_match = Some(key);
                best_len = node_ref.prefix.prefix_len;
            }
        }
        
        Ok(best_match.and_then(|key| self.py_nodes.get(key).map(|py_node| py_node.clone_ref(py).into())))
    }
    
    #[pyo3(signature = (network = None, packed = None))]
    fn search_worst(
        &self,
        py: Python,
        network: Option<String>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<PyObject>> {
        let search_target = match (network, packed) {
            (Some(net), None) => {
                // Try to parse as CIDR first, then as IP address
                if net.contains('/') {
                    // For CIDR notation, we need to find prefixes that contain the entire range
                    let search_prefix = Prefix::from_str(&net)?;
                    SearchTarget::Prefix(search_prefix)
                } else {
                    // For IP address, find prefixes that contain this address
                    let addr = IpAddr::from_str(&net)
                        .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?;
                    SearchTarget::Address(addr)
                }
            }
            (None, Some(packed_addr)) => {
                let addr = match packed_addr.len() {
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
                };
                SearchTarget::Address(addr)
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network or packed address"
                ));
            }
        };
        
        let mut worst_match: Option<&str> = None;
        let mut worst_len = 255;
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            let matches = match &search_target {
                SearchTarget::Address(addr) => {
                    // For address search, find prefixes that contain this address
                    node_ref.prefix.contains(addr)
                }
                SearchTarget::Prefix(search_prefix) => {
                    // For prefix search, find prefixes that contain the entire search prefix
                    node_ref.prefix.contains_prefix(search_prefix)
                }
            };
            
            if matches && node_ref.prefix.prefix_len <= worst_len {
                worst_match = Some(key);
                worst_len = node_ref.prefix.prefix_len;
            }
        }
        
        Ok(worst_match.and_then(|key| self.py_nodes.get(key).map(|py_node| py_node.clone_ref(py).into())))
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_covered(
        &self,
        py: Python,
        network: Option<String>,
        masklen: Option<i32>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<PyObject>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_network_masklen(&net, mask as u8)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_packed(&packed_addr, mask as u8)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let mut covered = Vec::new();
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            if prefix.contains_prefix(&node_ref.prefix) {
                covered.push(py_node.clone_ref(py).into());
            }
        }
        
        // Sort by prefix length (longest first)
        covered.sort_by(|a: &PyObject, b: &PyObject| {
            let a_node = a.extract::<PyRef<RadixNode>>(py).unwrap();
            let b_node = b.extract::<PyRef<RadixNode>>(py).unwrap();
            b_node.prefix.prefix_len.cmp(&a_node.prefix.prefix_len)
        });
        
        Ok(covered)
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_covering(
        &self,
        py: Python,
        network: Option<String>,
        masklen: Option<i32>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<PyObject>> {
        let prefix = match (network, masklen, packed) {
            (Some(net), None, None) => {
                Prefix::from_str(&net)?
            }
            (Some(net), Some(mask), None) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_network_masklen(&net, mask as u8)?
            }
            (None, Some(mask), Some(packed_addr)) => {
                // Validate range first
                if mask < 0 || mask > 255 {
                    return Err(PyValueError::new_err(
                        format!("Invalid prefix length: {}", mask)
                    ));
                }
                Prefix::from_packed(&packed_addr, mask as u8)?
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Must specify either network (with optional masklen) or packed address with masklen"
                ));
            }
        };
        
        let mut covering = Vec::new();
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            if node_ref.prefix.contains_prefix(&prefix) {
                covering.push(py_node.clone_ref(py).into());
            }
        }
        
        // Sort by prefix length (longest first - most specific first)
        covering.sort_by(|a: &PyObject, b: &PyObject| {
            let a_node = a.extract::<PyRef<RadixNode>>(py).unwrap();
            let b_node = b.extract::<PyRef<RadixNode>>(py).unwrap();
            b_node.prefix.prefix_len.cmp(&a_node.prefix.prefix_len)
        });
        
        Ok(covering)
    }
    
    fn nodes(&self, py: Python) -> Vec<PyObject> {
        self.py_nodes.values().map(|py_node| py_node.clone_ref(py).into()).collect()
    }
    
    fn prefixes(&self) -> Vec<String> {
        self.py_nodes.keys().cloned().collect()
    }
    
    fn __iter__(&self, py: Python) -> PyResult<RadixIterator> {
        // Sort by prefix to ensure consistent ordering
        let mut sorted_entries: Vec<_> = self.py_nodes.iter().collect();
        sorted_entries.sort_by_key(|(prefix, _)| prefix.as_str());
        
        let nodes: Vec<PyObject> = sorted_entries.into_iter()
            .map(|(_, py_node)| py_node.clone_ref(py).into())
            .collect();
        Ok(RadixIterator { nodes, index: 0 })
    }
    
    fn __len__(&self) -> usize {
        self.py_nodes.len()
    }
}

#[pyclass]
pub struct RadixIterator {
    nodes: Vec<PyObject>,
    index: usize,
}

#[pymethods]
impl RadixIterator {
    fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
        slf
    }
    
    fn __next__(mut slf: PyRefMut<Self>, py: Python) -> PyResult<Option<PyObject>> {
        if slf.index < slf.nodes.len() {
            let node = slf.nodes[slf.index].clone_ref(py);
            slf.index += 1;
            Ok(Some(node))
        } else {
            Ok(None)
        }
    }
}