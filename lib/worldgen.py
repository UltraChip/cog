#!/bin/python3

## WORLDGEN FUNCTIONS
##
## A series of functions used to drive the world generation for COG.


## IMPORTS AND CONSTANTS
import random

import lib.AIengine as ai
from lib.configManager import loadConfig

confFile = "./etc/main.conf"  # Location of config file


## FUNCTIONS
def findBounds(origin, radius):
    # Finds the bounding coordinates of a square box (upper left corner, lower 
    # right corner) centered on given origin coordinates (provided as a list 
    # [x,y]) and extending to given range. Returns list of coordinates [x1,y1, 
    # x2,y2]. All results rounded to int.
    x1 = round(origin[0]-radius)
    y1 = round(origin[1]+radius)
    x2 = round(origin[0]+radius)
    y2 = round(origin[1]-radius)
    return [x1,y1,x2,y2]

def makeGridSeed(x, y):
    # Creates a PRNG seed unique to specific grid squares. Takes in the grid
    # coordinates as input, returns a string as output.
    baseSeed = conf['hull']
    gridSeed = f"{baseSeed}:{x},{y}"
    return gridSeed

def getWeights(typeList):
    # Gets the probability weights for a given list of POI types. Takes in a
    # list of POI types as input, returns a list of weights (as ints) as output.
    weights = []
    for item in typeList:
        goString = f"weight_poi_{item}"
        weights.append(probs[goString])
    return weights

def sensorSweep(shipLoc, rng, type="visual"):
    # Primary function driving POI detection. Takes in ship's X,Y coordinates
    # as a list, range of the given sensor, and the type of sensor. Returns the
    # generated POIs as a list of lists(x,y,"U" or "L" to denote surface/sub).
    foundContacts = []
    searchBox = findBounds(shipLoc, rng)
    for y in range(searchBox[1], searchBox[3], -1):  # Step is negative because
        for x in range(searchBox[0], searchBox[2]):  # we're starting at top Y
            random.seed(f"{makeGridSeed(x,y)}{type}")# value and working down.
            roll = random.random()
            if type == "radar" or type == "visual":
                if roll <= probs['chanceSurfacePOI']:
                    foundContacts.append([x,y,"U"])
            elif type == "sonar":
                if roll <= probs['chanceSubPOI']:
                    foundContacts.append([x,y,"L"])
    return foundContacts

def getResources(type, gSeed):
    # Determines the resources available to a POI at a given set of coordinates.
    # Takes as input the POI type and the gridSeed. Returns a list of resources.
    resources = []
    i = 0
    random.seed(gSeed)
    typeString = f"resource_{type}"
    
    if type in ["offshore platform", "ship", "wreck", "coral", "deposit"]:
        return types[typeString]
    numResource = 2
    while i < numResource:
        c = random.choice(types[typeString])
        if c not in resources:
            resources.append(c)
            i += 1
    return resources

def computeWeird(contact):
    # Computes the level of "weirdness" for a given coordinate on a scale of
    # 1 to 10. Generally, the more extreme your latitude the more weird things
    # get. Takes a contact as input and returns an int in range 1-10 as output.
    random.seed(conf['hull'])
    lat = contact[1]
    nudge = random.uniform(-1, 1)
    baseWeird = (lat/1000)*10
    nudgeWeird = baseWeird+nudge
    if nudgeWeird < 1:
        weird = 1
    elif nudgeWeird > 10:
        weird = 10
    else:
        weird = round(nudgeWeird)
    return weird

def getPOI(contact):
    # Get the properties of a found POI - takes in a contact (tuple containing
    # X coord, Y coord, and Surface/Submerged identifier), returns a dictionary
    # containing the POI properties.
    gSeed = makeGridSeed(contact[0], contact[1])
    pProps = {}

    random.seed(gSeed)
    pTypes = types['surface_pois'] if contact[2] == "U" else types['submerged_pois']
    pWeights = getWeights(pTypes)
    pType = random.choices(pTypes, weights=pWeights)[0]  # Index of 0 because
                                                         # random.choices returns
    pProps['loc']       = (contact[0], contact[1])       # as a single-element
    pProps['type']      = pType                          # list.
    pProps['name']      = ai.getName(pType)
    pProps['adj']       = random.choice(types['adjectives'])
    pProps['weirdness'] = computeWeird(contact)
    pProps['resources'] = getResources(pType, gSeed)

    return pProps


## INITIALIZATION
conf  = loadConfig(confFile)
probs = loadConfig(f"./{conf['probfile']}")
types = loadConfig(f"./{conf['typefile']}")
random.seed(conf["hull"])


## UNIT TESTS
if __name__ == "__main__":
    conf['hull'] = "TEST"  # Override hull number (a.k.a. master PRNG seed) to
                           # a known value

    # Testing findBounds()
    print("TEST: findBounds()")
    print(f"    findBounds([0,0], 20)    : Expect [-20,20,20,-20] : Got {findBounds([0,0], 20)}")
    print(f"    findBounds([100,50], 50) : Expect [50,100,150,0]  : Got {findBounds([100,50], 50)}")
    print(f"    findBounds([3,3], 0)     : Expect [3,3,3,3]       : Got {findBounds([3,3], 0)}")
    print("")

    # Testing makeGridSeed()
    print("TEST: makeGridSeed()")
    print(f"    makeGridSeed(0,0) : Expect 'TEST:0,0' : Got '{makeGridSeed(0,0)}'")
    print(f"    makeGridSeed(8,8) : Expect 'TEST:8,8' : Got '{makeGridSeed(8,8)}'")
    print("")

    # Testing sensorSweep()
    print("TEST: sensorSweep()")
    numSurface = len(sensorSweep([0,0], 50, "radar"))
    numSub     = len(sensorSweep([0,0], 40, "sonar"))
    print(f"    Surface Contacts   : Expected 4 : Got {numSurface}")
    print(f"    Submerged Contacts : Expected 2 : Got {numSub}")
    print("")

    # Testing getWeights()
    typeList = [ "island", "wreck", "coral" ]
    i = 0
    print("TEST: getWeights()")
    weights = getWeights(typeList)
    for c in range(len(typeList)):
        print(f"    {typeList[i]} = {weights[i]}")
        i += 1
    print("")

    # Testing getResources()
    print("TEST: getResources()")
    print("    Resources for island:")
    r = getResources('island', 'gSeed')
    for item in r:
        print(f"        {item}")
    print("    Resources for platform:")
    r = getResources('offshore platform', 'gSeed')
    for item in r:
        print(f"        {item}")
    print("")

    # Testing computeWeird()
    print("TEST: computeWeird()")
    print(f"    0,0      : {computeWeird((0,0,'U'))}")
    print(f"    8,8      : {computeWeird((8,8,'U'))}")
    print(f"    12,22    : {computeWeird((12,22,'U'))}")
    print(f"    56, 111  : {computeWeird((56,111,'U'))}")
    print(f"    238,956  : {computeWeird((238,956,'U'))}")
    print(f"    320,1280 : {computeWeird((320,1280,'U'))}")
    print("")

    # Testing getPOI()
    print("TEST: getPOI()")
    contact = (8, 8, "U")
    poiDetails = getPOI(contact)
    print(f"    Location:  {poiDetails['loc']}")
    print(f"    Type:      {poiDetails['type']}")
    print(f"    Name:      {poiDetails['name']}")
    print(f"    Adjective: {poiDetails['adj']}")
    print(f"    Weirdness: {poiDetails['weirdness']}")
    print(f"    Resources: {poiDetails['resources']}")
    print("")
