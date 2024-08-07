#!/bin/bash

## CHIP'S OCEAN GAME (COG) SAVE BACKUP SCRIPT
##
## Automatically tars and copies COG's save directory to alternate locations
## for the sake of redundancy. Meant to be called by the main COG script at 
## regular intervals, but can also be called manually if you want. 


# CONSTANTS
COGROOT="/enter/a/path"       # Location where COG's files are stored
TMPDIR="/tmp/enter/a/path"    # Temporary working directory
BKDIR="/backups/enter/a/path" # The main backup directory
RETAIN=14                     # The number of backups to retain

# Secondary backup directory for redundancy
OFFSITE="user@somehost:/enter/a/path"


# MAIN
bkname="$(date +%Y%m%d%H%M)_COG_BACKUP.tgz"
if [ ! -d "$TMPDIR" ]; then
    mkdir $TMPDIR
fi

pushd $TMPDIR
rm -rf $TMPDIR/*
rsync -r $COGROOT/save $TMPDIR
tar -czf $bkname -C $TMPDIR .
rsync -r $TMPDIR/$bkname $BKDIR/
rsync -r $TMPDIR/$bkname $OFFSITE/

if (($(ls $BKDIR | wc -w) > $RETAIN)); then
    fileList=$(ls $BKDIR)
    numFiles=$(ls $BKDIR | wc -w)
    numDelete=$(($numFiles - $RETAIN))
    deleteList=$(ls $BKDIR | head -n $numDelete)
    for file in $deleteList; do
        rm -f $BKDIR/$file
    done
fi
rm -rf $TMPDIR/*
popd
