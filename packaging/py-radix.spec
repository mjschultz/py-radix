Name: py-radix
Summary: Radix tree data structure for Python
Version: 0.5
Release: 1
Source0: http://www2.mindrot.org/files/py-radix/py-radix-%{version}.tar.gz
License: BSD
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-buildroot
Requires: %{__python}
BuildRequires: python-devel, gcc
Url: http://www.mindrot.org/py-radix.html

%description
py-radix is an implementation of a radix tree for Python, which 
supports storage and lookups of IPv4 and IPv6 networks. 

The radix tree (a.k.a Patricia tree) is the data structure most 
commonly used for routing table lookups. It efficiently stores 
network prefixes of varying lengths and allows fast lookups of 
containing networks. py-radix's implementation is built solely 
for networks (the data structure itself is more general). 

%prep
%setup

%build
%{__python} setup.py build

%install
%{__python} setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
sed -e 's|/[^/]*$||' INSTALLED_FILES | grep "site-packages/" | \
    sort | uniq | awk '{ print "%attr(755,root,root) %dir " $1}' > INSTALLED_DIRS
cat INSTALLED_FILES INSTALLED_DIRS > INSTALLED_OBJECTS

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_OBJECTS
%defattr(-,root,root)
%doc LICENSE README TODO ChangeLog

%changelog
* Wed Jun 28 2006 Damien Miller <djm@mindrot.org>
- Build RPM
