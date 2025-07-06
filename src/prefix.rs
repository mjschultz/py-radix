use std::net::{IpAddr, Ipv4Addr, Ipv6Addr};
use std::str::FromStr;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Prefix {
    pub addr: IpAddr,
    pub prefix_len: u8,
}

impl Prefix {
    pub fn new(addr: IpAddr, prefix_len: u8) -> PyResult<Self> {
        let max_len = match addr {
            IpAddr::V4(_) => 32,
            IpAddr::V6(_) => 128,
        };
        
        if prefix_len > max_len {
            return Err(PyValueError::new_err(format!(
                "Prefix length {} is too large for {:?}",
                prefix_len, addr
            )));
        }
        
        Ok(Prefix { addr, prefix_len })
    }
    
    pub fn from_str(s: &str) -> PyResult<Self> {
        if let Some((addr_str, prefix_str)) = s.split_once('/') {
            let addr = IpAddr::from_str(addr_str)
                .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?;
            let prefix_len = prefix_str.parse::<u8>()
                .map_err(|e| PyValueError::new_err(format!("Invalid prefix length: {}", e)))?;
            Self::new(addr, prefix_len)
        } else {
            // No slash found - treat as host route
            let addr = IpAddr::from_str(s)
                .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?;
            let prefix_len = match addr {
                IpAddr::V4(_) => 32,
                IpAddr::V6(_) => 128,
            };
            Self::new(addr, prefix_len)
        }
    }
    
    pub fn from_network_masklen(network: &str, masklen: u8) -> PyResult<Self> {
        let addr = IpAddr::from_str(network)
            .map_err(|e| PyValueError::new_err(format!("Invalid IP address: {}", e)))?;
        Self::new(addr, masklen)
    }
    
    pub fn from_packed(packed: &[u8], masklen: u8) -> PyResult<Self> {
        let addr = match packed.len() {
            4 => {
                let bytes: [u8; 4] = packed.try_into()
                    .map_err(|_| PyValueError::new_err("Invalid IPv4 packed address"))?;
                IpAddr::V4(Ipv4Addr::from(bytes))
            }
            16 => {
                let bytes: [u8; 16] = packed.try_into()
                    .map_err(|_| PyValueError::new_err("Invalid IPv6 packed address"))?;
                IpAddr::V6(Ipv6Addr::from(bytes))
            }
            _ => return Err(PyValueError::new_err("Packed address must be 4 or 16 bytes")),
        };
        Self::new(addr, masklen)
    }
    
    pub fn network(&self) -> String {
        self.addr.to_string()
    }
    
    pub fn prefix(&self) -> String {
        format!("{}/{}", self.addr, self.prefix_len)
    }
    
    pub fn prefixlen(&self) -> u8 {
        self.prefix_len
    }
    
    pub fn family(&self) -> i32 {
        match self.addr {
            IpAddr::V4(_) => 2,  // AF_INET
            IpAddr::V6(_) => 10, // AF_INET6
        }
    }
    
    pub fn packed(&self) -> Vec<u8> {
        match self.addr {
            IpAddr::V4(v4) => v4.octets().to_vec(),
            IpAddr::V6(v6) => v6.octets().to_vec(),
        }
    }
    
    /// Check if this prefix contains the given address
    pub fn contains(&self, addr: &IpAddr) -> bool {
        match (self.addr, addr) {
            (IpAddr::V4(self_v4), IpAddr::V4(addr_v4)) => {
                self.contains_v4(self_v4, *addr_v4)
            }
            (IpAddr::V6(self_v6), IpAddr::V6(addr_v6)) => {
                self.contains_v6(self_v6, *addr_v6)
            }
            _ => false, // Different IP versions
        }
    }
    
    /// Check if this prefix contains the given prefix
    pub fn contains_prefix(&self, other: &Prefix) -> bool {
        if self.prefix_len > other.prefix_len {
            return false;
        }
        self.contains(&other.addr)
    }
    
    fn contains_v4(&self, self_addr: Ipv4Addr, addr: Ipv4Addr) -> bool {
        if self.prefix_len == 0 {
            return true;
        }
        
        let self_bits = u32::from(self_addr);
        let addr_bits = u32::from(addr);
        let mask = (!0u32) << (32 - self.prefix_len);
        
        (self_bits & mask) == (addr_bits & mask)
    }
    
    fn contains_v6(&self, self_addr: Ipv6Addr, addr: Ipv6Addr) -> bool {
        if self.prefix_len == 0 {
            return true;
        }
        
        let self_bits = u128::from(self_addr);
        let addr_bits = u128::from(addr);
        let mask = (!0u128) << (128 - self.prefix_len);
        
        (self_bits & mask) == (addr_bits & mask)
    }
    
    /// Get the network address with host bits cleared
    pub fn network_addr(&self) -> IpAddr {
        match self.addr {
            IpAddr::V4(v4) => {
                if self.prefix_len == 0 {
                    IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0))
                } else {
                    let bits = u32::from(v4);
                    let mask = (!0u32) << (32 - self.prefix_len);
                    IpAddr::V4(Ipv4Addr::from(bits & mask))
                }
            }
            IpAddr::V6(v6) => {
                if self.prefix_len == 0 {
                    IpAddr::V6(Ipv6Addr::new(0, 0, 0, 0, 0, 0, 0, 0))
                } else {
                    let bits = u128::from(v6);
                    let mask = (!0u128) << (128 - self.prefix_len);
                    IpAddr::V6(Ipv6Addr::from(bits & mask))
                }
            }
        }
    }
}