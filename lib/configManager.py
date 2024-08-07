#!/bin/python3

## CONFIGURATION MANAGER
##
## Part of Chip's Python Utilities. A series of easy-to-use functions for
## managing configuration files written in my own JSON-esque file format
## (essentially just regular JSON but with support for comments).


## IMPORTS AND CONSTANTS
import json
import io


## FUNCTIONS
def loadConfig(file):
    # Loads and parses a configuration file. Returns the configuration values
    # as a dictionary.
    configBuffer = io.StringIO("")
    with open(file, 'r') as f:
        for line in f:           # This loop is to strip comments out of the
            line = line.strip()  # config file, thus leaving pure JSON for
            if not line == "":   # json.loads()
                if not line[0] == "#":
                    configBuffer.write(line)
    config = json.loads(configBuffer.getvalue())
    configBuffer.close()
    return config

def writeConfig(config, file):
    # Takes a dictionary of values ('config') and writes it to the specified 
    # file ('file'). 
    with open(file, 'w') as f:
        json.dump(config, f, indent=4)
    # Future versions of writeConfig will include logic to attempt to preserve
    # comments in files that have them.


## UNIT TESTS
if __name__ == "__main__":

    # Attempt to load a known-good config file
    filename = "./configManager.sample"
    print("Test 1: Attempt to load known-good config file {}".format(filename))
    config = loadConfig(filename)
    if config['foo'] == 'bar' and config['bool'] == False:
        print("Test 1: Pass!\n")
    
    # Alter the above config and attempt to write it in a new config file
    newfile = "./unitTest.conf"
    print("Test 2: Try to write a new config at {}".format(newfile))
    config['bool'] = True
    config['int'] = 2
    config['newval'] = "Hello World!"
    writeConfig(config, newfile)
    print("Test 2: Pass!\n")

    # Load and validate the newly created config
    print("Test 3: Attempt to load newly-written config file {}".format(newfile))
    config = loadConfig(newfile)
    if config['bool'] and config['int'] == 2 and config['newval'] == "Hello World!":
        print("Test 3: Pass!\n")