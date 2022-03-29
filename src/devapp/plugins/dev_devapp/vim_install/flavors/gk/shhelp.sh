#!/usr/bin/env bash
vi="/home/gk/inst/nvim.appimage"

main() {
	$vi "$HOME/.config/nvim/utils/mappings.txt"
}

main "$@"
