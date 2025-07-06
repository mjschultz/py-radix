use pyo3::prelude::*;

mod radix;
mod node;
mod prefix;

use radix::RadixTree;
use node::RadixNode;

#[pymodule]
fn _radix_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RadixTree>()?;
    m.add_class::<RadixNode>()?;
    Ok(())
}