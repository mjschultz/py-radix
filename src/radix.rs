use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;
use std::collections::HashMap;
use std::net::IpAddr;
use std::str::FromStr;

use crate::prefix::Prefix;
use crate::node::RadixNode;

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
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<PyObject> {
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
        
        if self.py_nodes.remove(&key).is_some() {
            Ok(())
        } else {
            Err(PyValueError::new_err("Node not found"))
        }
    }
    
    #[pyo3(signature = (network = None, masklen = None, packed = None))]
    fn search_exact(
        &self,
        py: Python,
        network: Option<String>,
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<PyObject>> {
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
        
        Ok(self.py_nodes.get(&key).map(|py_node| py_node.clone_ref(py).into()))
    }
    
    #[pyo3(signature = (network = None, packed = None))]
    fn search_best(
        &self,
        py: Python,
        network: Option<String>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Option<PyObject>> {
        let addr = match (network, packed) {
            (Some(net), None) => {
                // Try to parse as CIDR first, then as IP address
                if net.contains('/') {
                    let prefix = Prefix::from_str(&net)?;
                    prefix.network_addr()
                } else {
                    IpAddr::from_str(&net)
                        .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?
                }
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
        
        let mut best_match: Option<&str> = None;
        let mut best_len = 0;
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            if node_ref.prefix.contains(&addr) && node_ref.prefix.prefix_len >= best_len {
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
        let addr = match (network, packed) {
            (Some(net), None) => {
                // Try to parse as CIDR first, then as IP address
                if net.contains('/') {
                    let prefix = Prefix::from_str(&net)?;
                    prefix.network_addr()
                } else {
                    IpAddr::from_str(&net)
                        .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?
                }
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
        
        let mut worst_match: Option<&str> = None;
        let mut worst_len = 255;
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            if node_ref.prefix.contains(&addr) && node_ref.prefix.prefix_len <= worst_len {
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
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<PyObject>> {
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
        masklen: Option<u8>,
        packed: Option<Vec<u8>>,
    ) -> PyResult<Vec<PyObject>> {
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
        
        for (key, py_node) in &self.py_nodes {
            let node_ref = py_node.bind(py).borrow();
            if node_ref.prefix.contains_prefix(&prefix) {
                covering.push(py_node.clone_ref(py).into());
            }
        }
        
        // Sort by prefix length (shortest first)
        covering.sort_by(|a: &PyObject, b: &PyObject| {
            let a_node = a.extract::<PyRef<RadixNode>>(py).unwrap();
            let b_node = b.extract::<PyRef<RadixNode>>(py).unwrap();
            a_node.prefix.prefix_len.cmp(&b_node.prefix.prefix_len)
        });
        
        Ok(covering)
    }
    
    fn nodes(&self, py: Python) -> Vec<PyObject> {
        self.py_nodes.values().map(|py_node| py_node.clone_ref(py).into()).collect()
    }
    
    fn prefixes(&self) -> Vec<String> {
        self.py_nodes.keys().cloned().collect()
    }
    
    // TODO: Fix iterator implementation
    // fn __iter__(slf: PyRef<Self>, py: Python) -> PyResult<RadixIterator> {
    //     let nodes: Vec<String> = slf.nodes.keys().cloned().collect();
    //     Ok(RadixIterator { tree: slf.into(), nodes, index: 0 })
    // }
    
    fn __len__(&self) -> usize {
        self.py_nodes.len()
    }
}

// TODO: Fix iterator implementation
// #[pyclass]
// pub struct RadixIterator {
//     tree: Py<RadixTree>,
//     nodes: Vec<String>,
//     index: usize,
// }

// #[pymethods]
// impl RadixIterator {
//     fn __iter__(slf: PyRef<Self>) -> PyRef<Self> {
//         slf
//     }
    
//     fn __next__(mut slf: PyRefMut<Self>, py: Python) -> PyResult<Option<RadixNode>> {
//         if slf.index < slf.nodes.len() {
//             let key = &slf.nodes[slf.index];
//             slf.index += 1;
//             let tree = slf.tree.bind(py);
//             Ok(tree.nodes.get(key).map(|node| node.clone_for_return(py)))
//         } else {
//             Ok(None)
//         }
//     }
// }