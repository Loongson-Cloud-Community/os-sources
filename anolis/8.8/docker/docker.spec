%define anolis_release 1
%global debug_package %{nil}

%global _gitcommit_engine f756502
%global _gitcommit_cli aa7e414
%global _source_engine moby-%{version}
%global _source_client cli-%{version}
%global _source_docker_init tini-0.19.0
%global _source_docker_proxy libnetwork-339b972b

Name: 	  docker
Version:  20.10.16
Release:  %{anolis_release}%{?dist}
Summary:  The open-source application container engine
License:  ASL 2.0
URL:	  https://www.docker.com
# https://github.com/docker/cli/archive/refs/tags/v20.10.16.tar.gz
Source0:  cli-%{version}.tar.gz
# https://github.com/moby/moby/archive/refs/tags/v20.10.16.tar.gz
Source1:  moby-%{version}.tar.gz
# https://github.com/krallin/tini/archive/refs/tags/v0.19.0.tar.gz
Source2:  tini-0.19.0.tar.gz
# https://github.com/moby/libnetwork.git@commit 339b972b464ee3d401b5788b2af9e31d09d6b7da
# this commit is specified in vendor.conf of {_source_engine}
Source3:  libnetwork-339b972b.tar.gz
Source4:  docker.service
Source5:  docker.socket

Requires: %{name}-engine = %{version}-%{release}
Requires: %{name}-client = %{version}-%{release}

# conflicting packages
Conflicts: docker-ce
Conflicts: docker-io
Conflicts: docker-engine-cs
Conflicts: docker-ee

%description
Docker is a product for you to build, ship and run any application as a
lightweight container.

Docker containers are both hardware-agnostic and platform-agnostic. This means
they can run anywhere, from your laptop to the largest cloud compute instance
and everything in between - and they don't require you to use a particular
language, framework or packaging system. That makes them great building blocks
for deploying and scaling web apps, databases, and backend services without
depending on a particular stack or provider.

%package engine
Summary: Docker daemon binary and related utilities

Requires: /usr/sbin/groupadd
Requires: docker-client
Requires: container-selinux >= 2:2.74
Requires: libseccomp >= 2.3
Requires: systemd
Requires: iptables
Requires: libcgroup
Requires: containerd >= 1.4.1
Requires: tar
Requires: xz

BuildRequires: bash
BuildRequires: ca-certificates
BuildRequires: cmake
BuildRequires: device-mapper-devel
BuildRequires: gcc
BuildRequires: git
BuildRequires: glibc-static
BuildRequires: libarchive
BuildRequires: libseccomp-devel
BuildRequires: libselinux-devel
BuildRequires: libtool
BuildRequires: libtool-ltdl-devel
BuildRequires: make
BuildRequires: pkgconfig
BuildRequires: pkgconfig(systemd)
BuildRequires: selinux-policy-devel
BuildRequires: systemd-devel
BuildRequires: tar
BuildRequires: which
BuildRequires: golang

%description engine
Docker daemon binary and related utilities

%package client
Summary: Docker client binary and related utilities

Requires:      /bin/sh
BuildRequires: golang
BuildRequires: libtool-ltdl-devel

%description client
Docker client binary and related utilities

%prep
%setup -q -n %{_source_client}
%setup -q -T -n %{_source_engine} -b 1
%setup -q -T -n %{_source_docker_init} -b 2
%setup -q -T -n %{_source_docker_proxy} -b 3

%build
export GO111MODULE=off
# build docker daemon
export DOCKER_GITCOMMIT=%{_gitcommit_engine}
export DOCKER_BUILDTAGS="exclude_graphdriver_btrfs"

pushd %{_builddir}/%{_source_engine}
AUTO_GOPATH=1 VERSION=%{version} PRODUCT=docker hack/make.sh dynbinary
popd

# build docker-tini
pushd %{_builddir}/%{_source_docker_init}
cmake .
make tini-static
popd

# build docker-proxy
pushd %{_builddir}/%{_source_docker_proxy}
mkdir -p .gopath/src/github.com/docker/libnetwork
export GOPATH=`pwd`/.gopath
rm -rf .gopath/src/github.com/docker/libnetwork
ln -s %{_builddir}/%{_source_docker_proxy} .gopath/src/github.com/docker/libnetwork
pushd .gopath/src/github.com/docker/libnetwork
go build -buildmode=pie -ldflags=-linkmode=external -o docker-proxy github.com/docker/libnetwork/cmd/proxy
popd
popd

