#!/bin/python3

## CHIP'S OCEAN GAME (COG) NAVIGATION MODULE
##
## Functions related to navigation - pretty self-explanatory.


# IMPORTS AND CONSTANTS
import math

from lib.configManager import loadConfig

confFile = "./etc/main.conf"


# FUNCTIONS
def computeBearing(ship, contact):
    # Calculates the bearing between a reference set of coordinates (ship) and
    # a remote set of coordinates (contact). Returns bearing as a float.
    if contact == None:
        return 0

    if ship[0] == contact[0]:     # Special case: If contact is directly above/
        if ship[1] > contact[1]:  # below ship then the normal algorithm will
            return 180            # error out (divide-by-zero).
        else:
            return 0

    offset = 90 if contact[0] > ship[0] else 270    # Determine horizontal offset

    slope = (contact[1]-ship[1])/(contact[0]-ship[0])
    angle = math.degrees(math.atan(slope))

    bearing = offset - angle    # Use offset to align angle w/ North
    return bearing

def computeRange(ship, contact):
    # Calculates the range to a contact. Takes in coordinates of the ship as
    # well as coordinates of the contact, returns range as a float.
    xSub = contact[0] - ship[0]
    ySub = contact[1] - ship[1]

    xSub = xSub**2
    ySub = ySub**2

    return math.sqrt(xSub+ySub)

def computeTravel(start, heading, distance):
    # Calculates the ship's new coordinates based on its starting position,
    # heading, and distance traveled.
    heading = math.radians(heading)
    x1 = start[0]
    y1 = start[1]

    x2 = distance*(math.sin(heading))
    y2 = distance*(math.cos(heading))

    fx = x1+x2
    fy = y1+y2

    return fx, fy

def computeEffectiveRange(base, modifier):
    # Calculates a sensor's effective range by taking in its base range and
    # modifier. Returns effective range as a float. 
    adjMod = modifier/100
    absMod = base*adjMod
    return base + absMod

def computeETA(speed, distance):
    # Pretty simple - computes the estimated time of arrival (ETA) given
    # current speed and distance to target. NOTE: Takes speed in knots, but
    # outputs ETA as minutes. 
    speed = speed / 60  # Converts speed from knots to nm per minute
    eta = distance/speed
    return eta

def convertETA(eta):
    # For display purposes, we often want to convert the raw ETA (in minutes) 
    # in to a more human-readable hours & minutes. Takes the raw ETA as input,
    # returns a string in the format of hh:mm (rounded to the nearest minute).
    hours   = math.floor(eta/60)
    minutes = round(eta%60)
    return f"{hours} hours, {minutes} minutes"

def getClosest(origin, contacts, farthest=False):
    # When given an origin point and a list of contacts, returns the contact
    # that's closest to the origin. Expects contacts as a list of tuple of 
    # tuples in the form of (id#, (X,Y,type)). Returns (id#, (X,Y,type), range)
    wRanges = []
    for contact in contacts:
        rng = computeRange(origin, contact[1])
        wRanges.append((contact[0], contact[1], rng))
    if not farthest:
        closest = min(wRanges, key=lambda x:x[2])
    # If "farthest" flag is set, then this function will actually return the
    # farthest away contact instead of the closest.
    else:
        closest = max(wRanges, key=lambda x:x[2])
    return closest


# INITIALIZATION
conf = loadConfig(confFile)


# UNIT TESTS
if __name__ == "__main__":
    ship    = (0,0)
    contact = (3,5)

    print("\nTesting computeBearing()")
    print(f"Ship at:    {ship}")
    print(f"Contact at: {contact}")
    print(f"\nBearing to contact:  {computeBearing(ship, contact)}")

    print("\nTesting computeRange()")
    print(f"Range to contact:  {computeRange(ship, contact)}")

    print("\nTesting computeTravel()")
    print("Starting at 0,0 and traveling 5.831nm at heading 30.9637.")
    print("Expect arrival coords at APPROXIMATELY 3,5")
    print(f"Received:   {computeTravel((0,0), 30.9637, 5.831)}")
    print("Starting at 5, 0 and traveling 5nm at heading 090.")
    print("Expect arrival coords at APPROXIMATELY 10, 0")
    print(f"Received:    {computeTravel((5,0), 90, 5)}")
    print("Starting at 3,3 and traveling 3nm at heading 045.")
    print("Expect arrival coords to be roughly equal")
    print(f"Received:    {computeTravel((3,3), 45, 3)}")

    print("\nTesting computeEffectiveRange()")
    r1 = computeEffectiveRange(50, 2.3)
    r2 = computeEffectiveRange(10, -0.8)
    print("BASE RANGES:    50,   10")
    print("MODIFIERS:     2.3, -0.8")
    print("EXPECT:      51.15, 9.92")
    print(f"GOT:         {r1}, {r2}")

    print("\nTesting getClosest()")
    shipLoc = (5.6, 6.7)
    contacts = [ (1, (2,3,"U")),
                 (2, (4,5,"L")),
                 (3, (6,7,"U")),
                 (4, (8,9,"L")) ]
    print("EXPECT:  (3, (6, 7, 'U'), 0.5000000000000001)")
    print(f"GOT:     {getClosest(shipLoc, contacts)}")
