use pyo3::prelude::*;
use pyo3::types::PyDict;
use crate::prefix::Prefix;

#[pyclass]
pub struct RadixNode {
    pub(crate) prefix: Prefix,
    pub(crate) data: Py<PyDict>,
    pub(crate) parent: Option<Py<RadixNode>>,
}

#[pymethods]
impl RadixNode {
    #[new]
    fn new(py: Python, network: String, masklen: Option<u8>) -> PyResult<Self> {
        let prefix = match masklen {
            Some(mask) => Prefix::from_network_masklen(&network, mask)?,
            None => Prefix::from_str(&network)?,
        };
        
        Ok(RadixNode {
            prefix,
            data: PyDict::new(py).into(),
            parent: None,
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
        Ok(self.data.clone_ref(py).into())
    }
    
    #[setter]
    fn set_data(&mut self, py: Python, value: PyObject) -> PyResult<()> {
        let dict = value.downcast_bound::<PyDict>(py)?;
        self.data = dict.clone().into();
        Ok(())
    }
    
    fn __str__(&self) -> String {
        format!("RadixNode({})", self.prefix.prefix())
    }
    
    fn __repr__(&self) -> String {
        format!("RadixNode({})", self.prefix.prefix())
    }
    
    #[getter]
    fn parent(&self, py: Python) -> PyResult<PyObject> {
        match &self.parent {
            Some(parent) => Ok(parent.clone_ref(py).into()),
            None => Ok(py.None()),
        }
    }
}

impl RadixNode {
    pub fn new_with_prefix(py: Python, prefix: Prefix) -> Self {
        RadixNode {
            prefix,
            data: PyDict::new(py).into(),
            parent: None,
        }
    }
    
    pub fn set_data_item(&self, py: Python, key: String, value: PyObject) -> PyResult<()> {
        self.data.bind(py).set_item(key, value)
    }
    
    pub fn get_data_item(&self, py: Python, key: &str) -> PyResult<Option<PyObject>> {
        match self.data.bind(py).get_item(key) {
            Ok(Some(value)) => Ok(Some(value.into())),
            Ok(None) => Ok(None),
            Err(e) => Err(e),
        }
    }
    
    pub fn clone_for_return(&self, py: Python) -> Self {
        RadixNode {
            prefix: self.prefix.clone(),
            data: self.data.clone_ref(py),
            parent: None,
        }
    }
    
}