# build cli
pushd %{_builddir}/%{_source_client}
mkdir -p .gopath/src/github.com/docker/cli
export GOPATH=`pwd`/.gopath
rm -rf .gopath/src/github.com/docker/cli
ln -s %{_builddir}/%{_source_client} .gopath/src/github.com/docker/cli
pushd .gopath/src/github.com/docker/cli
DISABLE_WARN_OUTSIDE_CONTAINER=1 make VERSION=%{version} GITCOMMIT=%{_gitcommit_cli} dynbinary
popd
popd

%check
# check for daemon
ver="$(%{_builddir}/%{_source_engine}/bundles/dynbinary-daemon/dockerd --version)"; \
    test "$ver" = "Docker version %{version}, build %{_gitcommit_engine}" && echo "PASS: daemon version OK" || (echo "FAIL: daemon version ($ver) did not match" && exit 1)
# check for client
ver="$(%{_builddir}/%{_source_client}/build/docker --version)"; \
    test "$ver" = "Docker version %{version}, build %{_gitcommit_cli}" && echo "PASS: cli version OK" || (echo "FAIL: cli version ($ver) did not match" && exit 1)


%install
# install daemon binary
install -D -p -m 0755 $(readlink -f %{_builddir}/%{_source_engine}/bundles/dynbinary-daemon/dockerd) %{buildroot}%{_bindir}/dockerd

# install proxy
install -D -p -m 0755 %{_builddir}/%{_source_docker_proxy}/docker-proxy %{buildroot}%{_bindir}/docker-proxy

# install tini
install -D -p -m 755 %{_builddir}/%{_source_docker_init}/tini-static %{buildroot}%{_bindir}/docker-init

# install systemd scripts
install -D -m 0644 %{SOURCE4} %{buildroot}%{_unitdir}/docker.service
install -D -m 0644 %{SOURCE5} %{buildroot}%{_unitdir}/docker.socket

# install docker client
install -p -m 0755 $(readlink -f %{_builddir}/%{_source_client}/build/docker) %{buildroot}%{_bindir}/docker

# add bash, zsh, and fish completions
install -d %{buildroot}%{_datadir}/bash-completion/completions
install -d %{buildroot}%{_datadir}/zsh/vendor-completions
install -d %{buildroot}%{_datadir}/fish/vendor_completions.d
install -p -m 644 %{_builddir}/%{_source_client}/contrib/completion/bash/docker %{buildroot}%{_datadir}/bash-completion/completions/docker
install -p -m 644 %{_builddir}/%{_source_client}/contrib/completion/zsh/_docker %{buildroot}%{_datadir}/zsh/vendor-completions/_docker
install -p -m 644 %{_builddir}/%{_source_client}/contrib/completion/fish/docker.fish %{buildroot}%{_datadir}/fish/vendor_completions.d/docker.fish

# add docs
install -d %{buildroot}%{_pkgdocdir}
install -p -m 644 %{_builddir}/%{_source_client}/{LICENSE,MAINTAINERS,NOTICE,README.md} %{buildroot}%{_pkgdocdir}

%files
# empty as it depends on engine and client

%files engine
%{_bindir}/dockerd
%{_bindir}/docker-proxy
%{_bindir}/docker-init
%{_unitdir}/docker.service
%{_unitdir}/docker.socket

%files client
%{_bindir}/docker
%{_datadir}/bash-completion/completions/docker
%{_datadir}/zsh/vendor-completions/_docker
%{_datadir}/fish/vendor_completions.d/docker.fish
%doc %{_pkgdocdir}

%post
%systemd_post docker.service
if ! getent group docker > /dev/null; then
    groupadd --system docker
fi

%preun
%systemd_preun docker.service

%postun
%systemd_postun_with_restart docker.service

%changelog
* Mon May 23 2022 Yuanhong Peng <yummypeng@linux.alibaba.com> -20.10.16-1
- Init repo from docker-ce-packaging upstream
