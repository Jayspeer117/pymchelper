#!/usr/bin/env bash

# generate single-case
cd single
shieldhit ../ -n 1000


# generate many-case
cd ../many/
shieldhit ../ -n 200 -N 1
shieldhit ../ -n 200 -N 2
shieldhit ../ -n 200 -N 3
shieldhit ../ -n 200 -N 4
shieldhit ../ -n 200 -N 5
cd ../