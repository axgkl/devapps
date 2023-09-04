#!/usr/bin/env bash
# wget <url> | bash  OR source (not run)

set -a
node="%(node)s"
lc_hubs="%(lc_hubs)s"
app_libs="%(app_libs)s"
d_project="%(d_project)s"
pip_to_install="%(pip_to_install)s"
PATH="$HOME/.local/bin:$PATH"
copied_dirs="%(copied_dirs)s"
inst_ops="%(inst_ops)s"
inst_pds="%(inst_pds)s"
set +a
have_hub=false

# anything we copied here before is exe:
chmod +x "$HOME/.local/bin/"*

function ops_inst {
    local svc="$1"
    shift
    ops project install --resource_match="$svc" --init_create_all_units --force -lf 3 "$@"
}
#inst_url="$inst_protocol://$inst_host"
function d_artifacts { echo "$MAMBA_ROOT_PREFIX/artifacts/hubpkgs"; }

function sh {
    echo -e "🟩 $*k"
    eval "$*"
}
function die {
    echo -e "🟥 $*"
    exit 1
}
function activate_home_base {
    . "$HOME/.bashrc"
    #. micromamba/etc/profile.d/micromamba.sh
    micromamba activate base
}
function check_bootstrapped {
    micromamba activate 2>/dev/null && return 0 # e.g. mamba docker container
    test -e "$HOME/micromamba" && activate_home_base && echo "Mamba activated: $MAMBA_ROOT_PREFIX" && return 0
    return 1
}
function install_bzip {
    test "$UID" == "0" || {
        echo "Please install bzip2 as root"
        exit 1
    }
    type apt-get && {
        apt-get update
        apt-get install bzip2 && return 0
    }
    type yum && { yum install -y bzip2 && return; }
    exit 1
}
function bootstrap {
    type bzip2 || install_bzip
    builtin cd
    curl micro.mamba.pm/install.sh | bash
    activate_home_base
}
function ensure_channel {
    echo -e 'channels:\n  - conda-forge\n' >"$HOME/.condarc"
}
function ensure_base_tools {
    local t r="$MAMBA_ROOT_PREFIX"
    test -z "$r" && {
        echo "No mamba"
        exit 1
    }
    local pkgs=""
    micromamba list >pkgs
    tools="python $app_libs"
    for t in git curl gcc jq fzf; do
        echo "Have $t?"
        type "$t" || tools="$tools $t"
    done
    for t in $tools; do grep "$t" <pkgs || pkgs="$t $pkgs"; done
    test -n "$pkgs" || return 0
    test -z "$pkgs" || {
        echo "Installing $pkgs..."
        sh micromamba install --quiet -y "$pkgs" && return 0
    }
    die "failure pkgs install $pkgs"
}

function ensure_lc_app_pkg {
    #local pips="$(pip list)"
    set -x
    d="$HOME/.cache/priv_pips"
    pip install --find-links="$d" "$pip_to_install" && return 0
    die "pip failed. libs missing?"
}

function ensure_proj_dir {
    mkdir -p "$d_project"
    cd "$d_project" || true
    git init || true
    mkdir -p conf
    cp "$HOME/system.py" conf/system.py
}
function ensure_proj_files {
    test -e "$HOME/proj_files.tgz" || return
    mv "$HOME/proj_files.tgz" .
    tar xfvz proj_files.tgz
    unlink proj_files.tgz
}
function ensure_environ_file_written_and_sourced {
    cat >environ <<EOF
# vi: ft=sh
micromamba activate
set -a
node="$node"
%(environ_file)s
test -f environ.personal && source environ.personal
PS1='\[\033[1;45m\]$node\[\033[0m\] \u \W\$ '
set +a
EOF
    . ./environ

}
function ensure_bash_helpers {
    local b="$HOME/.bashrc"
    local sep="$d_project-helpers"
    grep "$sep" <"$b" && {
        grep -B 10000 "beg $sep" <"$b" | head -n -1 >"$b.s"
        grep -A 10000 "end $sep" <"$b" | tail -n +2 >>"$b.s"
        mv "$b.s" "$b"
    }
    echo -e '
# > > > > > > beg '$sep'
function cd { builtin cd "$@"; test -e ./environ && . ./environ; }
function gomod {
    local mod="${1:-os}"
    local l="$(python -c "import os, $mod;print(os.path.dirname($mod.__file__))")"
    cd "$l"
    pwd
}
function ff { find . -print | grep "$1"; }
# < < < < < < end '$sep'
    ' >>"$b"
}
function ensure_pds {
    test -n "$inst_pds" && dev pds install --nvim_config_repo "$inst_pds"
}
function ensure_copied_dirs_linked {
    for d in $copied_dirs; do
        dev repo_sym_links -r "$d" link --force -lf 3
    done
}

function ensure_ops_svcs_installed {
    cd "$d_project" || true
    inst_ops="$inst_ops slc"
    export slc_lc_hubs="$lc_hubs"
    for d in $inst_ops; do
        ops_inst "$d"
        test "$d" = "hub" && {
            worker_name=slcm worker_functions=system worker_lc_tabs=System ops_inst worker
        }
    done
}

function main {
    sh check_bootstrapped || bootstrap
    sh ensure_channel
    sh activate_home_base
    sh ensure_base_tools
    sh ensure_lc_app_pkg
    sh ensure_proj_dir
    sh ensure_proj_files
    sh ensure_environ_file_written_and_sourced
    sh ensure_bash_helpers
    sh ensure_copied_dirs_linked
    sh ensure_pds
    sh ensure_ops_svcs_installed
}

main "$@"
