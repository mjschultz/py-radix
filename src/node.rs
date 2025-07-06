use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;
use crate::prefix::Prefix;

#[pyclass]
pub struct RadixNode {
    pub(crate) prefix: Prefix,
    pub(crate) data: HashMap<String, PyObject>,
}

#[pymethods]
impl RadixNode {
    #[new]
    fn new(_py: Python, network: String, masklen: Option<u8>) -> PyResult<Self> {
        let prefix = match masklen {
            Some(mask) => Prefix::from_network_masklen(&network, mask)?,
            None => Prefix::from_str(&network)?,
        };
        
        Ok(RadixNode {
            prefix,
            data: HashMap::new(),
        })
    }
    
    #[getter]
    fn network(&self) -> String {
        self.prefix.network()
    }
    
    #[getter]
    fn prefix(&self) -> String {
        self.prefix.prefix()
    }
    
    #[getter]
    fn prefixlen(&self) -> u8 {
        self.prefix.prefixlen()
    }
    
    #[getter]
    fn family(&self) -> i32 {
        self.prefix.family()
    }
    
    #[getter]
    fn packed(&self) -> Vec<u8> {
        self.prefix.packed()
    }
    
    #[getter]
    fn data(&self, py: Python) -> PyResult<PyObject> {
        let dict = PyDict::new(py);
        for (key, value) in &self.data {
            dict.set_item(key, value)?;
        }
        Ok(dict.into())
    }
    
    #[setter]
    fn set_data(&mut self, py: Python, value: PyObject) -> PyResult<()> {
        let dict = value.downcast_bound::<PyDict>(py)?;
        self.data.clear();
        for (key, val) in dict.iter() {
            let key_str = key.extract::<String>()?;
            self.data.insert(key_str, val.into());
        }
        Ok(())
    }
    
    fn __str__(&self) -> String {
        format!("RadixNode({})", self.prefix.prefix())
    }
    
    fn __repr__(&self) -> String {
        format!("RadixNode({})", self.prefix.prefix())
    }
}

impl RadixNode {
    pub fn new_with_prefix(prefix: Prefix) -> Self {
        RadixNode {
            prefix,
            data: HashMap::new(),
        }
    }
    
    pub fn set_data_item(&mut self, key: String, value: PyObject) {
        self.data.insert(key, value);
    }
    
    pub fn get_data_item(&self, key: &str) -> Option<&PyObject> {
        self.data.get(key)
    }
    
    pub fn clone_for_return(&self) -> Self {
        RadixNode {
            prefix: self.prefix.clone(),
            data: HashMap::new(), // We'll handle data cloning differently
        }
    }
}