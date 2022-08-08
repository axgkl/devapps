#!/bin/bash
# part:local: name contains control
source "%(feature:functions.sh)s"

for n in $(echo "$names"); do
    [[ $n =~ control ]] && continue
    K label nodes "$n" 'kubernetes.io/role=worker' &
    K label nodes "$n" 'node-type=worker' &
done
#K get nodes --show-labels
